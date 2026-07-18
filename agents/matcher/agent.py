"""
Matcher Agent — 候选人与岗位的深度语义匹配。

负责将候选人简历与岗位需求进行四层匹配分析：
  1. 精确匹配：技能名称完全相同，置信度 0.9-1.0
  2. 语义匹配：同义词或紧密相关技能，置信度 0.7-0.9
  3. 可迁移匹配：跨领域可复用能力，置信度 0.4-0.7
  4. 维度评分：技能、经验、学历、职业轨迹四维综合打分

使用 DeepSeek V4 Pro thinking 模式进行深度推理，最终输出
综合评分、各维度得分、匹配技能详情、差距分析和推荐建议。
"""

import json
from agent_orchestration.state import ScreeningState
from services.llm_pool import llm_pool
from agent_orchestration.tools.calculator import calculate_match_score, determine_recommendation
from .prompts import MATCHER_SYSTEM_PROMPT


def _build_match_messages(resume_data: dict, job_requirements: dict) -> list[dict]:
    """构建发送给 LLM 的匹配请求消息。

    将候选人简历数据和岗位需求分别截断至 4000 字符后嵌入 user 消息，
    配合系统提示词指导 LLM 执行深度语义匹配分析。

    Args:
        resume_data: 解析后的候选人简历数据字典
        job_requirements: 结构化岗位需求数据字典

    Returns:
        OpenAI 格式的消息列表 [{"role": "system", ...}, {"role": "user", ...}]
    """
    return [
        {"role": "system", "content": MATCHER_SYSTEM_PROMPT},
        {"role": "user", "content": (
            "请对以下候选人和岗位进行深度匹配分析：\n\n"
            f"=== 候选人简历 ===\n{json.dumps(resume_data, ensure_ascii=False, indent=2)[:4000]}\n\n"
            f"=== 岗位需求 ===\n{json.dumps(job_requirements, ensure_ascii=False, indent=2)[:4000]}"
        )},
    ]


async def run(state: ScreeningState) -> dict:
    """执行候选人-岗位深度匹配分析。

    从 state 中提取 resume_data 和 job_requirements，调用 DeepSeek V4 Pro
    进行四层语义匹配，然后用 calculator 工具计算加权综合评分和推荐等级。

    容错设计:
      - LLM 返回的 JSON 可能被包裹在 Markdown 代码块中，自动剥离
      - JSON 解析失败时使用 raw_decode 解析最长有效前缀
      - 匹配失败时返回空 match_result + failed 状态，不中断管道

    Args:
        state: 当前筛选状态，必须包含 resume_data 和 job_requirements

    Returns:
        包含 match_result、parsing_errors 和 status 的字典
    """
    resume_data = state.get("resume_data")
    job_requirements = state.get("job_requirements")

    if not resume_data or not job_requirements:
        return {
            "match_result": {},
            "parsing_errors": ["Missing resume_data or job_requirements"],
            "status": "failed",
        }

    try:
        # 调用 LLM 进行深度匹配，增大 max_tokens 防止 JSON 截断
        model = llm_pool.get_model_for_task("matching")
        messages = _build_match_messages(resume_data, job_requirements)
        response = await llm_pool.chat(model=model, messages=messages, thinking=True, max_tokens=8192)

        # 解析 LLM 返回的 JSON（容错处理：LLM 可能输出格式瑕疵）
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        try:
            match_data = json.loads(json_str)
        except json.JSONDecodeError:
            # raw_decode 解析最长有效 JSON 前缀，忽略尾部截断内容
            decoder = json.JSONDecoder()
            match_data, _ = decoder.raw_decode(json_str)

        # 计算综合评分
        dim_scores = match_data.get("dimension_scores", {})
        weights = job_requirements.get("scoring_weights", {})
        overall = calculate_match_score(dimension_scores=dim_scores, scoring_weights=weights)

        # 构建匹配结果
        return {
            "match_result": {
                "overall_match_score": overall,
                "dimension_scores": dim_scores,
                "matched_skills": match_data.get("matched_skills", []),
                "gaps": match_data.get("unmatched_requirements", []),
                "transferable_skills": match_data.get("transferable_skills", []),
                "highlights": match_data.get("strengths", []),
                "risks": match_data.get("weaknesses", []),
                "recommendation": determine_recommendation(overall, len(match_data.get("unmatched_requirements", [])) > 0),
                "match_rationale": match_data.get("recommendation_rationale", ""),
            },
            "parsing_errors": [],
            "status": "running",
        }

    except Exception as e:
        return {
            "match_result": {},
            "parsing_errors": [f"Match failed: {str(e)}"],
            "status": "failed",
        }
