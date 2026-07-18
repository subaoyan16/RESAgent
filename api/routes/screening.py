"""
筛选任务管理 API — LangGraph 多 Agent 管道：Job Analyzer → RAG 检索 → 匹配 → 偏差检测
"""
import asyncio, json, uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.base import get_db, SessionLocal
from models.job import Job
from models.candidate import Candidate
from models.screening_task import ScreeningTask
from models.match_result import MatchResult
from models.bias_report import BiasReport
from api.schemas.screening import (
    ScreeningTaskCreate, ScreeningTaskRead, MatchResultRead,
    MatchDetailSchema, GapSchema, TransferableSkillSchema,
)
from api.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()

_event_queues: dict[str, asyncio.Queue] = {}
_running_tasks: dict[str, asyncio.Task] = {}


def _task_to_read(task: ScreeningTask, db: Session) -> ScreeningTaskRead:
    """将 ScreeningTask ORM 实例转换为 ScreeningTaskRead 响应模型。

    Args:
        task: 筛选任务 ORM 实例
        db: 数据库会话（用于查询关联的职位名称）

    Returns:
        ScreeningTaskRead Pydantic 模型
    """
    job = db.query(Job).filter(Job.id == task.job_id).first()
    return ScreeningTaskRead(
        id=uuid.UUID(task.id), job_id=uuid.UUID(task.job_id),
        job_title=job.title if job else "未知岗位", status=task.status,
        total_candidates=task.total_candidates or 0,
        processed_candidates=task.processed_candidates,
        created_at=datetime.fromisoformat(task.created_at) if task.created_at else datetime.now(timezone.utc),
        completed_at=datetime.fromisoformat(task.completed_at) if task.completed_at else None,
    )


def _publish(queue: asyncio.Queue, event: dict):
    """向 SSE 事件队列发布事件（非阻塞）。

    Args:
        queue: 异步事件队列，用于 SSE 流式推送
        event: 要发布的事件字典
    """
    try: queue.put_nowait(event)
    except: pass


def _make_event(event_type: str, **kwargs) -> dict:
    """构建带有时间戳的标准化 SSE 事件字典。

    Args:
        event_type: 事件类型标识（如 workflow_start、node_update、workflow_complete）
        **kwargs: 事件附带的额外数据

    Returns:
        包含 event、timestamp 和其他字段的字典
    """
    return {"event": event_type, "timestamp": datetime.now(timezone.utc).isoformat(), **kwargs}


def _update_task_status(db: Session, task_id: str, status: str):
    """更新筛选任务的状态字段。

    当状态变更为 completed 或 failed 时，自动记录完成时间。

    Args:
        db: 数据库会话
        task_id: 筛选任务 ID
        status: 新状态（pending / running / completed / failed）
    """
    task = db.query(ScreeningTask).filter(ScreeningTask.id == task_id).first()
    if task:
        task.status = status
        if status in ("completed", "failed"):
            task.completed_at = datetime.now(timezone.utc).isoformat()
        db.commit()


async def _execute_screening_graph(task_id: str, job: Job, candidate_ids: list[str]):
    """后台运行 LangGraph 4 节点管线：job_analyzer → retriever → matcher → bias_detector。

    通过 contextvars 注入 SSE 队列，图中各节点自动推送进度。
    """
    from agent_orchestration.state import (
        ScreeningState, _event_queue_ctx, publish_event,
    )
    from agent_orchestration.graph import screening_graph

    queue = _event_queues.get(task_id)
    db = SessionLocal()
    total_count = len(candidate_ids)
    token = None

    try:
        token = _event_queue_ctx.set(queue)
        publish_event("workflow_start", task_id=task_id, status="running", total=total_count)
        _update_task_status(db, task_id, status="running")

        initial_state: ScreeningState = {
            "task_id": task_id, "job_id": job.id, "status": "running",
            "resume_files": [], "job_description": job.description or "",
            "candidate_ids": candidate_ids, "top_k": 5,
            "parsing_errors": [], "analysis_errors": [], "match_errors": [],
            "bias_errors": [], "report_errors": [],
            "needs_human_review": False, "skip_bias_detection": False,
            "ranked_candidates": [], "retrieval_metrics": {}, "match_results": [],
        }

        config = {"configurable": {"thread_id": task_id}}
        final_state = await screening_graph.ainvoke(initial_state, config)

        if final_state.get("status") == "failed":
            raise RuntimeError(final_state.get("error_message", "管线执行失败"))

        _update_task_status(db, task_id, status="completed")

        matches = db.query(MatchResult).filter(MatchResult.task_id == task_id).all()
        cdata = []
        for m in matches:
            c = db.query(Candidate).filter(Candidate.id == m.candidate_id).first()
            cdata.append({
                "id": m.candidate_id, "name": c.name if c else "未知",
                "overall_score": m.overall_score, "recommendation": m.recommendation,
            })

        metrics = final_state.get("retrieval_metrics", {})
        ranked = final_state.get("ranked_candidates", [])
        _publish(queue, _make_event(
            "workflow_complete", task_id=task_id, status="completed",
            candidates=cdata,
            message=f"RAG: BM25({metrics.get('bm25','?')}) "
                    f"+Chroma({metrics.get('chroma','?')}) "
                    f"→混合({metrics.get('hybrid','?')}) "
                    f"→Rerank({metrics.get('rerank_out', len(ranked))}) "
                    f"→匹配{len(matches)}人"))
        _publish(queue, {"event": "__done__"})

    except Exception as exc:
        import traceback
        traceback.print_exc()
        _update_task_status(db, task_id, status="failed")
        _publish(queue, _make_event("workflow_error", task_id=task_id, status="failed", error=str(exc)))
        _publish(queue, {"event": "__done__"})
    finally:
        if token is not None:
            _event_queue_ctx.reset(token)
        db.close()
        _event_queues.pop(task_id, None)
        _running_tasks.pop(task_id, None)

