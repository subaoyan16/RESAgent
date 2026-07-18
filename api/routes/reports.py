"""
模块: 报告查询与导出 API 端点
提供候选人评估报告的 LLM 生成（通过 report_generator Agent）和导出（Markdown / HTML）功能。
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from models.base import get_db
from models.screening_task import ScreeningTask
from models.match_result import MatchResult
from models.candidate import Candidate
from models.job import Job
from models.bias_report import BiasReport
from api.schemas.report import ReportOutput, BiasFlagSchema

router = APIRouter()


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


async def _build_report_async(task: ScreeningTask, db: Session) -> str:
    """调用 report_generator Agent 生成任务级别的候选人评估报告（Markdown）。

    聚合任务关联的全部匹配结果、岗位信息和偏差报告，
    通过 LLM（Flash 模式）生成结构化的中文 Markdown 报告。
    Agent 内部包含缓存和模板降级机制，确保高可用。

    Args:
        task: 筛选任务 ORM 实例
        db: 数据库会话

    Returns:
        Markdown 格式的完整报告文本
    """
    from agents.report_generator.agent import run as report_run

    match_results = (
        db.query(MatchResult)
        .filter(MatchResult.task_id == task.id)
        .order_by(MatchResult.overall_score.desc())
        .all()
    )
    if not match_results:
        return "# 候选人评估报告\n\n*暂无匹配结果*"

    # 构建候选人列表（已按分数降序）
    candidates = []
    for rank, m in enumerate(match_results, start=1):
        candidate = db.query(Candidate).filter(Candidate.id == m.candidate_id).first()
        dim_scores = json.loads(m.dimension_scores) if m.dimension_scores else {}
        candidates.append({
            "rank": rank,
            "name": candidate.name if candidate else "未知",
            "overall_score": m.overall_score or 0,
            "recommendation": m.recommendation or "",
            "dimension_scores": dim_scores,
            "matched_skills": json.loads(m.matched_skills) if m.matched_skills else [],
            "gaps": json.loads(m.gaps) if m.gaps else [],
            "transferable_skills": json.loads(m.transferable_skills) if m.transferable_skills else [],
            "highlights": json.loads(m.highlights) if m.highlights else [],
            "risks": json.loads(m.risks) if m.risks else [],
            "match_rationale": m.match_rationale or "",
        })

    # 岗位信息
    job = db.query(Job).filter(Job.id == match_results[0].job_id).first()
    job_info = {
        "title": job.title if job else "未知岗位",
        "company": job.company if job else "",
        "department": job.department if job else "",
        "description_summary": (job.description or "")[:300],
    }

    # 偏差报告
    bias_report = None
    bias = db.query(BiasReport).filter(BiasReport.task_id == task.id).first()
    if bias:
        flags = json.loads(bias.flags) if bias.flags else []
        bias_report = {
            "overall_fairness_score": bias.fairness_score or 1.0,
            "flags": flags,
            "distribution_analysis": json.loads(bias.distribution_analysis)
                if bias.distribution_analysis else {},
        }

    result = await report_run(candidates, job_info, bias_report)
    return result.get("final_report", "# 候选人评估报告\n\n*报告生成失败*")


def _markdown_to_html(md: str) -> str:
    """将基础 Markdown 转换为 HTML，用于 PDF 打印。

    这是一个轻量级转换器，仅处理报告中使用到的 Markdown 子集。
    完整的 Markdown 支持可考虑安装 ``markdown`` 包。

    Args:
        md: Markdown 格式的文本

    Returns:
        HTML 格式的文档字符串
    """
    lines = md.split("\n")
    html_parts: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        # 处理标题
        if stripped.startswith("### "):
            html_parts.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("# "):
            html_parts.append(f"<h1>{stripped[2:]}</h1>")

        # 水平分割线
        elif stripped.startswith("---"):
            html_parts.append("<hr>")

        # 表格行 — 遇到表格开始则创建 <table>，遇到分隔行则跳过
        elif stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not in_table:
                html_parts.append("<table border='1' cellpadding='6' style='border-collapse: collapse;'>")
                in_table = True
            if all(c.startswith("-") or c == "" for c in cells):
                continue  # 跳过表格分隔行
            html_parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        else:
            # 如果之前在处理表格，遇到非表格行时关闭 </table>
            if in_table:
                html_parts.append("</table>")
                in_table = False

            # 无序列表项
            if stripped.startswith("- "):
                html_parts.append(f"<li>{stripped[2:]}</li>")
            elif stripped.startswith("  - "):
                html_parts.append(f"<li>{stripped[4:]}</li>")

            # 内联加粗（**text** 格式）
            elif "**" in stripped:
                processed = stripped.replace("**", "<strong>", 1) if stripped.count("**") >= 2 else stripped
                if stripped.count("**") >= 2:
                    # 简单的成对替换 **text** -> <strong>text</strong>
                    parts = stripped.split("**")
                    result = ""
                    for i, p in enumerate(parts):
                        if i % 2 == 1:
                            result += f"<strong>{p}</strong>"
                        else:
                            result += p
                    html_parts.append(f"<p>{result}</p>")
                else:
                    html_parts.append(f"<p>{stripped}</p>")
            elif stripped:
                html_parts.append(f"<p>{stripped}</p>")

    if in_table:
        html_parts.append("</table>")

    # 包装为完整 HTML 文档，包含中文友好字体栈
    wrapper = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
body {{ font-family: 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', sans-serif; font-size: 12pt; line-height: 1.6; margin: 2cm; }}
h1 {{ color: #1a56db; font-size: 22pt; }}
h2 {{ color: #2563eb; font-size: 18pt; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }}
h3 {{ color: #374151; font-size: 14pt; }}
table {{ width: 100%; margin: 12px 0; }}
th, td {{ padding: 6px 10px; text-align: left; }}
hr {{ margin: 24px 0; }}
li {{ margin: 4px 0; }}
p {{ margin: 8px 0; }}
</style>
</head>
<body>
{"".join(html_parts)}
</body>
</html>"""
    return wrapper


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.get("/{task_id}", response_model=ReportOutput)
async def get_report(
    task_id: str,
    db: Session = Depends(get_db),
):
    """获取筛选任务的候选人评估报告（Markdown 格式）。

    Args:
        task_id: 筛选任务 ID
        db: 数据库会话

    Returns:
        ReportOutput 包含 Markdown 报告内容和偏差标记

    Raises:
        HTTPException 404: 任务不存在
    """
    task = db.query(ScreeningTask).filter(ScreeningTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="筛选任务不存在")

    markdown_content = await _build_report_async(task, db)

    # 收集偏差标记
    match_results = (
        db.query(MatchResult)
        .filter(MatchResult.task_id == task.id)
        .all()
    )
    bias_flags: list = []
    bias_report = (
        db.query(BiasReport)
        .filter(BiasReport.task_id == task.id)
        .first()
    )
    if bias_report:
        flags_data = json.loads(bias_report.flags) if bias_report.flags else []
        for flag in flags_data:
            bias_flags.append(BiasFlagSchema(**flag))

    # 计算所有候选人的平均综合评分
    scores = [m.overall_score for m in match_results if m.overall_score is not None]
    overall_score = sum(scores) / len(scores) if scores else 0.0

    first_result = match_results[0] if match_results else None

    return ReportOutput(
        candidate_id=(
            uuid.UUID(first_result.candidate_id)
            if first_result else uuid.UUID(int=0)
        ),
        job_id=(
            uuid.UUID(first_result.job_id)
            if first_result else uuid.UUID(int=0)
        ),
        markdown_content=markdown_content,
        bias_flags=bias_flags,
        overall_score=overall_score,
    )


