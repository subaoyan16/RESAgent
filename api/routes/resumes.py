"""
模块: 简历上传与候选人管理 API 端点
提供简历文件上传、文本提取、候选人列表查询和删除功能。
"""
import json
import uuid
import os as os_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.base import get_db
from models.candidate import Candidate
from api.schemas.candidate import CandidateRead
from api.schemas.common import (
    MessageResponse,
    PaginatedResponse,
)
from services.pdf_parser import doc_parser

router = APIRouter()

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 上传文件存储目录 — 相对于项目根目录的 data/uploads/
UPLOAD_DIR = os_mod.path.join(os_mod.path.dirname(os_mod.path.dirname(os_mod.path.dirname(os_mod.path.abspath(__file__)))), "data", "uploads")
# 允许上传的文件扩展名集合（不可变集合保证不会被意外修改）
_ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"})


def _ensure_upload_dir() -> str:
    """确保上传目录存在，若不存在则创建。

    Returns:
        上传目录路径
    """
    os_mod.makedirs(UPLOAD_DIR, exist_ok=True)
    return UPLOAD_DIR


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _candidate_to_read(candidate: Candidate) -> CandidateRead:
    """将 Candidate ORM 实例转换为 CandidateRead Pydantic 响应模型。

    从 JSON 字段 structured_data 中提取结构化信息，组装为 Pydantic 模型。

    Args:
        candidate: Candidate ORM 实例

    Returns:
        CandidateRead 响应模型
    """
    sd = json.loads(candidate.structured_data) if candidate.structured_data else {}

    # 归一化：LLM 可能返回缺失字段或 None，统一填充默认值
    raw_skills = sd.get("skills", [])
    skills = []
    for s in raw_skills:
        if isinstance(s, dict):
            skills.append({
                "name": s.get("name", ""),
                "level": s.get("level", "intermediate"),
                "years": s.get("years") or 0,
                "category": s.get("category", ""),
            })
        else:
            skills.append({"name": str(s), "level": "intermediate", "years": 0, "category": ""})

    raw_work = sd.get("work_experience", [])
    work_experience = []
    for w in raw_work:
        if isinstance(w, dict):
            work_experience.append({
                "company": w.get("company", ""),
                "title": w.get("title", ""),
                "start_date": w.get("start_date", ""),
                "end_date": w.get("end_date"),
                "responsibilities": w.get("responsibilities", []),
                "achievements": w.get("achievements", []),
                "tech_stack": w.get("tech_stack", []),
            })
        else:
            work_experience.append({"company": str(w), "title": "", "start_date": "", "end_date": None, "responsibilities": [], "achievements": [], "tech_stack": []})

    raw_edu = sd.get("education", [])
    education = []
    for e in raw_edu:
        if isinstance(e, dict):
            education.append({
                "school": e.get("school", ""),
                "degree": e.get("degree", ""),
                "major": e.get("major", ""),
                "year": e.get("year") or 0,
            })
        else:
            education.append({"school": str(e), "degree": "", "major": "", "year": 0})

    raw_certs = sd.get("certifications", [])
    certs = [{"name": c} if isinstance(c, str) else c for c in raw_certs]

    raw_langs = sd.get("languages", [])
    langs = [{"name": l} if isinstance(l, str) else l for l in raw_langs]

    return CandidateRead(
        id=uuid.UUID(candidate.id),
        name=candidate.name,
        email=candidate.email or "",
        phone=candidate.phone,
        location=candidate.location,
        years_of_experience=candidate.years_of_experience,
        skills=skills,
        work_experience=work_experience,
        education=education,
        certifications=certs,
        languages=langs,
        parsing_confidence=sd.get("parsing_confidence"),
        created_at=(
            datetime.fromisoformat(candidate.created_at)
            if candidate.created_at else datetime.now(timezone.utc)
        ),
        updated_at=(
            datetime.fromisoformat(candidate.updated_at)
            if candidate.updated_at else datetime.now(timezone.utc)
        ),
    )


