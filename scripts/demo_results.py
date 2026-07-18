"""演示结果注入脚本：为已完成的筛选任务注入模拟匹配结果和偏差报告。

用途:
  - 前端仪表盘演示数据的快速生成
  - Pipeline 兜底方案 — 当完整的 RAG/LLM 管道尚未执行时提供示例数据
  - 开发和测试阶段快速验证报告展示功能

用法:
  python scripts/demo_results.py          # 为最新的任务和最近 2 个候选人注入演示数据
  python -c "from scripts.demo_results import inject_demo_results; ..."  # 编程式调用
"""
import sys, os, json, uuid, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.match_result import MatchResult
from models.bias_report import BiasReport


def inject_demo_results(db, task_id: str, candidate_id: str, job_id: str):
    """为单个候选人注入演示匹配结果和偏差报告。

    生成随机评分（0.65-0.92），构建包含维度评分、技能匹配详情、
    能力差距、亮点和风险点的完整 MatchResult 记录。
    同时为该任务创建一份演示偏差报告（若尚不存在）。

    Args:
        db: SQLAlchemy 数据库会话
        task_id: 筛选任务 ID
        candidate_id: 候选人 ID
        job_id: 职位 ID
    """
    score = round(random.uniform(0.65, 0.92), 2)
    rec = "strong_hire" if score >= 0.85 else "recommend" if score >= 0.70 else "hold"

    match = MatchResult(
        id=str(uuid.uuid4()),
        task_id=task_id,
        candidate_id=candidate_id,
        job_id=job_id,
        overall_score=score,
        recommendation=rec,
        dimension_scores=json.dumps({
            "skill_match": round(score + random.uniform(-0.05, 0.1), 2),
            "experience_relevance": round(score + random.uniform(-0.1, 0.05), 2),
            "education": round(random.uniform(0.7, 0.95), 2),
            "career_trajectory": round(random.uniform(0.6, 0.9), 2),
        }, ensure_ascii=False),
        matched_skills=json.dumps([
            {"skill": "Python", "requirement_level": "expert", "candidate_level": "expert", "match": 0.95},
            {"skill": "系统设计", "requirement_level": "intermediate", "candidate_level": "intermediate", "match": 0.85},
        ], ensure_ascii=False),
        gaps=json.dumps([
            {"skill": "Kubernetes", "importance": "nice_to_have", "gap_severity": "low"},
        ], ensure_ascii=False),
        transferable_skills=json.dumps([], ensure_ascii=False),
        highlights=json.dumps(["技能匹配度高", "经验丰富"], ensure_ascii=False),
        risks=json.dumps(["行业背景需补强"], ensure_ascii=False),
        match_rationale="基于 AI 多维度评估自动生成。候选人核心技能匹配良好，建议进入面试环节。",
    )
    db.add(match)

    existing = db.query(BiasReport).filter(BiasReport.task_id == task_id).first()
    if not existing:
        bias = BiasReport(
            id=str(uuid.uuid4()),
            task_id=task_id,
            fairness_score=0.90,
            flags=json.dumps([], ensure_ascii=False),
            distribution_analysis=json.dumps({"note": "基于演示数据，仅供参考"}, ensure_ascii=False),
        )
        db.add(bias)

    db.commit()


if __name__ == "__main__":
    from models.base import SessionLocal
    from models.screening_task import ScreeningTask
    from models.candidate import Candidate

    db = SessionLocal()
    task = db.query(ScreeningTask).order_by(ScreeningTask.created_at.desc()).first()
    candidates = db.query(Candidate).order_by(Candidate.created_at.desc()).limit(2).all()

    if task and candidates:
        db.query(MatchResult).filter(MatchResult.task_id == task.id).delete()
        db.query(BiasReport).filter(BiasReport.task_id == task.id).delete()
        for c in candidates:
            inject_demo_results(db, task.id, c.id, task.job_id)
        task.status = "completed"
        task.processed_candidates = len(candidates)
        db.commit()
        print(f"Done: {len(candidates)} candidates for task {task.id[:8]}...")
    else:
        print("No task or candidates found")

    db.close()
