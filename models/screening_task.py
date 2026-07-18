"""
模块: 筛选任务数据模型
定义筛选任务表的 SQLAlchemy ORM 模型，跟踪批量筛选作业的执行状态和进度。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class ScreeningTask(Base):
    """筛选任务 ORM 模型 — 映射到 screening_tasks 表，管理一次批量筛选作业"""

    __tablename__ = "screening_tasks"

    # 主键 — 使用 UUID 字符串
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 关联的职位 ID — 外键，级联删除
    job_id = Column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    # 任务状态：pending（等待中）/ running（运行中）/ completed（已完成）/ failed（失败）
    status = Column(
        String,
        nullable=False,
        default="pending",
        index=True,
    )
    # 待筛选候选人总数
    total_candidates = Column(Integer, nullable=True, default=0)
    # 已处理的候选人数
    processed_candidates = Column(Integer, nullable=False, default=0)
    # JSON 格式的筛选配置参数
    config = Column(Text, nullable=True, default="{}")
    # 任务创建时间
    created_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        server_default=func.now(),
    )
    # 任务完成时间 — 任务完成或失败时由业务逻辑写入
    completed_at = Column(String, nullable=True)

    # 关联的职位
    job = relationship("Job", back_populates="screening_tasks")
    # 关联的匹配结果列表 — 级联删除
    match_results = relationship("MatchResult", back_populates="task", cascade="all, delete-orphan")
    # 关联的偏差报告列表 — 级联删除
    bias_reports = relationship("BiasReport", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """调试用字符串表示"""
        return f"<ScreeningTask(id={self.id!r}, status={self.status!r})>"
