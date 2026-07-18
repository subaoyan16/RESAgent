"""
模块: 职位数据模型
定义职位表的 SQLAlchemy ORM 模型，存储岗位描述、要求和评分配置。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Job(Base):
    """职位 ORM 模型 — 映射到 jobs 表，存储招聘岗位的详细信息"""

    __tablename__ = "jobs"

    # 主键 — 使用 UUID 字符串保证分布式唯一性
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 职位名称 — 建立索引方便搜索
    title = Column(String, nullable=False, index=True)
    # 公司名称
    company = Column(String, nullable=True)
    # 所属部门
    department = Column(String, nullable=True)
    # 职位详细描述
    description = Column(Text, nullable=True)
    # JSON 格式的职位要求（含硬性要求、加分项、学历要求等）
    requirements = Column(Text, nullable=True, default="{}")
    # JSON 格式的评分权重配置（各维度评分比例）
    scoring_weights = Column(Text, nullable=True, default="{}")
    # 职位状态：open（开放）/ closed（关闭）/ draft（草稿），建立索引以支持按状态筛选
    status = Column(String, nullable=False, default="open", index=True)
    # Chroma 向量数据库中对应的文档 ID
    chroma_doc_id = Column(String, nullable=True)
    # 记录创建时间
    created_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        server_default=func.now(),
    )

    # 关联的筛选任务列表 — 级联删除
    screening_tasks = relationship("ScreeningTask", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """调试用字符串表示"""
        return f"<Job(id={self.id!r}, title={self.title!r})>"
