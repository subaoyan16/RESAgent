"""
模块: 筛选任务 Pydantic 数据模型
定义筛选任务、匹配结果、候选人排名等相关请求和响应数据模型。
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4


class ScreeningTaskCreate(BaseModel):
    """创建筛选任务请求模型 — 指定职位和待筛选的简历 ID 列表"""
    job_id: UUID = Field(..., description="职位唯一标识")
    resume_ids: list[str] = Field(..., description="待筛选的简历 ID 列表")
    config: Optional[dict] = Field(None, description="筛选配置参数")


class ScreeningTaskRead(BaseModel):
    """筛选任务响应模型 — 返回任务的创建信息与当前状态"""
    id: UUID = Field(default_factory=uuid4, description="任务唯一标识")
    job_id: UUID = Field(..., description="职位唯一标识")
    job_title: Optional[str] = Field(None, description="岗位名称")
    status: str = Field(default="pending", description="任务状态：pending/running/completed/failed")
    total_candidates: int = Field(default=0, description="候选人数总量")
    processed_candidates: int = Field(default=0, description="已处理候选人数")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")

    # 允许从 ORM 属性读取
    model_config = {"from_attributes": True}


class MatchDetailSchema(BaseModel):
    """单项匹配详情模型 — 描述单个技能在候选人与职位之间的匹配程度"""
    skill: str = Field(..., description="技能名称")
    requirement_level: str = Field(..., description="要求水平")
    candidate_level: str = Field(..., description="候选人水平")
    match_score: float = Field(..., description="匹配得分，0~1")


class GapSchema(BaseModel):
    """能力差距模型 — 描述候选人某项技能的差距及其严重程度"""
    skill: str = Field(..., description="技能名称")
    importance: float = Field(..., description="重要性，0~1")
    gap_severity: str = Field(..., description="差距严重程度：low/medium/high")


class TransferableSkillSchema(BaseModel):
    """可迁移技能模型 — 描述候选人已有技能与岗位需求技能的映射关系"""
    candidate_skill: str = Field(..., description="候选人已有技能")
    mapped_to: str = Field(..., description="映射到的岗位技能")
    similarity: float = Field(..., description="相似度，0~1")


class MatchResultRead(BaseModel):
    """匹配结果响应模型 — 返回单个候选人与职位的完整匹配评估"""
    id: UUID = Field(default_factory=uuid4, description="结果唯一标识")
    candidate_id: UUID = Field(..., description="候选人唯一标识")
    job_id: UUID = Field(..., description="职位唯一标识")
    overall_score: float = Field(..., description="综合评分，0~100")
    dimension_scores: dict[str, float] = Field(default_factory=dict, description="各维度评分")
    matched_skills: list[MatchDetailSchema] = Field(default_factory=list, description="匹配技能详情")
    gaps: list[GapSchema] = Field(default_factory=list, description="能力差距")
    transferable_skills: list[TransferableSkillSchema] = Field(default_factory=list, description="可迁移技能")
    highlights: list[str] = Field(default_factory=list, description="候选人亮点")
    risks: list[str] = Field(default_factory=list, description="候选人风险点")
    recommendation: str = Field(default="考虑", description="推荐建议：强烈推荐/推荐/考虑/不推荐")
    match_rationale: Optional[str] = Field(None, description="匹配理由详细说明")

    # 允许从 ORM 属性读取
    model_config = {"from_attributes": True}


class CandidateRanking(BaseModel):
    """候选人排名模型 — 用于展示候选人的综合排名简表"""
    candidate_id: UUID = Field(..., description="候选人唯一标识")
    name: str = Field(..., description="候选人姓名")
    overall_score: float = Field(..., description="综合评分")
    recommendation: str = Field(default="考虑", description="推荐建议")
