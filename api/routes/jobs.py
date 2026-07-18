"""
模块: 职位 CRUD API 端点
提供职位的增删改查接口，包括分页列表、创建、读取、更新和软删除功能。
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.base import get_db
from models.job import Job
from api.schemas.job import (
    JobCreate,
    JobRead,
    JobUpdate,
    RequirementsSchema,
    ScoringWeightsSchema,
    EducationRequirementSchema,
)
from api.schemas.common import (
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _serialize_requirements(body: JobCreate) -> str:
    """将 JobCreate 中的各种要求字段序列化为 JSON 字符串存入 requirements 字段。

    Args:
        body: 创建职位的请求体

    Returns:
        JSON 字符串，包含硬性要求、加分项、学历要求、软技能和行业背景
    """
    data: dict = {}
    if body.requirements:
        data.update(body.requirements.model_dump())
    if body.education_requirement:
        data["education_requirement"] = body.education_requirement.model_dump()
    if body.soft_skills:
        data["soft_skills"] = body.soft_skills
    if body.industry_context:
        data["industry_context"] = body.industry_context
    return json.dumps(data, ensure_ascii=False)


def _deserialize_requirements(raw: str | None) -> dict:
    """将 requirements JSON 字符串解析为字典，供 JobRead 反序列化使用。

    Args:
        raw: 数据库中的 JSON 字符串

    Returns:
        解析后的字典，无效数据返回空字典
    """
    data = json.loads(raw) if raw else {}
    if not isinstance(data, dict):
        data = {}
    return data


def _job_to_read(job: Job) -> JobRead:
    """将 Job ORM 实例转换为 JobRead Pydantic 响应模型。

    反向处理 _serialize_requirements 的序列化逻辑，将 JSON 字段还原为结构化的 Pydantic 模型。

    Args:
        job: Job ORM 实例

    Returns:
        JobRead 响应模型
    """
    req = _deserialize_requirements(job.requirements)

    return JobRead(
        id=uuid.UUID(job.id),
        title=job.title,
        company=job.company or "",
        department=job.department,
        description=job.description or "",
        requirements=RequirementsSchema(
            hard=req.get("hard", []),
            nice_to_have=req.get("nice_to_have", []),
        ),
        education_requirement=(
            EducationRequirementSchema(**req["education_requirement"])
            if req.get("education_requirement") else None
        ),
        soft_skills=req.get("soft_skills", []),
        industry_context=req.get("industry_context"),
        scoring_weights=(
            ScoringWeightsSchema(**json.loads(job.scoring_weights))
            if job.scoring_weights and job.scoring_weights != "{}"
            else ScoringWeightsSchema()
        ),
        status=job.status,
        created_at=(
            datetime.fromisoformat(job.created_at)
            if job.created_at else datetime.now(timezone.utc)
        ),
    )


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.get("/", response_model=PaginatedResponse[JobRead])
async def list_jobs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: str | None = Query(None, description="按状态筛选"),
    db: Session = Depends(get_db),
):
    """获取职位列表，支持按状态筛选和分页。

    Args:
        page: 当前页码
        page_size: 每页条数
        status: 可选的状态过滤条件
        db: 数据库会话

    Returns:
        分页的职位列表
    """
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    else:
        # 默认不返回已关闭的职位
        query = query.filter(Job.status != "closed")
    query = query.order_by(desc(Job.created_at))

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedResponse[JobRead](
        items=[_job_to_read(j) for j in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("/", response_model=JobRead, status_code=201)
async def create_job(
    body: JobCreate,
    db: Session = Depends(get_db),
):
    """创建新的职位。

    Args:
        body: 职位创建请求体
        db: 数据库会话

    Returns:
        创建后的职位信息
    """
    job = Job(
        id=str(uuid.uuid4()),
        title=body.title,
        company=body.company,
        department=body.department,
        description=body.description,
        requirements=_serialize_requirements(body),
        scoring_weights=(
            body.scoring_weights.model_dump_json()
            if body.scoring_weights else "{}"
        ),
        status="open",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_to_read(job)


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """根据 ID 获取单个职位详情。

    Args:
        job_id: 职位 ID
        db: 数据库会话

    Returns:
        职位信息

    Raises:
        HTTPException 404: 职位不存在
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")
    return _job_to_read(job)


@router.put("/{job_id}", response_model=JobRead)
async def update_job(
    job_id: str,
    body: JobUpdate,
    db: Session = Depends(get_db),
):
    """更新已有职位的信息。仅更新提供字段，未提供字段保持不变。

    Args:
        job_id: 职位 ID
        body: 职位更新请求体（所有字段可选）
        db: 数据库会话

    Returns:
        更新后的职位信息

    Raises:
        HTTPException 404: 职位不存在
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")

    # 更新简单的标量字段
    for field in ("title", "company", "department", "description", "status"):
        value = getattr(body, field, None)
        if value is not None:
            setattr(job, field, value)

    # 如果任何要求相关字段被提供，则更新 requirements JSON 字段
    if any(
        getattr(body, f, None) is not None
        for f in ("requirements", "education_requirement", "soft_skills", "industry_context")
    ):
        current = _deserialize_requirements(job.requirements)
        if body.requirements is not None:
            current.update(body.requirements.model_dump())
        if body.education_requirement is not None:
            current["education_requirement"] = body.education_requirement.model_dump()
        if body.soft_skills is not None:
            current["soft_skills"] = body.soft_skills
        if body.industry_context is not None:
            current["industry_context"] = body.industry_context
        job.requirements = json.dumps(current, ensure_ascii=False)

    # 更新评分权重
    if body.scoring_weights is not None:
        job.scoring_weights = body.scoring_weights.model_dump_json()

    db.commit()
    db.refresh(job)
    return _job_to_read(job)


@router.delete("/{job_id}", response_model=MessageResponse)
async def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """软删除职位 — 将状态设为 'closed' 而非物理删除。

    Args:
        job_id: 职位 ID
        db: 数据库会话

    Returns:
        操作结果消息

    Raises:
        HTTPException 404: 职位不存在
        HTTPException 409: 职位已关闭
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")
    if job.status == "closed":
        raise HTTPException(status_code=409, detail="职位已关闭")

    job.status = "closed"
    db.commit()
    return MessageResponse(message=f"职位 {job_id} 已关闭")
