"""LangGraph 筛选工作流：Job Analyzer → RAG 检索 → 匹配 → 偏差检测。

四个节点线性执行：
  job_analyzer  — LLM 分析岗位需求
  retriever     — BM25 + Chroma 混合召回 → BGE-Reranker 精排 → LLM 排序
  matcher       — Top-K 候选人逐一 LLM 深度匹配
  bias_detector — 批量 LLM 偏见审计

每个节点通过 agent_orchestration.state.publish_event() 推送 SSE 进度事件。
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langgraph.graph import StateGraph, END

from .state import ScreeningState, publish_event

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  Node 1: Job Analyzer
# ═══════════════════════════════════════════════════════════════════

async def job_analyzer_node(state: ScreeningState) -> dict:
    """LLM 分析 JD → 提取硬性要求 + 评分权重。"""
    from agents.job_analyzer.agent import run as job_analyzer_run

    publish_event("node_update", node="job_analyzer", status="running",
                  message="LLM 分析岗位需求")

    result = await job_analyzer_run(state)
    job_req = result.get("job_requirements", {})
    if not job_req.get("hard"):
        job_req["hard"] = []
    if not job_req.get("scoring_weights"):
        job_req["scoring_weights"] = {
            "skill_match": 0.45, "experience_relevance": 0.25,
            "education": 0.10, "career_trajectory": 0.10, "other": 0.10,
        }

    publish_event("node_update", node="job_analyzer", status="completed",
                  message="岗位分析完成")
    return {
        "job_requirements": job_req,
        "status": result.get("status", "running"),
    }


# ═══════════════════════════════════════════════════════════════════
#  Node 2: Retriever — BM25 + Chroma + Reranker + LLM 排序
# ═══════════════════════════════════════════════════════════════════

async def retriever_node(state: ScreeningState) -> dict:
    """多阶段检索：BM25 关键词 + Chroma 向量 → 混合融合 → Reranker 精排 → LLM 排序。"""
    from models.base import SessionLocal
    from models.candidate import Candidate
    from models.job import Job
    from services.chroma_store import chroma_store
    from services.embedding import embedding_service
    from agent_orchestration.tools.bm25 import BM25Retriever
    from services.llm_pool import llm_pool as lp

    job_req = state.get("job_requirements", {})
    job_description = state.get("job_description", "")

    # 获取职位标题
    db = SessionLocal()
    try:
        job_obj = db.query(Job).filter(Job.id == state.get("job_id", "")).first()
        job_title = job_obj.title if job_obj else ""
    finally:
        db.close()

    publish_event("node_update", node="retriever", status="running",
                  message="BM25 + 向量混合检索")

    # ── 2a: 加载候选人 + 构建 BM25 ──
    db = SessionLocal()
    try:
        all_candidates = db.query(Candidate).all()
    finally:
        db.close()

    bm25 = BM25Retriever()
    for c in all_candidates:
        sd = json.loads(c.structured_data) if c.structured_data else {}
        skills_text = " ".join(s.get("name", "") for s in sd.get("skills", []))
        exp_text = " ".join(
            f"{e.get('title','')} {e.get('company','')} "
            f"{' '.join(e.get('tech_stack', []))}"
            for e in sd.get("work_experience", [])
        )
        bm25_text = f"{c.name or ''} {sd.get('location', '')} {skills_text} {exp_text}"
        bm25.add_document(c.id, bm25_text, {"name": c.name or "未知"})

    skill_names = [r.get("skill", "") for r in job_req.get("hard", [])]
    query_text = f"{job_title} {job_description} {' '.join(skill_names)}"[:2000]

    bm25.build()
    bm25_results = bm25.search(query_text, top_k=20)
    publish_event("node_update", node="retriever", status="running",
                  message=f"BM25 召回 {len(bm25_results)} 人")

    # ── 2b: Chroma 向量检索 ──
    query_emb = embedding_service.embed_query(query_text)
    chroma_raw = chroma_store.search_candidates(query_embedding=query_emb, top_k=20)
    publish_event("node_update", node="retriever", status="running",
                  message=f"Chroma 召回 {len(chroma_raw)} 人")

    # ── 2c: 混合融合 (BM25 0.4 + 向量 0.6) ──
    candidate_scores: dict[str, dict] = {}
    max_b = max((r["score"] for r in bm25_results), default=1)
    for r in bm25_results:
        cid = r["id"]
        candidate_scores[cid] = {
            "bm25": r["score"] / max(max_b, 0.001), "vector": 0,
            "name": r["metadata"].get("name", "未知"),
        }
    for cr in chroma_raw:
        cid = cr.get("id", "")
        meta = cr.get("metadata", {})
        vec_score = 1 - cr.get("distance", 0)
        name = meta.get("name", "未知") if isinstance(meta, dict) else "未知"
        if cid not in candidate_scores:
            candidate_scores[cid] = {"bm25": 0, "vector": 0, "name": name}
        candidate_scores[cid]["vector"] = max(
            candidate_scores[cid]["vector"], vec_score)

    for cid, scores in candidate_scores.items():
        scores["final"] = scores["bm25"] * 0.4 + scores["vector"] * 0.6

    ranked = sorted(candidate_scores.items(),
                    key=lambda x: x[1]["final"], reverse=True)
    top_k_hybrid = min(10, len(ranked))
    hybrid_results = []
    for cid, scores in ranked[:top_k_hybrid]:
        hybrid_results.append({
            "id": cid,
            "distance": 1 - scores["final"],
            "metadata": {"name": scores["name"],
                         "bm25": round(scores["bm25"], 3),
                         "vector": round(scores["vector"], 3)},
        })

    if not hybrid_results:
        raise RuntimeError("混合检索未召回任何候选人——请确认简历已上传并成功索引")

    retrieval_metrics = {
        "bm25": len(bm25_results),
        "chroma": len(chroma_raw),
        "hybrid": len(hybrid_results),
    }

    # ── 2d: BGE-Reranker 精排 ──
    candidate_texts: dict[str, str] = {}
    db = SessionLocal()
    try:
        for c in db.query(Candidate).all():
            sd = json.loads(c.structured_data) if c.structured_data else {}
            skills = " ".join(s.get("name", "") for s in sd.get("skills", []))
            exp = " ".join(
                f"{e.get('title','')} {e.get('company','')} "
                f"{' '.join(e.get('responsibilities', [])[:2])}"
                for e in sd.get("work_experience", [])[:3]
            )
            candidate_texts[c.id] = f"{c.name or ''} {skills} {exp} {sd.get('location', '')}"
    finally:
        db.close()

    rerank_ids = []
    rerank_docs = []
    for hr in hybrid_results[:20]:
        cid = hr["id"]
        rerank_ids.append(cid)
        rerank_docs.append(candidate_texts.get(cid, hr["metadata"].get("name", "未知")))

    chroma_results = hybrid_results  # default: 无 reranker 时用混合结果
    if rerank_docs:
        from services.local_ml import get_local_ml
        ml = get_local_ml()
        reranked = ml.rerank(query_text, rerank_docs, top_k=min(10, len(rerank_docs)))
        chroma_results = []
        for rr in reranked:
            cid = rerank_ids[rr["index"]]
            chroma_results.append({
                "id": cid,
                "distance": 1 - rr["score"],
                "metadata": {
                    "name": candidate_texts.get(cid, cid)[:80],
                    "rerank_score": round(rr["score"], 3),
                },
            })
        retrieval_metrics["rerank_in"] = len(rerank_docs)
        retrieval_metrics["rerank_out"] = len(chroma_results)
        retrieval_metrics["reranker"] = "BGE-Reranker-v2-m3" if ml.is_available() else "passthrough"

    publish_event("node_update", node="retriever", status="running",
                  message=f"精排完成: {len(chroma_results)} 人 (BM25→{len(bm25_results)} "
                          f"Chroma→{len(chroma_raw)} Rerank→{len(chroma_results)})",
                  metrics=retrieval_metrics)

    # ── 2e: LLM 排序 ──
    publish_event("node_update", node="retriever", status="running",
                  message="LLM 排序评估")

    # 构建带 ID 的候选行，LLM 直接返回 ID（无需模糊名字匹配）
    id_to_info: dict[str, dict] = {}
    candidate_lines: list[str] = []
    for i, cr in enumerate(chroma_results[:10]):
        cid = cr.get("id", "")
        meta = cr.get("metadata", {}) if isinstance(cr.get("metadata"), dict) else {}
        full_text = meta.get("name", "未知")
        short_name = full_text.split(" ")[0] if " " in full_text else full_text
        dist = cr.get("distance", 1.0)
        candidate_lines.append(f"[{i}] id={cid} | {short_name} | 匹配分: {1-dist:.1%}")
        id_to_info[cid] = {"name": short_name, "distance": dist}

    jd_json = json.dumps(job_req, ensure_ascii=False)[:2000]
    rag_prompt = (
        "你是资深HR。根据岗位需求对候选人排序，输出JSON。"
        "必须原样返回候选人 id，不要修改。\n"
        f"岗位需求:\n{jd_json}\n\n候选人:\n" + "\n".join(candidate_lines) + "\n\n"
        '{"rankings":[{"id":"候选人id","name":"候选人姓名","score":0.92,"reason":"理由"}]}'
    )

    llm_resp = await lp.chat(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": rag_prompt}],
        thinking=False, max_tokens=8192,
    )
    if not llm_resp or not llm_resp.strip():
        raise RuntimeError("LLM 排序返回空响应")

    # 解析 LLM 排序结果
    try:
        llm_result = json.loads(llm_resp.strip())
    except json.JSONDecodeError:
        # 容错：处理 markdown 包裹
        text = llm_resp.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        llm_result = json.loads(text.strip())

    rankings = llm_result.get("rankings", [])
    if not rankings:
        raise RuntimeError("LLM 排序返回空结果")

    # 按 ID + 基础名 双重去重构建最终列表
    ranked_candidates: list[dict] = []
    seen_ids: set[str] = set()
    seen_base_names: set[str] = set()
    for r in rankings[:10]:
        cid = r.get("id", "")
        name = r.get("name", "")
        score = r.get("score", 0.5)
        reason = r.get("reason", "")

        # LLM 没返回 id 时，从 name 回退匹配
        if not cid:
            for _cid, info in id_to_info.items():
                if info["name"] == name:
                    cid = _cid
                    break

        # ID 去重
        if cid and cid in seen_ids:
            logger.info("LLM排序去重(ID): 跳过 %s (%s)", name, cid[:12])
            continue

        # 基础名去重：提取 "xxx - 张三" 中的 "张三" 部分
        base = name.split(" - ")[-1].strip() if " - " in name else name.strip()
        if base and base in seen_base_names:
            logger.info("LLM排序去重(name): 跳过 %s (base=%s)", name, base)
            continue

        if cid:
            seen_ids.add(cid)
        if base:
            seen_base_names.add(base)

        ranked_candidates.append({
            "id": cid,
            "name": name,
            "score": score,
            "reason": reason,
        })

    publish_event("node_update", node="retriever", status="completed",
                  message=f"LLM 排序完成: {len(ranked_candidates)} 人")

    return {
        "ranked_candidates": ranked_candidates,
        "retrieval_metrics": retrieval_metrics,
        "status": "running",
    }


# ═══════════════════════════════════════════════════════════════════
#  Node 3: Matcher — Top-K 逐一 LLM 深度匹配
# ═══════════════════════════════════════════════════════════════════

def _save_match_result(
    task_id: str, candidate_id: str, job_id: str, overall_score: float,
    recommendation: str, dimension_scores: dict, matched_skills: list,
    gaps: list, transferable_skills: list, highlights: list, risks: list,
    match_rationale: str,
) -> None:
    """持久化单条匹配结果到 SQLite。"""
    from models.base import SessionLocal
    from models.match_result import MatchResult
    from models.screening_task import ScreeningTask

    db = SessionLocal()
    try:
        db.add(MatchResult(
            id=str(uuid.uuid4()), task_id=task_id, candidate_id=candidate_id,
            job_id=job_id, overall_score=overall_score, recommendation=recommendation,
            dimension_scores=json.dumps(dimension_scores, ensure_ascii=False),
            matched_skills=json.dumps(matched_skills, ensure_ascii=False),
            gaps=json.dumps(gaps, ensure_ascii=False),
            transferable_skills=json.dumps(transferable_skills, ensure_ascii=False),
            highlights=json.dumps(highlights, ensure_ascii=False),
            risks=json.dumps(risks, ensure_ascii=False),
            match_rationale=match_rationale,
        ))
        db.commit()
        match_count = db.query(MatchResult).filter(MatchResult.task_id == task_id).count()
        db.query(ScreeningTask).filter(ScreeningTask.id == task_id).update(
            {"processed_candidates": match_count})
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def matcher_node(state: ScreeningState) -> dict:
    """对 Top-K 候选人逐一调用 Matcher Agent 做深度匹配。"""
    from agents.matcher.agent import run as matcher_run
    from models.base import SessionLocal
    from models.candidate import Candidate

    ranked = state.get("ranked_candidates", [])
    job_req = state.get("job_requirements", {})
    job_description = state.get("job_description", "")
    task_id = state.get("task_id", "")
    job_id = state.get("job_id", "")
    top_k = state.get("top_k", 5)

    # 去重
    deduped: list[dict] = []
    seen: set[str] = set()
    for rc in ranked:
        cid = rc.get("id", "")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        deduped.append(rc)
    ranked = deduped

    effective = min(top_k, len(ranked))
    if effective == 0:
        publish_event("node_update", node="matcher", status="completed",
                      message="无候选人需要匹配")
        return {"match_results": [], "status": "running"}

    publish_event("node_update", node="matcher", status="running",
                  message=f"深度匹配 {effective} 位候选人")

    # 加载候选人数据
    db = SessionLocal()
    try:
        candidates_map = {c.id: c for c in db.query(Candidate).all()}
    finally:
        db.close()

    match_results: list[dict] = []

    for idx, rc in enumerate(ranked[:effective]):
        cid = rc["id"]
        name = rc.get("name", "未知")
        llm_score = rc.get("score", 0.7)
        reason = rc.get("reason", "")

        candidate = candidates_map.get(cid)
        if not candidate:
            logger.warning("Matcher: 候选人 %s (%s) 在 SQLite 中不存在，可能已被删除，跳过", name, cid[:12])
            continue

        publish_event("node_update", node="matcher", status="running",
                      message=f"匹配 {idx+1}/{effective}: {name}")

        sd = json.loads(candidate.structured_data) if candidate.structured_data else {}

        match_state: ScreeningState = {
            "task_id": task_id, "job_id": job_id, "status": "running",
            "resume_data": sd, "job_description": job_description,
            "job_requirements": job_req,
            "resume_files": [], "candidate_ids": [], "top_k": top_k,
            "ranked_candidates": [], "retrieval_metrics": {},
            "match_results": [], "parsing_errors": [], "analysis_errors": [],
            "match_errors": [], "bias_errors": [], "report_errors": [],
            "needs_human_review": False, "skip_bias_detection": False,
        }

        m_result = await matcher_run(match_state)  # type: ignore[arg-type]
        mr = m_result.get("match_result", {})

        if m_result.get("status") == "failed" or not mr:
            raise RuntimeError(f"Matcher 失败 [{name}]: {m_result.get('match_errors', ['未知错误'])}")

        # 以 Matcher Agent 深度匹配分作为最终综合评分（0-1 → 0-100）
        matcher_score = mr.get("overall_match_score", llm_score)
        overall_score = round(matcher_score * 100, 1)
        recommendation = (
            "strong_hire" if overall_score >= 85
            else "recommend" if overall_score >= 70
            else "hold"
        )
        match_entry = {
            "candidate_id": cid, "name": name,
            "overall_score": overall_score,
            "recommendation": recommendation,
            "dimension_scores": mr.get("dimension_scores", {}),
            "matched_skills": mr.get("matched_skills", []),
            "gaps": mr.get("gaps", []),
            "transferable_skills": mr.get("transferable_skills", []),
            "highlights": mr.get("highlights", []),
            "risks": mr.get("risks", []),
            "match_rationale": reason or mr.get("match_rationale", ""),
        }
        match_results.append(match_entry)

        _save_match_result(
            task_id=task_id, candidate_id=cid, job_id=job_id,
            overall_score=overall_score, recommendation=recommendation,
            dimension_scores=mr.get("dimension_scores", {}),
            matched_skills=mr.get("matched_skills", []),
            gaps=mr.get("gaps", []),
            transferable_skills=mr.get("transferable_skills", []),
            highlights=mr.get("highlights", []),
            risks=mr.get("risks", []),
            match_rationale=reason or mr.get("match_rationale", ""),
        )

    publish_event("node_update", node="matcher", status="completed",
                  message=f"深度匹配完成: {len(match_results)} 人")
    return {"match_results": match_results, "status": "running"}


# ═══════════════════════════════════════════════════════════════════
#  Node 4: Bias Detector — 批量偏见检测
# ═══════════════════════════════════════════════════════════════════

async def bias_detector_node(state: ScreeningState) -> dict:
    """收集全部匹配结果，调用偏差检测 Agent 进行批量公平性审计。"""
    from agents.bias_detector.agent import run as bias_run
    from models.base import SessionLocal
    from models.bias_report import BiasReport
    from models.job import Job

    match_results = state.get("match_results", [])
    if not match_results:
        publish_event("node_update", node="bias_detector", status="completed",
                      message="无匹配结果，跳过偏见检测")
        return {"status": "running", "needs_human_review": False}

    publish_event("node_update", node="bias_detector", status="running",
                  message="LLM 偏见检测分析中")

    # 获取岗位名称用于上下文
    db = SessionLocal()
    try:
        job_obj = db.query(Job).filter(Job.id == state.get("job_id", "")).first()
        job_title = job_obj.title if job_obj else ""
    finally:
        db.close()

    # 调用偏差检测 Agent（Pro + thinking 模式，5 维度审计）
    result = await bias_run(match_results, job_title=job_title)

    if result.get("status") == "failed":
        errs = result.get("bias_errors", ["未知错误"])
        publish_event("node_update", node="bias_detector", status="completed",
                      message=f"偏差检测失败: {errs[0][:80]}")
        return {"bias_errors": errs, "status": "running", "needs_human_review": False}

    bias_report = result["bias_report"]
    needs_review = result.get("needs_human_review", False)

    # 持久化偏差报告
    db2 = SessionLocal()
    try:
        db2.add(BiasReport(
            id=str(uuid.uuid4()), task_id=state.get("task_id", ""),
            fairness_score=bias_report.get("overall_fairness_score", 1.0),
            flags=json.dumps(bias_report.get("flags", []), ensure_ascii=False),
            distribution_analysis=json.dumps(
                bias_report.get("distribution_analysis", {}), ensure_ascii=False),
        ))
        db2.commit()
    finally:
        db2.close()

    flag_count = len(bias_report.get("flags", []))
    publish_event("node_update", node="bias_detector", status="completed",
                  message=f"偏见检测完成: 发现 {flag_count} 个标记")

    return {
        "bias_report": bias_report,
        "needs_human_review": needs_review,
        "status": "running",
    }


# ═══════════════════════════════════════════════════════════════════
#  Graph 构建
# ═══════════════════════════════════════════════════════════════════

def build_screening_graph() -> StateGraph:
    """构建 4 节点 LangGraph 管线：job_analyzer → retriever → matcher → bias_detector。"""
    workflow = StateGraph(ScreeningState)

    workflow.add_node("job_analyzer", job_analyzer_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("matcher", matcher_node)
    workflow.add_node("bias_detector", bias_detector_node)

    workflow.set_entry_point("job_analyzer")
    workflow.add_edge("job_analyzer", "retriever")
    workflow.add_edge("retriever", "matcher")
    workflow.add_edge("matcher", "bias_detector")
    workflow.add_edge("bias_detector", END)

    from langgraph.checkpoint.memory import MemorySaver
    return workflow.compile(checkpointer=MemorySaver())


screening_graph = build_screening_graph()
