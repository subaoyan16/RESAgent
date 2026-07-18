"""
模块: 职位 Pydantic 数据模型
定义职位相关的请求和响应数据模型，包括要求、评分权重等子模型。
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4


class HardRequirementSchema(BaseModel):
    """硬性要求模型 — 职位必需满足的技能要求"""
    skill: str = Field(..., description="技能名称")
    min_years: float = Field(..., description="最低年限要求")
    weight: float = Field(default=1.0, description="权重，0~1")
    category: str = Field(default="", description="技能类别")


class NiceToHaveSchema(BaseModel):
    """加分项模型 — 非必需但具备更优的技能要求"""
    skill: str = Field(..., description="技能名称")
    weight: float = Field(default=0.5, description="权重，0~1")
    category: str = Field(default="", description="技能类别")


class RequirementsSchema(BaseModel):
    """职位要求汇总模型 — 包含硬性要求和加分项列表"""
    hard: list[HardRequirementSchema] = Field(default_factory=list, description="硬性要求列表")
    nice_to_have: list[NiceToHaveSchema] = Field(default_factory=list, description="加分项列表")


class EducationRequirementSchema(BaseModel):
    """学历要求模型 — 职位的最低学历和优先专业"""
    min_degree: str = Field(default="本科", description="最低学历要求：博士/硕士/本科/大专/不限")
    preferred_majors: list[str] = Field(default_factory=list, description="优先专业列表")


class ScoringWeightsSchema(BaseModel):
    """评分权重配置模型 — 各评分维度在综合评分中的占比"""
    skill_match: float = Field(default=0.4, ge=0, le=1, description="技能匹配权重")
    experience_relevance: float = Field(default=0.25, ge=0, le=1, description="经验相关性权重")
    education: float = Field(default=0.15, ge=0, le=1, description="学历权重")
    career_trajectory: float = Field(default=0.1, ge=0, le=1, description="职业轨迹权重")
    other: float = Field(default=0.1, ge=0, le=1, description="其他因素权重")


class JobCreate(BaseModel):
    """创建职位请求模型 — 新增招聘岗位时提交的信息"""
    title: str = Field(..., description="职位名称")
    company: str = Field(..., description="公司名称")
    department: Optional[str] = Field(None, description="所属部门")
    description: str = Field(..., description="职位描述")
    requirements: RequirementsSchema = Field(default_factory=RequirementsSchema, description="职位要求")
    education_requirement: Optional[EducationRequirementSchema] = Field(None, description="学历要求")
    soft_skills: list[str] = Field(default_factory=list, description="软技能要求")
    industry_context: Optional[str] = Field(None, description="行业背景要求")
    scoring_weights: ScoringWeightsSchema = Field(default_factory=ScoringWeightsSchema, description="评分权重配置")


class JobRead(BaseModel):
    """职位响应模型 — 查询职位时返回的完整信息"""
    id: UUID = Field(default_factory=uuid4, description="职位唯一标识")
    title: str = Field(..., description="职位名称")
    company: str = Field(..., description="公司名称")
    department: Optional[str] = Field(None, description="所属部门")
    description: str = Field(..., description="职位描述")
    requirements: RequirementsSchema = Field(default_factory=RequirementsSchema, description="职位要求")
    education_requirement: Optional[EducationRequirementSchema] = Field(None, description="学历要求")
    soft_skills: list[str] = Field(default_factory=list, description="软技能要求")
    industry_context: Optional[str] = Field(None, description="行业背景要求")
    scoring_weights: ScoringWeightsSchema = Field(default_factory=ScoringWeightsSchema, description="评分权重配置")
    status: str = Field(default="active", description="职位状态：active/closed/draft")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

    # 允许从 ORM 属性读取
    model_config = {"from_attributes": True}


class JobUpdate(BaseModel):
    """更新职位请求模型 — 所有字段可选，仅更新提供的字段"""
    title: Optional[str] = Field(None, description="职位名称")
    company: Optional[str] = Field(None, description="公司名称")
    department: Optional[str] = Field(None, description="所属部门")
    description: Optional[str] = Field(None, description="职位描述")
    requirements: Optional[RequirementsSchema] = Field(None, description="职位要求")
    education_requirement: Optional[EducationRequirementSchema] = Field(None, description="学历要求")
    soft_skills: Optional[list[str]] = Field(None, description="软技能要求")
    industry_context: Optional[str] = Field(None, description="行业背景要求")
    scoring_weights: Optional[ScoringWeightsSchema] = Field(None, description="评分权重配置")
    status: Optional[str] = Field(None, description="职位状态：active/closed/draft")
