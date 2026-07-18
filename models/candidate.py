"""
模块: 候选人数据模型
定义候选人表的 SQLAlchemy ORM 模型，存储从简历中提取的结构化信息。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class Candidate(Base):
    """候选人 ORM 模型 — 映射到 candidates 表，存储简历解析结果和元数据"""

    __tablename__ = "candidates"

    # 主键 — 使用 UUID 字符串保证分布式唯一性
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # 候选人姓名 — 必填，建立索引方便搜索
    name = Column(String, nullable=False, index=True)
    # 电子邮箱
    email = Column(String, nullable=True)
    # 联系电话
    phone = Column(String, nullable=True)
    # 所在地
    location = Column(String, nullable=True)
    # 总工作年限
    years_of_experience = Column(Float, nullable=True)
    # JSON 格式的结构化简历数据（技能、工作经历、教育等）
    structured_data = Column(Text, nullable=False, default="{}")
    # Chroma 向量数据库中对应的文档 ID，用于语义检索
    chroma_doc_id = Column(String, nullable=True)
    # 记录创建时间 — ISO 格式字符串，同时设置 server_default 以确保数据库层也有默认值
    created_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        server_default=func.now(),
    )
    # 记录更新时间 — onupdate 在每次更新时自动刷新
    updated_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc).isoformat(),
    )

    # 关联的匹配结果列表 — 级联删除：候选人删除时所有匹配结果一并删除
    match_results = relationship("MatchResult", back_populates="candidate", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """调试用字符串表示"""
        return f"<Candidate(id={self.id!r}, name={self.name!r})>"