def _validate_extension(filename: str) -> str:
    """验证文件扩展名是否在允许列表中。

    Args:
        filename: 上传的文件名

    Returns:
        小写的文件扩展名

    Raises:
        HTTPException 400: 文件格式不支持
    """
    ext = os_mod.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 '{ext}'。允许的类型: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )
    return ext


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=CandidateRead, status_code=201)
async def upload_resume(
    file: UploadFile = File(..., description="简历文件（PDF、DOCX、TXT 或图片格式）"),
    db: Session = Depends(get_db),
):
    """上传简历文件，提取文本内容并创建候选人记录。

    文件以 UUID 重命名后保存到 data/uploads/ 目录避免冲突。
    立即执行基础文本提取，完整的结构化解析在筛选工作流中完成。

    Args:
        file: 上传的简历文件
        db: 数据库会话

    Returns:
        创建的候选人信息

    Raises:
        HTTPException 400: 未提供文件名或格式不支持
        HTTPException 422: 文本提取失败
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    ext = _validate_extension(file.filename)
    _ensure_upload_dir()

    # 生成唯一文件名并保存上传文件
    stored_name = f"{uuid.uuid4()}{ext}"
    stored_path = os_mod.path.join(UPLOAD_DIR, stored_name)

    content = await file.read()
    with open(stored_path, "wb") as f:
        f.write(content)

    # 使用文档解析器提取文本内容
    try:
        raw_text = doc_parser.extract_text(stored_path)
        cleaned_text = doc_parser.clean_text(raw_text)
    except Exception as exc:
        print(f"[UPLOAD-ERR] 文本提取失败 [{file.filename}]: {exc}", flush=True)
        raise HTTPException(
            status_code=422,
            detail=f"文本提取失败 ({type(exc).__name__}): {exc}",
        )

    # 使用原始文件名（不含扩展名）作为候选人姓名（初步推测）
    candidate_name = os_mod.path.splitext(file.filename)[0]

    # ---- RAG 索引阶段：LLM解析 → BGE-M3向量化 → Chroma入库 ----
    from agents.parser.agent import run as parser_run
    from agent_orchestration.state import ScreeningState
    from services.embedding import embedding_service
    from services.chroma_store import chroma_store

    parse_state = ScreeningState(task_id="upload", job_id="upload", status="running",
                                 resume_files=[stored_path], job_description="")
    parser_result = await parser_run(parse_state)
    rd = parser_result.get("resume_data")
    if not rd:
        errors = parser_result.get("parsing_errors", ["未知错误"])
        print(f"[UPLOAD-ERR] LLM解析失败 [{file.filename}]: {errors}", flush=True)
        raise HTTPException(
            status_code=422,
            detail=f"LLM 解析失败 [{file.filename}]: 文本长度={len(cleaned_text)}, "
                   f"错误={errors}. 请检查简历文件是否包含可读文本。",
        )

    rd_name = rd.get("name") or candidate_name

    # 去重：取简历文本前 500 字符的哈希，内容相同的简历复用已有 Candidate
    import hashlib
    content_hash = hashlib.sha256(cleaned_text[:500].encode()).hexdigest()
    existing = db.query(Candidate).filter(Candidate.structured_data.like(f"%{content_hash}%")).first()

    if existing:
        candidate = existing
        candidate.name = rd_name  # 更新名字（LLM 可能提取出更好的名字）
        candidate.structured_data = json.dumps(
            {**rd, "_content_hash": content_hash}, ensure_ascii=False)
        db.commit()
    else:
        candidate = Candidate(
            id=str(uuid.uuid4()),
            name=rd_name,
            structured_data=json.dumps(
                {**rd, "_content_hash": content_hash}, ensure_ascii=False),
        )
        db.add(candidate)
        db.commit()
    db.refresh(candidate)

    skills_raw = rd.get("skills", [])
    skills_text = " ".join(s["name"] if isinstance(s, dict) else str(s) for s in skills_raw)
    work_list = rd.get("work_experience", [])
    work_text = " ".join(f"{w.get('title','')} {w.get('company','')}" for w in work_list if isinstance(w, dict))
    edu_list = rd.get("education", [])
    edu_text = " ".join(f"{e.get('degree','')} {e.get('major','')} {e.get('school','')}" for e in edu_list if isinstance(e, dict))

    full_text = f"{skills_text} {work_text} {edu_text}"
    if not full_text.strip():
        # 降级：用原始文本作为索引内容
        full_text = cleaned_text[:2000]
    if not full_text.strip():
        print(f"[UPLOAD-ERR] 简历内容为空 [{file.filename}]", flush=True)
        raise HTTPException(status_code=422, detail="简历内容为空，无法生成索引")

    emb = embedding_service.embed_query(full_text)
    chroma_store.add_candidate(
        candidate_id=candidate.id, document=full_text[:2000],
        metadata={"name": rd_name, "skills": skills_text, "years": rd.get("years_of_experience", 0)},
        embedding=emb,
    )
    candidate.chroma_doc_id = candidate.id
    db.commit()

    return _candidate_to_read(candidate)


@router.get("/", response_model=PaginatedResponse[CandidateRead])
async def list_candidates(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
):
    """获取所有已上传的候选人列表，支持分页。

    Args:
        page: 当前页码
        page_size: 每页条数
        db: 数据库会话

    Returns:
        分页的候选人列表
    """
    query = db.query(Candidate).order_by(desc(Candidate.created_at))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedResponse[CandidateRead](
        items=[_candidate_to_read(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/{candidate_id}", response_model=CandidateRead)
async def get_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """根据 ID 获取单个候选人详情，包含完整的结构化数据。

    Args:
        candidate_id: 候选人 ID
        db: 数据库会话

    Returns:
        候选人完整信息

    Raises:
        HTTPException 404: 候选人不存在
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return _candidate_to_read(candidate)


@router.delete("/{candidate_id}", response_model=MessageResponse)
async def delete_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """删除候选人记录及其关联的 Chroma 向量数据。

    Args:
        candidate_id: 候选人 ID
        db: 数据库会话

    Returns:
        操作结果消息

    Raises:
        HTTPException 404: 候选人不存在
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")

    # 如果存在 Chroma 文档 ID，同步删除向量库中的数据
    if candidate.chroma_doc_id:
        try:
            from services.chroma_store import chroma_store
            chroma_store.delete_candidate(candidate.chroma_doc_id)
        except Exception:
            pass  # API 层对 Chroma 删除采用尽力而为策略

    db.delete(candidate)
    db.commit()
    return MessageResponse(message=f"候选人 {candidate_id} 已删除")
