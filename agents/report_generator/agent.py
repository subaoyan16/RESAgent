"""
报告生成 Agent 模块。

该 Agent 根据整批筛选结果、岗位信息和偏差检测报告，
生成任务级别的结构化候选人评估 Markdown 报告。
使用 LLM 的 Flash 模式（确定性任务，不启用深度思考），
结果缓存 2 小时以提高重复查阅性能。
"""

import json
import logging

from services.llm_pool import llm_pool
from services.cache_service import cache_service
from .prompts import REPORT_GENERATOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def run(
    candidates: list[dict],
    job_info: dict,
    bias_report: dict | None = None,
) -> dict:
    """生成任务级别的候选人筛选评估报告。

    将全部匹配结果、岗位信息和偏差报告打包为上下文，
    调用 LLM（Flash 模式）生成结构化的中文 Markdown 报告。
    优先尝试缓存命中（相同输入 2 小时内复用）。

    Args:
        candidates: 所有候选人的匹配结果列表（已按分数降序排列），每项包含：
            rank, name, overall_score, recommendation, dimension_scores,
            matched_skills, gaps, transferable_skills, highlights, risks,
            match_rationale
        job_info: 岗位信息 dict，包含 title, company, department, description_summary
        bias_report: 可选的偏差检测报告

    Returns:
        {
            "final_report": str (Markdown),
            "status": "completed" | "failed",
            "report_errors": [...]  # 仅失败时
        }
    """
    if not candidates:
        return {
            "final_report": "# 候选人筛选评估报告\n\n*暂无匹配结果*",
            "status": "completed",
        }

    context = {
        "job_info": job_info,
        "total_candidates": len(candidates),
        "candidates": candidates,
        "bias_report": bias_report,
    }

    # 缓存检测：相同上下文的报告在 2 小时内直接复用
    cache_key = cache_service.make_key(
        "report", json.dumps(context, sort_keys=True, ensure_ascii=False)[:200]
    )
    cached = cache_service.get(cache_key)
    if cached:
        logger.info("Report cache hit for key %s", cache_key[:32])
        return {"final_report": cached, "status": "completed"}

    # 调用 Flash 模型（报告生成属于确定性任务，不需深度思考）
    model = llm_pool.get_model_for_task("report")
    messages = [
        {"role": "system", "content": REPORT_GENERATOR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Generate a comprehensive screening report in Chinese based on "
                "the following data:\n\n"
                f"{json.dumps(context, indent=2, ensure_ascii=False)}"
            ),
        },
    ]

    try:
        report_markdown = await llm_pool.chat(
            model=model,
            messages=messages,
            thinking=False,
            max_tokens=8192,
        )

        # 写入缓存，TTL 7200 秒（2 小时）
        cache_service.set(cache_key, report_markdown, ttl=7200)

        return {"final_report": report_markdown, "status": "completed"}
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        return {
            "report_errors": [f"Report generation failed: {str(e)}"],
            "final_report": _fallback_report(candidates, job_info, bias_report),
            "status": "completed",  # 降级为模板报告，不阻塞流程
        }


def _fallback_report(
    candidates: list[dict],
    job_info: dict,
    bias_report: dict | None = None,
) -> str:
    """LLM 失败时的模板降级报告——保证用户始终能看到结果。"""
    lines = [
        "# 候选人筛选评估报告",
        "",
        f"## 岗位信息",
        f"- **职位**: {job_info.get('title', 'N/A')}",
        f"- **公司**: {job_info.get('company', 'N/A')}",
        "",
        "## 候选人排名",
        "",
        "| 排名 | 姓名 | 综合评分 | 推荐等级 |",
        "|------|------|----------|----------|",
    ]
    for c in candidates:
        rec = c.get("recommendation", "")
        badge = {"strong_hire": "✅ 强烈推荐", "recommend": "推荐",
                 "hold": "⚠️ 待定"}.get(rec, rec)
        lines.append(
            f"| {c.get('rank', '-')} | **{c.get('name', '?')}** | "
            f"**{c.get('overall_score', 0)}** | {badge} |"
        )
    lines.append("")

    if bias_report:
        lines.append("## 公平性分析")
        fs = bias_report.get("overall_fairness_score", 1.0)
        lines.append(f"- **公平性评分**: {fs:.1f}/1.0")
        flags = bias_report.get("flags", [])
        if flags:
            lines.append("")
            for f in flags:
                lines.append(
                    f"- **{f.get('type', '?')}** ({f.get('severity', '?')}): "
                    f"{f.get('detail', '')}"
                )
        lines.append("")

    lines.append("\n---\n*报告由 ResAgent 自动生成 (模板降级模式)*")
    return "\n".join(lines)
