"""
模块: 候选人 Pydantic 数据模型
定义候选人相关的请求和响应数据模型，包括技能、工作经历、教育等子模型。
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4


class SkillSchema(BaseModel):
    """技能信息模型 — 表示单个技能的详细信息"""
    name: str = Field(..., description="技能名称，如 Python、项目管理")
    level: str = Field(..., description="熟练程度：entry/medium/expert")
    years: float = Field(..., description="经验年限")
    category: str = Field(default="", description="技能类别，如 programming、management")


class WorkExperienceSchema(BaseModel):
    """工作经历模型 — 表示一段工作经历的详细信息"""
    company: str = Field(..., description="公司名称")
    title: str = Field(..., description="职位名称")
    start_date: str = Field(..., description="开始日期，格式 YYYY-MM")
    end_date: Optional[str] = Field(None, description="结束日期，格式 YYYY-MM，在职则为空")
    responsibilities: list[str] = Field(default_factory=list, description="工作职责描述列表")
    achievements: list[str] = Field(default_factory=list, description="工作成就描述列表")
    tech_stack: list[str] = Field(default_factory=list, description="使用的技术栈")


class EducationSchema(BaseModel):
    """教育经历模型 — 表示一段教育经历的详细信息"""
    school: str = Field(..., description="学校名称")
    degree: str = Field(..., description="学位：博士/硕士/本科/大专")
    major: str = Field(..., description="专业名称")
    year: int = Field(..., description="毕业年份")


class CertificationSchema(BaseModel):
    """证书信息模型 — 表示单个证书"""
    name: str = Field(..., description="证书名称")


class LanguageSchema(BaseModel):
    """语言能力模型 — 表示一种语言的掌握程度"""
    name: str = Field(..., description="语言名称，如 中文、英语")
    level: str = Field(..., description="语言水平：native/fluent/intermediate/basic")


class CandidateCreate(BaseModel):
    """创建候选人请求模型 — 用于上传简历后手动补充或创建候选人信息"""
    name: str = Field(..., description="候选人姓名")
    email: str = Field(..., description="电子邮箱")
    phone: Optional[str] = Field(None, description="联系电话")
    location: Optional[str] = Field(None, description="所在地")
    years_of_experience: Optional[float] = Field(None, description="总工作年限")
    skills: list[SkillSchema] = Field(default_factory=list, description="技能列表")
    work_experience: list[WorkExperienceSchema] = Field(default_factory=list, description="工作经历列表")
    education: list[EducationSchema] = Field(default_factory=list, description="教育经历列表")
    certifications: list[CertificationSchema] = Field(default_factory=list, description="证书列表")
    languages: list[LanguageSchema] = Field(default_factory=list, description="语言能力列表")


class CandidateRead(BaseModel):
    """候选人响应模型 — 查询候选人时返回的完整信息"""
    id: UUID = Field(default_factory=uuid4, description="候选人唯一标识")
    name: str = Field(..., description="候选人姓名")
    email: str = Field(..., description="电子邮箱")
    phone: Optional[str] = Field(None, description="联系电话")
    location: Optional[str] = Field(None, description="所在地")
    years_of_experience: Optional[float] = Field(None, description="总工作年限")
    skills: list[SkillSchema] = Field(default_factory=list, description="技能列表")
    work_experience: list[WorkExperienceSchema] = Field(default_factory=list, description="工作经历列表")
    education: list[EducationSchema] = Field(default_factory=list, description="教育经历列表")
    certifications: list[CertificationSchema] = Field(default_factory=list, description="证书列表")
    languages: list[LanguageSchema] = Field(default_factory=list, description="语言能力列表")
    parsing_confidence: Optional[float] = Field(None, description="简历解析置信度，0~1")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")

    # 允许从 ORM 属性读取（SQLAlchemy -> Pydantic）
    model_config = {"from_attributes": True}


class CandidateUpdate(BaseModel):
    """更新候选人请求模型 — 所有字段可选，仅更新提供的字段"""
    name: Optional[str] = Field(None, description="候选人姓名")
    email: Optional[str] = Field(None, description="电子邮箱")
    phone: Optional[str] = Field(None, description="联系电话")
    location: Optional[str] = Field(None, description="所在地")
    years_of_experience: Optional[float] = Field(None, description="总工作年限")
    skills: Optional[list[SkillSchema]] = Field(None, description="技能列表")
    work_experience: Optional[list[WorkExperienceSchema]] = Field(None, description="工作经历列表")
    education: Optional[list[EducationSchema]] = Field(None, description="教育经历列表")
    certifications: Optional[list[CertificationSchema]] = Field(None, description="证书列表")
    languages: Optional[list[LanguageSchema]] = Field(None, description="语言能力列表")
