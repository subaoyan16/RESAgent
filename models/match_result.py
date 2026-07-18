"""
模块: 匹配结果数据模型
定义匹配结果表的 SQLAlchemy ORM 模型，存储候选人与职位之间的详细匹配评分。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class MatchResult(Base):
    """匹配结果 ORM 模型 — 映射到 match_results 表，记录单个候选人与职位的匹配详情"""

    __tablename__ = "match_results"

    # 主键 — 使用 UUID 字符串
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 关联的筛选任务 ID — 外键，级联删除
    task_id = Column(
        String,
        ForeignKey("screening_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 关联的候选人 ID — 外键，级联删除
    candidate_id = Column(
        String,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 关联的职位 ID — 外键，级联删除
    job_id = Column(
        String,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 综合匹配评分（0~100）
    overall_score = Column(Float, nullable=True)
    # JSON 格式的各维度评分（如技能匹配、经验相关性、学历等）
    dimension_scores = Column(Text, nullable=True, default="{}")
    # JSON 格式的匹配技能列表
    matched_skills = Column(Text, nullable=True, default="[]")
    # JSON 格式的能力差距列表
    gaps = Column(Text, nullable=True, default="[]")
    # JSON 格式的可迁移技能列表
    transferable_skills = Column(Text, nullable=True, default="[]")
    # JSON 格式的候选人亮点列表
    highlights = Column(Text, nullable=True, default="[]")
    # JSON 格式的候选人风险点列表
    risks = Column(Text, nullable=True, default="[]")
    # 推荐建议：强烈推荐 / 推荐 / 考虑 / 不推荐
    recommendation = Column(String, nullable=True)
    # 匹配理由的详细说明文本
    match_rationale = Column(Text, nullable=True)
    # 记录创建时间
    created_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        server_default=func.now(),
    )

    # 关联的筛选任务
    task = relationship("ScreeningTask", back_populates="match_results")
    # 关联的候选人
    candidate = relationship("Candidate", back_populates="match_results")
    # 关联的职位（仅用于读取，不定义反向引用）
    job = relationship("Job")

    def __repr__(self) -> str:
        """调试用字符串表示"""
        return f"<MatchResult(id={self.id!r}, score={self.overall_score!r})>"
