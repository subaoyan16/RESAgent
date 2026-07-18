"""
模块: 报告 Pydantic 数据模型
定义偏差报告、报告输出和导出请求等与筛选报告相关的数据结构。
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4


class BiasFlagSchema(BaseModel):
    """偏差标记模型 — 记录筛选过程中检测到的某种偏差类型"""
    type: str = Field(..., description="偏差类型，如 gender_bias、name_bias")
    severity: str = Field(..., description="严重程度：low/medium/high")
    detail: str = Field(..., description="偏差详情描述")
    affected_candidates: list[UUID] = Field(default_factory=list, description="受影响的候选人 ID 列表")
    suggested_action: Optional[str] = Field(None, description="建议改进措施")


class DistributionAnalysisSchema(BaseModel):
    """分布分析模型 — 描述按不同维度（如性别、分数段）的分布情况"""
    gender_ratio_in_top10: Optional[float] = Field(None, description="前十名男女比例")
    avg_score_by_gender: Optional[dict[str, float]] = Field(None, description="按性别分类的平均分")
    score_distribution: Optional[dict[str, int]] = Field(None, description="分数段分布")
    diversity_metrics: Optional[dict[str, float]] = Field(None, description="多样性指标")


class BiasReportRead(BaseModel):
    """偏差报告响应模型 — 返回一次筛选任务的公平性分析结果"""
    id: UUID = Field(default_factory=uuid4, description="报告唯一标识")
    task_id: UUID = Field(..., description="关联的筛选任务 ID")
    fairness_score: float = Field(..., description="公平性评分，0~100")
    flags: list[BiasFlagSchema] = Field(default_factory=list, description="偏差标记列表")
    distribution_analysis: Optional[DistributionAnalysisSchema] = Field(None, description="分布分析")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

    # 允许从 ORM 属性读取
    model_config = {"from_attributes": True}


class ReportOutput(BaseModel):
    """报告输出模型 — 包含候选人的 Markdown 格式评估报告及相关元数据"""
    candidate_id: UUID = Field(..., description="候选人唯一标识")
    job_id: UUID = Field(..., description="职位唯一标识")
    markdown_content: str = Field(..., description="Markdown 格式报告内容")
    bias_flags: list[BiasFlagSchema] = Field(default_factory=list, description="偏差标记")
    overall_score: float = Field(..., description="综合评分")


class ExportRequest(BaseModel):
    """导出请求模型 — 指定报告导出的格式"""
    format: str = Field(default="pdf", description="导出格式：pdf/csv/json")