# ═══════════════════════════════════════════════════════════
#  API 路由
# ═══════════════════════════════════════════════════════════

@router.post("/run", response_model=ScreeningTaskRead, status_code=201)
async def run_screening(body: ScreeningTaskCreate, db: Session = Depends(get_db)):
    """启动一次批量筛选任务。

    验证职位和候选人存在后，创建 ScreeningTask 记录并启动后台异步管道
    （_execute_screening_graph），通过 SSE 端点可实时追踪进度。

    Args:
        body: 筛选任务创建请求（包含 job_id 和 resume_ids）
        db: 数据库会话

    Returns:
        新创建的筛选任务信息

    Raises:
        HTTPException 404: 职位不存在
        HTTPException 400: 无有效候选人
    """
    job = db.query(Job).filter(Job.id == str(body.job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="职位不存在")

    candidates = db.query(Candidate).filter(Candidate.id.in_(body.resume_ids)).all()
    if not candidates:
        raise HTTPException(status_code=400, detail="无有效候选人")

    task = ScreeningTask(id=str(uuid.uuid4()), job_id=str(body.job_id), status="pending",
                         total_candidates=len(candidates), processed_candidates=0,
                         config=json.dumps(body.config or {}, ensure_ascii=False))
    db.add(task)
    db.commit()
    db.refresh(task)

    queue: asyncio.Queue = asyncio.Queue()
    _event_queues[task.id] = queue
    bg = asyncio.create_task(_execute_screening_graph(task.id, job, [c.id for c in candidates]))
    _running_tasks[task.id] = bg

    return _task_to_read(task, db)


@router.get("/", response_model=PaginatedResponse[ScreeningTaskRead])
async def list_tasks(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     db: Session = Depends(get_db)):
    query = db.query(ScreeningTask).order_by(desc(ScreeningTask.created_at))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(items=[_task_to_read(t, db) for t in items],
                             total=total, page=page, page_size=page_size,
                             total_pages=max(1, (total + page_size - 1) // page_size))


@router.get("/{task_id}", response_model=ScreeningTaskRead)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScreeningTask).filter(ScreeningTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_to_read(task, db)


@router.get("/{task_id}/results")
async def get_results(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScreeningTask).filter(ScreeningTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    matches = db.query(MatchResult).filter(MatchResult.task_id == task_id).all()
    clist = []
    for m in matches:
        c = db.query(Candidate).filter(Candidate.id == m.candidate_id).first()
        clist.append({
            "candidate_id": m.candidate_id, "name": c.name if c else "未知",
            "overall_score": m.overall_score, "recommendation": m.recommendation,
            "dimension_scores": json.loads(m.dimension_scores) if m.dimension_scores else {},
            "matched_skills": json.loads(m.matched_skills) if m.matched_skills else [],
            "gaps": json.loads(m.gaps) if m.gaps else [],
            "transferable_skills": json.loads(m.transferable_skills) if m.transferable_skills else [],
            "highlights": json.loads(m.highlights) if m.highlights else [],
            "risks": json.loads(m.risks) if m.risks else [],
            "match_rationale": m.match_rationale,
        })
    bias = db.query(BiasReport).filter(BiasReport.task_id == task_id).first()
    bias_data = None
    if bias:
        bias_data = {"fairness_score": bias.fairness_score,
                     "flags": json.loads(bias.flags) if bias.flags else [],
                     "distribution_analysis": json.loads(bias.distribution_analysis) if bias.distribution_analysis else {}}
    return {"task_id": task_id, "status": task.status, "job_title": "",
            "total_candidates": task.total_candidates, "candidates": clist, "bias_report": bias_data}


@router.get("/{task_id}/stream")
async def stream(task_id: str):
    """SSE 端点：实时推送筛选任务的执行进度。

    使用 Server-Sent Events 协议，前端通过 EventSource 连接后可持续接收
    工作流各阶段的进度更新事件（node_update、candidate_start、candidate_done 等），
    以及最终的 workflow_complete 或 workflow_error 事件。

    Args:
        task_id: 筛选任务 ID

    Returns:
        StreamingResponse，media_type 为 text/event-stream
    """
    queue = _event_queues.get(task_id)
    if not queue:
        async def empty():
            yield f"data: {json.dumps({'error': 'no queue'})}\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    async def gen():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("event") == "__done__":
                    break
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'event':'heartbeat'})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.delete("/{task_id}", response_model=MessageResponse)
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScreeningTask).filter(ScreeningTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.query(MatchResult).filter(MatchResult.task_id == task_id).delete()
    db.query(BiasReport).filter(BiasReport.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return MessageResponse(message=f"任务 {task_id} 已删除")


@router.post("/{task_id}/approve", response_model=MessageResponse)
async def approve(task_id: str, db: Session = Depends(get_db)):
    """人工确认筛选结果。

    用于 Human-in-the-Loop 流程中审批偏差检测后的筛选结果。
    当前为占位端点，后续将实现完整的审批工作流（如重新评分、忽略偏差标记等）。

    Args:
        task_id: 筛选任务 ID
        db: 数据库会话

    Returns:
        确认消息
    """
    return MessageResponse(message="已确认")
