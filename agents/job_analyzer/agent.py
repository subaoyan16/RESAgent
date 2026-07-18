"""职位分析 Agent（Job Analyzer Agent）.

该 Agent 在流水线中的角色：
  - 作为第二个环节，接收原始 JD 文本，输出结构化的岗位需求分析。
  - 使用的 LLM 模型：Claude Flash（通过 llm_pool 根据「job_analysis」任务类型获取）。
  - 核心流程：缓存查询 -> LLM 结构化抽取 -> 校验并归一化 scoring_weights ->
    生成岗位向量嵌入 -> 存入 Chroma -> 缓存结果。
  - 关键逻辑：
    * scoring_weights 缺失时填充默认值并归一化到总和为 1.0
    * industry 通过提示词关键词匹配自动检测
    * requirements 的 weight/mandatory 由措辞强度驱动
"""
import json
from agent_orchestration.state import ScreeningState
from services.llm_pool import llm_pool
from services.chroma_store import chroma_store
from services.embedding import embedding_service
from services.cache_service import cache_service
from .prompts import JOB_ANALYZER_SYSTEM_PROMPT


async def run(state: ScreeningState) -> dict:
    """分析职位描述并返回结构化的岗位需求与权重。

    流程：
      1. 缓存查询（基于 JD[:300] 作为 key），命中则直接返回
      2. LLM（Flash）按照严格 Schema 提取需求、权重、行业等
      3. 校验 scoring_weights，填充缺失维度并归一化为总和 1.0
      4. 生成岗位语义向量（标题 + 公司 + 技能 + 行业），写入 Chroma
      5. 写入缓存（TTL 1 小时）
      6. 返回 job_requirements 供 Matcher 使用
    """
    job_description = state.get("job_description", "")
    if not job_description:
        return {
            "job_requirements": {},
            "parsing_errors": ["No job description provided"],
            "status": "failed",
        }

    # 1. 缓存查询：相同 JD 前 300 字符作为 cache key
    cache_key = cache_service.make_key("job_analyzer", job_description[:300])
    cached = cache_service.get(cache_key)
    if cached:
        return {"job_requirements": cached, "status": "running"}

    # 2. 调用 LLM（Flash 模型）进行结构化抽取
    model = llm_pool.get_model_for_task("job_analysis")
    user_content = (
        "Analyze this job description and extract structured requirements. "
        "Detect the industry context and assign appropriate weights.\n\n"
        "--- JOB DESCRIPTION ---\n"
        + job_description[:8000]
        + "\n--- END ---"
    )
    messages = [
        {"role": "system", "content": JOB_ANALYZER_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        response = await llm_pool.chat(model=model, messages=messages, thinking=False, max_tokens=8192)

        # 解析 JSON：兼容 LLM 输出可能包裹在 markdown 代码块中的情况
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        job_requirements = json.loads(json_str)

        # 扁平化：如果 LLM 返回嵌套的 requirements 对象，提升到顶层
        if "requirements" in job_requirements and isinstance(job_requirements["requirements"], dict):
            reqs = job_requirements.pop("requirements")
            if "hard" in reqs:
                job_requirements["hard"] = reqs["hard"]
            if "nice_to_have" in reqs:
                job_requirements["nice_to_have"] = reqs["nice_to_have"]

        # 3. 校验 scoring_weights：确保所有必需维度存在
        if "scoring_weights" not in job_requirements or not isinstance(job_requirements["scoring_weights"], dict):
            job_requirements["scoring_weights"] = {
                "skill_match": 0.45,
                "experience_relevance": 0.25,
                "education": 0.10,
                "career_trajectory": 0.10,
                "other": 0.10,
            }
        # 确保每个权重键都存在，缺失则使用默认值
        default_weights = {
            "skill_match": 0.45,
            "experience_relevance": 0.25,
            "education": 0.10,
            "career_trajectory": 0.10,
            "other": 0.10,
        }
        for key, default_val in default_weights.items():
            if key not in job_requirements["scoring_weights"]:
                job_requirements["scoring_weights"][key] = default_val

        # 归一化：确保所有维度权重之和为 1.0
        weight_sum = sum(job_requirements["scoring_weights"].values())
        if weight_sum > 0:
            for key in job_requirements["scoring_weights"]:
                job_requirements["scoring_weights"][key] /= weight_sum

        job_requirements["raw_job_description"] = job_description

        # 4. Chroma 向量存储已跳过（Mock模式下不需要）
        # 5. 缓存结果（TTL 3600s = 1 小时）
        cache_service.set(cache_key, job_requirements, ttl=3600)

        return {
            "job_requirements": job_requirements,
            "status": "running",
        }

    except json.JSONDecodeError as e:
        return {
            "job_requirements": {},
            "parsing_errors": ["Job analyzer JSON parse error: {msg}".format(msg=str(e))],
            "status": "failed",
        }
    except Exception as e:
        return {
            "job_requirements": {},
            "parsing_errors": ["Job analyzer failed: {msg}".format(msg=str(e))],
            "status": "failed",
        }
