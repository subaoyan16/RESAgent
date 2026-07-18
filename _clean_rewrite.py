"""简化管道重写脚本：将逐候选人 LLM 评估管道注入 screening.py。

该脚本读取 api/routes/screening.py，将其 _execute_screening_graph 函数体
替换为简化的两阶段管道：

  Phase 1 — 批量解析：对每份简历执行 Parser Agent（LLM 结构化提取）
  Phase 2 — LLM 语义匹配：对每位候选人逐一执行 Job Analyzer → Matcher →
            Bias Detector → Report Generator 完整 5-Agent 管道

与 _rag_rewrite.py 的区别：本脚本不包含 BM25 关键词索引和向量混合检索，
而是对每位候选人直接调用 LLM 进行深度语义匹配，适用于候选人数量较少（<10）的场景。

用法:
  python _clean_rewrite.py    # 直接执行，将简化管道注入 screening.py
"""
with open('d:/resagent/api/routes/screening.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '        #  延迟导入'
end_marker = '\n    except Exception as exc:'

start_pos = content.find(start_marker)
end_pos = content.find(end_marker)

if start_pos == -1 or end_pos == -1:
    print(f'ERROR: start={start_pos}, end={end_pos}')
    exit(1)

clean_code = '''        # 延迟导入
        from agents.parser.agent import run as parser_run
        from agents.job_analyzer.agent import run as job_analyzer_run
        from agents.matcher.agent import run as matcher_run
        from agents.bias_detector.agent import run as bias_run
        from agents.report_generator.agent import run as report_run
        from agent_orchestration.state import ScreeningState

        candidate_ids = [c.id for c in candidates]
        fresh_candidates = db.query(Candidate).filter(Candidate.id.in_(candidate_ids)).all()

        # ═══════════════════════════════════════════════════════════
        #  Phase 1: 批量解析简历
        # ═══════════════════════════════════════════════════════════
        _publish(queue, _make_event("node_update", node="parser", status="running",
                                    message=f"Phase 1: 解析 {len(fresh_candidates)} 份简历"))

        all_resume_data = []

        for idx, candidate in enumerate(fresh_candidates, start=1):
            file_path = _write_candidate_temp_file(candidate, db)
            if not file_path:
                _publish(queue, _make_event("node_update", node="parser", candidate_id=candidate.id,
                           status="skipped", message=f"跳过 (无文本) ({idx}/{len(fresh_candidates)})"))
                continue

            _publish(queue, _make_event("node_update", node="parser", candidate_id=candidate.id,
                       status="running", message=f"LLM 解析 {idx}/{len(fresh_candidates)}"))

            parse_state = ScreeningState(task_id=task_id, job_id=job.id, status="running",
                                         resume_files=[file_path], job_description=job.description or "")
            try:
                pr = await parser_run(parse_state)
                rd = pr.get("resume_data")
                if rd:
                    name = rd.get("name") or (rd.get("basic_info", {}) or {}).get("name", "未知")
                    all_resume_data.append({"candidate_id": candidate.id, "name": name, "data": rd, "candidate": candidate})
                    _publish(queue, _make_event("node_update", node="parser", candidate_id=candidate.id,
                               status="completed", message=f"已解析: {name}"))
                else:
                    _publish(queue, _make_event("node_update", node="parser", candidate_id=candidate.id,
                               status="skipped", message="解析结果为空"))
            except Exception:
                _publish(queue, _make_event("node_update", node="parser", candidate_id=candidate.id,
                           status="failed", message="解析失败"))

            db.query(ScreeningTask).filter(ScreeningTask.id == task_id).update(
                {"processed_candidates": idx})
            db.commit()

        _publish(queue, _make_event("node_update", node="parser", status="completed",
                 message=f"Phase 1 完成: {len(all_resume_data)}/{len(fresh_candidates)} 份简历解析成功"))

        if not all_resume_data:
            _update_task_status(db, task_id, status="failed")
            _publish(queue, _make_event("workflow_error", task_id=task_id, status="failed",
                       error="所有简历解析失败"))
            _publish(queue, {"event": "__done__"})
            return

        # ═══════════════════════════════════════════════════════════
        #  Phase 2: Job Analyzer + LLM 语义匹配
        # ═══════════════════════════════════════════════════════════
        _publish(queue, _make_event("node_update", node="job_analyzer", status="running",
                                    message="Phase 2: LLM 分析岗位需求..."))

        ja_state = ScreeningState(task_id=task_id, job_id=job.id, status="running",
                                  job_description=job.description or "", resume_files=[])
        ja_result = await job_analyzer_run(ja_state)
        job_requirements = ja_result.get("job_requirements", {})
        if not job_requirements.get("hard"):
            job_requirements["hard"] = []
        if not job_requirements.get("scoring_weights"):
            job_requirements["scoring_weights"] = {"skill_match": 0.45, "experience_relevance": 0.25,
                                                     "education": 0.10, "career_trajectory": 0.10, "other": 0.10}

        _publish(queue, _make_event("node_update", node="job_analyzer", status="completed",
                                    message="岗位分析完成"))

        # 对每位候选人逐一 LLM 深度语义匹配
        _publish(queue, _make_event("node_update", node="matcher", status="running",
                                    message=f"Phase 2: LLM 语义匹配 {len(all_resume_data)} 位候选人..."))

        match_count = 0
        for idx, ac in enumerate(all_resume_data, start=1):
            candidate = ac["candidate"]
            candidate_id = ac["candidate_id"]
            name = ac["name"]

            _publish(queue, _make_event("candidate_start", candidate_id=candidate_id,
                       name=name, index=idx, total=len(all_resume_data)))

            file_path = _write_candidate_temp_file(candidate, db)
            if not file_path:
                continue

            match_state = ScreeningState(task_id=task_id, job_id=job.id, status="running",
                                         resume_files=[file_path], job_description=job.description or "",
                                         job_requirements=job_requirements)
            try:
                # Parser
                p_result = await parser_run(match_state)
                if p_result.get("resume_data"):
                    match_state.update(p_result)

                # Matcher — LLM 深度语义匹配
                m_result = await matcher_run(match_state)
                match_state.update(m_result)
                _publish(queue, _make_event("node_update", node="matcher", candidate_id=candidate_id, status="completed"))

                # Bias Detector
                b_result = await bias_run(match_state)
                match_state.update(b_result)
                _publish(queue, _make_event("node_update", node="bias_detector", candidate_id=candidate_id, status="completed"))

                # Report Generator
                r_result = await report_run(match_state)
                match_state.update(r_result)
                _publish(queue, _make_event("node_update", node="report_generator", candidate_id=candidate_id, status="completed"))

                await _save_graph_results(db, task_id, candidate_id, job.id, match_state)
                match_count += 1
                _publish(queue, _make_event("candidate_done", candidate_id=candidate_id, status="completed",
                           message=f"完成 {name} ({idx}/{len(all_resume_data)})"))

            except Exception as e:
                _publish(queue, _make_event("node_update", node="workflow", candidate_id=candidate_id,
                           status="failed", message=f"匹配失败: {str(e)[:50]}"))

            db.query(ScreeningTask).filter(ScreeningTask.id == task_id).update(
                {"processed_candidates": len(fresh_candidates) + idx})
            db.commit()

        _update_task_status(db, task_id, status="completed")

        matches = db.query(MatchResult).filter(MatchResult.task_id == task_id).all()
        candidates_data = [{"id": m.candidate_id,
                            "name": db.query(Candidate).filter(Candidate.id == m.candidate_id).first().name
                            if db.query(Candidate).filter(Candidate.id == m.candidate_id).first() else "未知",
                            "overall_score": m.overall_score, "recommendation": m.recommendation}
                           for m in matches]

        _publish(queue, _make_event("workflow_complete", task_id=task_id, status="completed",
                 candidates=candidates_data,
                 message=f"LLM 语义匹配: {match_count}/{len(all_resume_data)} 人评估完成"))
        _publish(queue, {"event": "__done__"})
'''

content = content[:start_pos] + clean_code + content[end_pos:]

with open('d:/resagent/api/routes/screening.py', 'w', encoding='utf-8') as f:
    f.write(content)

with open('d:/resagent/api/routes/screening.py', 'r', encoding='utf-8') as f:
    c = f.read()
for ch in ['LLM 语义匹配', 'all_resume_data', 'Phase 1', 'Phase 2', 'job_analyzer_run', 'matcher_run']:
    print(f'  [{("OK" if ch in c else "MISS")}] {ch}')
print(f'Total: {len(c)} chars')
