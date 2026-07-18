"""
模块: 偏差报告数据模型
定义偏差报告表的 SQLAlchemy ORM 模型，存储筛选过程中的公平性分析和偏差检测结果。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class BiasReport(Base):
    """偏差报告 ORM 模型 — 映射到 bias_reports 表，记录一次筛选任务的公平性评估"""

    __tablename__ = "bias_reports"

    # 每个筛选任务只能有一条偏差报告（通过唯一约束保证）
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_bias_report_task"),
    )

    # 主键 — 使用 UUID 字符串
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 关联的筛选任务 ID — 外键，唯一且建立索引
    task_id = Column(
        String,
        ForeignKey("screening_tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # 整体公平性评分（0~100）
    fairness_score = Column(Float, nullable=True)
    # JSON 格式的偏差标记列表（如性别偏差、姓名偏差等）
    flags = Column(Text, nullable=True, default="[]")
    # JSON 格式的分布分析数据（如性别比例、分数分布等）
    distribution_analysis = Column(Text, nullable=True, default="{}")
    # 记录创建时间
    created_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        server_default=func.now(),
    )

    # 关联的筛选任务
    task = relationship("ScreeningTask", back_populates="bias_reports")

    def __repr__(self) -> str:
        """调试用字符串表示"""
        return f"<BiasReport(id={self.id!r}, fairness_score={self.fairness_score!r})>"
