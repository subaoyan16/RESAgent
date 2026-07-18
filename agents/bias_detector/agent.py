"""
偏差检测 Agent — 筛选结果批量公平性审计。

该 Agent 对整批筛选结果进行五维度公平性审计：
  1. 性别偏差 — 检测不同性别候选人在技能描述和评分中的系统性差异
  2. 年龄偏差 — 检测毕业年份、经验年限等年龄代理变量的歧视性评分
  3. 学历偏差 — 检测名校偏好导致的评分膨胀
  4. 地域偏差 — 检测基于地理位置或时区的隐性歧视
  5. 经验描述偏差 — 检测相同经验因候选人特征不同而被差异化描述

使用 DeepSeek V4 Pro thinking 模式进行深度语义分析，
根据 flag 严重级别（low/medium/high）决定是否需要人工复审。
"""

import json
import logging

from services.llm_pool import llm_pool
from services.cache_service import cache_service
from .prompts import BIAS_DETECTOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def run(match_results: list[dict], job_title: str = "") -> dict:
    """对批量匹配结果执行偏差检测。

    将全部候选人的匹配结果（评分、推荐、维度分数等）打包为分析快照，
    让 LLM 从宏观角度审计是否存在系统性偏见模式。
    优先尝试缓存命中（相同输入 1 小时内复用），
    否则调用 DeepSeek V4 Pro（thinking 模式）进行深度分析。

    Args:
        match_results: 所有候选人的匹配结果列表，每项包含：
            candidate_id, name, overall_score, recommendation,
            dimension_scores, highlights, risks, match_rationale
        job_title: 岗位名称（可选，用于上下文）

    Returns:
        {
            "bias_report": {
                "overall_fairness_score": float,
                "flags": [...],
                "distribution_analysis": {...},
                "confidence": str,
            },
            "needs_human_review": bool,
            "status": "running" | "failed",
        }
    """
    if not match_results:
        return {
            "bias_report": {
                "overall_fairness_score": 1.0,
                "flags": [],
                "distribution_analysis": {},
                "confidence": "high",
            },
            "needs_human_review": False,
            "status": "running",
        }

    # 构建分析快照：只保留偏差检测相关的字段，减少 token 消耗
    snapshot = []
    for r in match_results:
        dim_scores = r.get("dimension_scores", {})
        snapshot.append({
            "candidate_id": r.get("candidate_id", ""),
            "name": r.get("name", "未知"),
            "overall_score": r.get("overall_score", 0),
            "recommendation": r.get("recommendation", ""),
            "dimension_scores": {
                k: round(v, 2) for k, v in dim_scores.items()
            } if isinstance(dim_scores, dict) else {},
            "highlights": r.get("highlights", [])[:5],
            "risks": r.get("risks", [])[:5],
            "match_rationale": (r.get("match_rationale", "") or "")[:300],
        })

    context = {
        "job_title": job_title,
        "total_candidates": len(snapshot),
        "candidates": snapshot,
    }

    # 缓存检测：相同上下文的偏差报告在 1 小时内直接复用
    cache_key = cache_service.make_key(
        "bias", json.dumps(context, sort_keys=True, ensure_ascii=False)[:200]
    )
    cached = cache_service.get(cache_key)
    if cached:
        logger.info("Bias report cache hit for key %s", cache_key[:32])
        return {
            "bias_report": cached,
            "needs_human_review": _check_needs_review(cached),
            "status": "running",
        }

    # 调用 Pro 模型（thinking 模式）进行细致的批量偏差分析
    model = llm_pool.get_model_for_task("bias_detection")
    messages = [
        {"role": "system", "content": BIAS_DETECTOR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Analyze the following batch screening results for potential "
                "systemic bias. All detail/type/suggested_action text MUST be "
                "in Chinese.\n\n"
                f"{json.dumps(context, indent=2, ensure_ascii=False)}"
            ),
        },
    ]

    try:
        response = await llm_pool.chat(
            model=model,
            messages=messages,
            thinking=True,
            max_tokens=8192,
        )

        # 解析 LLM 返回的 JSON，兼容 markdown 代码块包裹
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        start = json_str.find("{")
        end = json_str.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = json_str[start:end + 1]

        bias_report = json.loads(json_str)

        needs_review = _check_needs_review(bias_report)

        # 写入缓存，TTL 3600 秒（1 小时）
        cache_service.set(cache_key, bias_report, ttl=3600)

        return {
            "bias_report": bias_report,
            "needs_human_review": needs_review,
            "status": "running",
        }
    except json.JSONDecodeError as e:
        logger.error("Bias detection JSON parse failed: %s", e)
        return {
            "bias_errors": [
                f"偏差检测 JSON 解析失败: {e}\n原始输出 (前 200 字符): {response[:200]}"
            ],
            "status": "failed",
        }
    except Exception as e:
        logger.error("Bias detection failed: %s", e)
        return {
            "bias_errors": [f"Bias detection failed: {str(e)}"],
            "status": "failed",
        }


def _check_needs_review(bias_report: dict) -> bool:
    """根据 flag 严重级别判断是否需要人工复审。"""
    flags = bias_report.get("flags", [])
    return any(
        f.get("severity") in ("medium", "high")
        for f in flags
    )