@router.get("/{task_id}/export")
async def export_report(
    task_id: str,
    fmt: str = Query("pdf", alias="format", description="导出格式：'pdf' 或 'markdown'"),
    db: Session = Depends(get_db),
):
    """导出评估报告为可下载文件。

    支持 ``format=markdown``（返回 .md 文件）和 ``format=pdf``
    （返回专为 PDF 打印优化的 HTML 文档）。
    如需真正的 PDF 生成，请安装 ``weasyprint`` 或 ``pdfkit`` 并替换此处的 HTML 渲染逻辑。

    Args:
        task_id: 筛选任务 ID
        fmt: 导出格式（markdown / pdf）
        db: 数据库会话

    Returns:
        响应对象，包含文件内容和适当的 Content-Disposition 头

    Raises:
        HTTPException 404: 任务不存在
    """
    task = db.query(ScreeningTask).filter(ScreeningTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="筛选任务不存在")

    md_content = await _build_report_async(task, db)

    if fmt == "markdown":
        return Response(
            content=md_content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="report_{task_id}.md"',
            },
        )

    # 默认返回 HTML 格式（适合浏览器打印为 PDF）
    html_content = _markdown_to_html(md_content)
    return Response(
        content=html_content,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="report_{task_id}.html"',
        },
    )
