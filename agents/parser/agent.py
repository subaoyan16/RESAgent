"""简历解析 Agent（Resume Parser Agent）.

该 Agent 在流水线中的角色：
  - 作为第一个环节，接收原始简历文件（PDF/DOCX），输出结构化的 JSON 数据。
  - 使用的 LLM 模型：Claude Flash（通过 llm_pool 根据「parsing」任务类型获取）。
  - 核心流程：提取文本 -> 缓存查询 -> LLM 结构化抽取 -> 校验字段 ->
    生成向量嵌入 -> 存入 Chroma 向量库 -> 缓存结果 -> 返回（附解析置信度）。
  - 低置信度（<0.8）时会附带警告信息，供下游 Agent 判断是否需要人工复核。
"""
import json
import os
from agent_orchestration.state import ScreeningState
from services.llm_pool import llm_pool
from services.pdf_parser import doc_parser
from services.chroma_store import chroma_store
from services.embedding import embedding_service
from services.cache_service import cache_service
from .prompts import PARSER_SYSTEM_PROMPT

async def run(state: ScreeningState) -> dict:
    """解析简历文件并返回结构化 JSON 数据，同时生成向量嵌入存入 Chroma。

    流程：
      1. 从 PDF/Word 中提取原始文本 -> 清洗
      2. 缓存查询（基于 text[:200] 作为 key），命中则直接返回
      3. LLM（Flash）按照严格 Schema 提取结构化 JSON
      4. 校验必需字段（basic_info、skills）
      5. 生成 candidate 的语义向量，写入 Chroma 用于后续语义检索
      6. 写入缓存（TTL 1 小时）
      7. 返回含 parsing_confidence 的结果及低置信度警告
    """
    resume_files = state.get("resume_files", [])
    if not resume_files:
        return {"parsing_errors": ["No resume files provided"], "status": "failed"}

    file_path = resume_files[0]  # 当前仅处理第一个文件；批量处理由上游编排

    # 1. 提取并清洗原始文本
    raw_text = doc_parser.extract_text(file_path)
    cleaned_text = doc_parser.clean_text(raw_text)

    # 2. 缓存查询：相同内容的前 200 字符作为 cache key，避免重复解析
    cache_key = cache_service.make_key("parser", cleaned_text[:200])
    cached = cache_service.get(cache_key)
    if cached:
        return {"resume_data": cached, "status": "running"}

    # 3. 调用 LLM（Flash 模型）进行结构化提取
    model = llm_pool.get_model_for_task("parsing")
    messages = [
        {"role": "system", "content": PARSER_SYSTEM_PROMPT},
        {"role": "user", "content": "Extract structured information from this resume:\n\n" + cleaned_text[:8000]},
    ]

    try:
        response = await llm_pool.chat(model=model, messages=messages, thinking=False, max_tokens=16384)
        # 解析 JSON：兼容 LLM 输出可能包裹在 markdown 代码块中的情况
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        try:
            resume_data = json.loads(json_str)
        except json.JSONDecodeError:
            # 容错：只解析最长有效 JSON 前缀，忽略尾部截断内容
            decoder = json.JSONDecoder()
            resume_data, _ = decoder.raw_decode(json_str)

        # 4. 校验必需字段，缺失时设置默认值以避免下游处理异常
        if "basic_info" not in resume_data:
            resume_data["basic_info"] = {}
        if "skills" not in resume_data:
            resume_data["skills"] = []
        resume_data["candidate_id"] = state.get("task_id", "unknown") + "_candidate"
        resume_data["raw_text"] = cleaned_text

        # 5. 生成语义嵌入并存储到 Chroma 向量库
        #     嵌入文本为「姓名 + 技能列表」，供后续语义检索匹配使用
        embedding_text = "{name} {skills}".format(
            name=resume_data.get("basic_info", {}).get("name", ""),
            skills=" ".join(s["name"] if isinstance(s, dict) else str(s) for s in resume_data.get("skills", [])),
        )
        embedding = embedding_service.embed_query(embedding_text)
        chroma_store.add_candidate(
            candidate_id=resume_data["candidate_id"],
            document=cleaned_text[:2000],
            metadata={
                "name": resume_data.get("basic_info", {}).get("name", "Unknown"),
                "years_of_experience": resume_data.get("basic_info", {}).get("years_of_experience", 0),
                "skills": [s["name"] if isinstance(s, dict) else s for s in resume_data.get("skills", [])],
                "location": resume_data.get("basic_info", {}).get("location", ""),
            },
            embedding=embedding,
        )

        # 6. 缓存结果（TTL 3600s = 1 小时）
        cache_service.set(cache_key, resume_data, ttl=3600)

        confidence = resume_data.get("parsing_confidence", 0.5)
        parsing_errors = []
        # 低置信度警告：用于提醒下游或人工审核
        if confidence < 0.8:
            low_conf_msg = "Low parsing confidence: {c}. Please verify: name, email, skills.".format(c=confidence)
            parsing_errors.append(low_conf_msg)

        return {
            "resume_data": resume_data,
            "parsing_errors": parsing_errors,
            "status": "running",
        }
    except Exception as e:
        return {"parsing_errors": ["Parser failed: {msg}".format(msg=str(e))], "status": "failed"}
