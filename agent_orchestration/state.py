"""LangGraph 筛选工作流的共享状态定义。

定义工作流中各个阶段所使用的数据结构（TypedDict），
涵盖简历解析、职位分析、检索召回、匹配结果、偏差检测和最终报告。

事件发布通过 contextvars 实现：图中节点调用 publish_event() 推送进度，
调用方（screening.py）在运行图之前注入 asyncio.Queue。
"""
from __future__ import annotations

import contextvars
import logging
from datetime import datetime, timezone
from typing import TypedDict, Optional, Annotated, Any
from operator import add
import uuid

logger = logging.getLogger(__name__)

# ── SSE 事件发布（依赖注入，解耦图与传输层）─────────────────────
_event_queue_ctx: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "event_queue", default=None
)


def get_event_queue() -> Any:
    return _event_queue_ctx.get()


def publish_event(event_type: str, **kwargs: Any) -> None:
    queue = _event_queue_ctx.get()
    if queue is None:
        return
    try:
        queue.put_nowait({
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        })
    except Exception:
        pass


class SkillItem(TypedDict, total=False):
    """单项技能信息。"""
    name: str
    level: str          # expert / intermediate / beginner — 技能熟练度等级
    years: float
    category: str


class WorkExperience(TypedDict, total=False):
    """工作经历信息。"""
    company: str
    title: str
    start_date: str
    end_date: str
    responsibilities: list[str]
    achievements: list[str]
    tech_stack: list[str]


class Education(TypedDict, total=False):
    """教育背景信息。"""
    school: str
    degree: str         # bachelor / master / phd — 学历等级
    major: str
    year: int


class ResumeData(TypedDict, total=False):
    """解析后的完整简历数据结构。"""
    candidate_id: str
    name: str
    email: str
    phone: str
    location: str
    years_of_experience: float
    skills: list[SkillItem]
    work_experience: list[WorkExperience]
    education: list[Education]
    certifications: list[str]
    languages: list[dict]
    parsing_confidence: float    # 解析置信度（0-1）
    raw_text: str                # 简历原始文本


class HardRequirement(TypedDict, total=False):
    """职位硬性要求（必备条件）。"""
    skill: str
    min_years: float             # 最低年限要求
    weight: float                # 该要求的权重
    category: str


class NiceToHave(TypedDict, total=False):
    """职位加分项（非必需但优先）。"""
    skill: str
    weight: float
    category: str


class JobRequirements(TypedDict, total=False):
    """职位需求分析结果。"""
    job_id: str
    title: str
    company: str
    hard: list[HardRequirement]
    nice_to_have: list[NiceToHave]
    education_requirement: dict
    soft_skills: list[str]       # 软技能要求列表
    industry_context: str        # 行业背景信息
    scoring_weights: dict        # 各维度的评分权重配置
    description: str             # 职位描述原文


class MatchDetail(TypedDict, total=False):
    """单项技能匹配详情。"""
    skill: str
    requirement_level: str       # 要求的熟练度等级
    candidate_level: str         # 候选人的熟练度等级
    match: float                 # 匹配度分数（0-1）


class GapItem(TypedDict, total=False):
    """候选人与职位之间的差距项。"""
    skill: str
    importance: str              # 差距重要性
    gap_severity: str            # 差距严重程度


class TransferableSkill(TypedDict, total=False):
    """可迁移技能映射。"""
    candidate_skill: str         # 候选人的原始技能名
    mapped_to: str               # 映射到的目标技能名
    similarity: float            # 语义相似度


class MatchResult(TypedDict, total=False):
    """候选人与职位的完整匹配结果。"""
    overall_match_score: float   # 综合匹配分数（0-1）
    dimension_scores: dict       # 各维度得分明细
    matched_skills: list[MatchDetail]
    gaps: list[GapItem]
    transferable_skills: list[TransferableSkill]
    highlights: list[str]        # 候选人亮点
    risks: list[str]             # 候选人风险点
    recommendation: str          # 推荐建议（strong_hire / recommend / hold / not_recommended）
    match_rationale: str         # 匹配理由说明
    top_candidates: list[dict]   # 按照相似度排序的候选人列表


class BiasFlag(TypedDict, total=False):
    """偏差检测的单项标记。"""
    type: str                    # 偏差类型（如 gender, age, ethnicity）
    severity: str                # 严重程度
    detail: str                  # 偏差详情说明
    affected_candidates: list[str]  # 受影响的候选人列表
    suggested_action: str        # 建议的修正措施


class BiasReport(TypedDict, total=False):
    """偏差检测完整报告。"""
    overall_fairness_score: float  # 整体公平性评分（0-1）
    flags: list[BiasFlag]
    distribution_analysis: dict    # 候选人分布的统计分析


class ScreeningState(TypedDict, total=False):
    """完整的共享状态，流经 5 个 Agent 的整个管线。

    该状态类型定义了工作流中所有节点之间传递的数据契约，
    包含输入、各阶段输出、人工审核标记和流程控制字段。

    关键设计:
      - Annotated[list[str], add] 字段使用 LangGraph 的 add 归约操作符，
        允许多个节点向同一列表追加错误信息而不会相互覆盖
      - status 字段跟踪任务生命周期：pending -> running -> completed -> failed
      - needs_human_review + human_decision 实现 Human-in-the-Loop 模式
    """
    # Task metadata — 任务元数据
    task_id: str
    job_id: str
    status: str                    # pending -> running -> completed -> failed — 任务状态流转

    # Input — 工作流入参
    resume_files: list[str]        # 待处理的简历文件路径列表
    job_description: str           # 职位描述的原始文本
    candidate_ids: list[str]       # 待筛选候选人 ID 列表
    top_k: int                     # 深度匹配上限（默认 5）

    # Parser Agent output — 解析 Agent 输出
    resume_data: Optional[ResumeData]
    parsing_errors: Annotated[list[str], add]

    # Job Analyzer Agent output — 职位分析 Agent 输出
    job_requirements: Optional[JobRequirements]
    analysis_errors: Annotated[list[str], add]

    # Retriever output — 混合检索 + 精排 + LLM 排序
    ranked_candidates: list[dict]   # [{id, name, score, reason}, ...]
    retrieval_metrics: dict         # BM25 / Chroma / Reranker 各阶段指标

    # Match Agent output — 匹配 Agent 输出
    match_result: Optional[MatchResult]
    match_errors: Annotated[list[str], add]
    match_results: list[dict]       # 批量匹配结果，供偏差检测分析

    # Bias Detector output — 偏差检测 Agent 输出
    bias_report: Optional[BiasReport]
    bias_errors: Annotated[list[str], add]

    # Report Generator output — 报告生成 Agent 输出
    final_report: Optional[str]
    report_errors: Annotated[list[str], add]

    # Human-in-the-Loop — 人工介入
    needs_human_review: bool
    human_decision: Optional[str]

    # Flow control — 流程控制
    skip_bias_detection: bool
    error_message: Optional[str]
