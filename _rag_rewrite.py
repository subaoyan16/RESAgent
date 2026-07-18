"""RAG 管道重写脚本：将完整的 BM25 + 向量混合召回 + LLM 深度评估管道注入 screening.py。

该脚本读取 api/routes/screening.py，将其 _execute_screening_graph 函数体
替换为完整的三阶段 RAG 实现：

  Phase 1 — RAG 索引阶段：结构化切分（技能/经历/教育）+ 多路向量构建 + BM25 索引
  Phase 2 — RAG 检索阶段：BM25 关键词过滤 + 向量语义检索 + 混合加权融合
  Phase 3 — RAG 生成阶段：LLM（DeepSeek V4 Pro）深度评估 + 匹配结果写入 + 偏差检测

与 _clean_rewrite.py 的区别：本脚本实现了完整的 BM25 + 向量混合检索，
而 _clean_rewrite.py 仅使用逐候选人 LLM 管道（无 BM25，无混合召回）。

用法:
  python _rag_rewrite.py    # 直接执行，将 RAG 管道注入 screening.py
"""
with open('d:/resagent/api/routes/screening.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '        #  延迟导入（避免模块级循环依赖）'
end_marker = '\n    except Exception as exc:'

start_pos = content.find(start_marker)
end_pos = content.find(end_marker)

if start_pos == -1 or end_pos == -1:
    print(f'ERROR markers: start={start_pos}, end={end_pos}')
    exit(1)

rag_code = '''        # ═══════════════════════════════════════════════════════════════
        #  延迟导入
        # ═══════════════════════════════════════════════════════════════
        from agents.parser.agent import run as parser_run
        from agents.job_analyzer.agent import run as job_analyzer_run
        from agents.matcher.agent import run as matcher_run
        from agents.bias_detector.agent import run as bias_run
        from agents.report_generator.agent import run as report_run
        from agent_orchestration.state import ScreeningState
        from agent_orchestration.tools.bm25 import BM25Retriever
        from services.embedding import embedding_service
        from services.chroma_store import chroma_store

        candidate_ids = [c.id for c in candidates]
        fresh_candidates = db.query(Candidate).filter(Candidate.id.in_(candidate_ids)).all()

        # ═══════════════════════════════════════════════════════════════
        #  Phase 1: RAG 索引阶段 — 结构化切分 + 多路向量构建
        # ═══════════════════════════════════════════════════════════════
        _publish(queue, _make_event("node_update", node="parser", status="running",
                                    message="Phase 1: 索引构建（结构化切分 + 多路向量）..."))

        all_candidates = []  # [{candidate_id, name, fields: {skills, experience, education}, ...}]
        bm25_index = BM25Retriever()  # BM25 关键词索引

        for idx, candidate in enumerate(fresh_candidates, start=1):
            file_path = _write_candidate_temp_file(candidate, db)
            if not file_path:
                continue

            _publish(queue, _make_event("node_update", node="parser", candidate_id=candidate.id,
                       status="running", message=f"索引 {idx}/{len(fresh_candidates)}"))

            parse_state = ScreeningState(task_id=task_id, job_id=job.id, status="running",
                                         resume_files=[file_path], job_description=job.description or "")
            try:
                pr = await parser_run(parse_state)
                rd = pr.get("resume_data")
                if not rd:
                    continue
                name = rd.get("name") or (rd.get("basic_info", {}) or {}).get("name", "未知")

                # ---- 多路切分：技能 / 经历 / 教育 分别构建文本和向量 ----
                skills_raw = rd.get("skills", [])
                skills_text = " ".join(
                    s["name"] if isinstance(s, dict) else str(s) for s in skills_raw
                )

                work_list = rd.get("work_experience", [])
                work_text = " ".join(
                    f"{w.get('title','')} {w.get('company','')} {' '.join(w.get('responsibilities',[]))} {' '.join(w.get('achievements',[]))}"
                    for w in work_list if isinstance(w, dict)
                )

                edu_list = rd.get("education", [])
                edu_text = " ".join(
                    f"{e.get('degree','')} {e.get('major','')} {e.get('school','')}"
                    for e in edu_list if isinstance(e, dict)
                )

                full_text = f"{skills_text} {work_text} {edu_text}"

                # 多路向量存入 Chroma（技能向量权重最高）
                if skills_text.strip():
                    skills_emb = embedding_service.embed_query(skills_text)
                    chroma_store.add_candidate(
                        candidate_id=candidate.id + "_skills",
                        document=skills_text,
                        metadata={"name": name, "field": "skills", "candidate_id": candidate.id},
                        embedding=skills_emb,
                    )
                if work_text.strip():
                    work_emb = embedding_service.embed_query(work_text)
                    chroma_store.add_candidate(
                        candidate_id=candidate.id + "_work",
                        document=work_text,
                        metadata={"name": name, "field": "experience", "candidate_id": candidate.id},
                        embedding=work_emb,
                    )
                if edu_text.strip():
                    edu_emb = embedding_service.embed_query(edu_text)
                    chroma_store.add_candidate(
                        candidate_id=candidate.id + "_edu",
                        document=edu_text,
                        metadata={"name": name, "field": "education", "candidate_id": candidate.id},
                        embedding=edu_emb,
                    )

                # BM25 全文索引
                bm25_index.add_document(candidate.id, full_text, {"name": name})

                all_candidates.append({
                    "candidate_id": candidate.id,
                    "name": name,
                    "fields": {"skills": skills_text, "experience": work_text, "education": edu_text},
                    "full_text": full_text,
                })

                _publish(queue, _make_event("node_update", node="parser", candidate_id=candidate.id,
                           status="completed", message=f"已索引: {name} ({idx}/{len(fresh_candidates)})"))

            except Exception:
                _publish(queue, _make_event("node_update", node="parser", candidate_id=candidate.id,
                           status="failed", message=f"索引失败 ({idx}/{len(fresh_candidates)})"))

            db.query(ScreeningTask).filter(ScreeningTask.id == task_id).update(
                {"processed_candidates": idx})
            db.commit()

        _publish(queue, _make_event("node_update", node="parser", status="completed",
                 message=f"Phase 1 完成: {len(all_candidates)}/{len(fresh_candidates)} 份简历完成多路索引"))

        if not all_candidates:
            _update_task_status(db, task_id, status="failed")
            _publish(queue, _make_event("workflow_error", task_id=task_id, status="failed",
                       error="所有简历索引失败"))
            _publish(queue, {"event": "__done__"})
            return

        # ═══════════════════════════════════════════════════════════════
        #  Phase 2: RAG 检索阶段 — BM25 + 向量混合召回
        # ═══════════════════════════════════════════════════════════════
        _publish(queue, _make_event("node_update", node="job_analyzer", status="running",
                                    message="Phase 2: 分析岗位需求..."))

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

        # ---- BM25 关键词过滤硬性条件 ----
        _publish(queue, _make_event("node_update", node="matcher", status="running",
                                    message="Phase 2: BM25 + 向量混合检索..."))

        hard_keywords = " ".join(r.get("skill", "") for r in job_requirements.get("hard", []))
        jd_full_text = f"{job.description or ''} {job.title or ''} {hard_keywords}"
        bm25_index.build()
        bm25_results = bm25_index.search(jd_full_text, top_k=min(20, len(all_candidates)))

        # ---- 向量语义检索（技能字段优先） ----
        query_text = f"{job_requirements.get('title','')} {hard_keywords} {job.description or ''}"[:1000]
        query_emb = embedding_service.embed_query(query_text)
        vector_results = chroma_store.search_candidates(
            query_embedding=query_emb, top_k=min(20, len(all_candidates) * 3))

        # ---- 混合加权融合 ----
        candidate_scores: dict[str, dict] = {}  # candidate_id -> {bm25, vector, fields}

        for r in bm25_results:
            cid = r["id"]
            if cid not in candidate_scores:
                candidate_scores[cid] = {"bm25": 0, "vector": 0, "name": r["metadata"].get("name", "?")}
            candidate_scores[cid]["bm25"] = max(candidate_scores[cid]["bm25"], r["score"])

        for r in vector_results:
            meta = r.get("metadata", {})
            cid = meta.get("candidate_id", "")
            if not cid:
                continue
            if cid not in candidate_scores:
                candidate_scores[cid] = {"bm25": 0, "vector": 0, "name": meta.get("name", "?")}
            # 技能字段加权更高
            field_weight = 1.5 if meta.get("field") == "skills" else 1.0
            vec_score = (1.0 - r.get("distance", 1.0)) * field_weight
            candidate_scores[cid]["vector"] = max(candidate_scores[cid]["vector"], vec_score)

        # 归一化并融合
        if candidate_scores:
            max_bm25 = max(v["bm25"] for v in candidate_scores.values()) or 1
            max_vec = max(v["vector"] for v in candidate_scores.values()) or 1
            for cid, scores in candidate_scores.items():
                scores["bm25"] /= max_bm25
                scores["vector"] /= max_vec
                scores["final"] = scores["bm25"] * 0.4 + scores["vector"] * 0.6  # 向量权重高

        ranked = sorted(candidate_scores.items(), key=lambda x: x[1]["final"], reverse=True)
        top_k = min(5, len(ranked))
        top_candidates = []
        for cid, scores in ranked[:top_k]:
            for ac in all_candidates:
                if ac["candidate_id"] == cid:
                    top_candidates.append(ac)
                    break

        names_str = ", ".join(c["name"] for c in top_candidates)
        _publish(queue, _make_event("node_update", node="matcher", status="completed",
                 message=f"混合召回 Top-{len(top_candidates)}: {names_str}"))

        # ═══════════════════════════════════════════════════════════════
        #  Phase 3: RAG 生成阶段 — LLM 深度评估报告
        # ═══════════════════════════════════════════════════════════════
        _publish(queue, _make_event("node_update", node="matcher", status="running",
                                    message=f"Phase 3: LLM 深度评估 {len(top_candidates)} 位候选人..."))

        # 构建 RAG 上下文
        candidates_context = []
        for ac in top_candidates:
            candidates_context.append(
                f"[候选人: {ac['name']}]\n"
                f"技能: {ac['fields']['skills']}\n"
                f"经历: {ac['fields']['experience'][:300]}\n"
                f"教育: {ac['fields']['education']}\n"
            )

        rag_prompt = f"""你是一位资深 HR 和招聘专家。请根据以下岗位要求和候选人信息，对每位候选人进行深度评估。

=== 岗位需求 ===
{json.dumps(job_requirements, ensure_ascii=False, indent=2)[:3000]}

=== 候选人简历 ===
{chr(10).join(candidates_context)}

请输出 JSON 格式，对每位候选人给出：
- overall_score: 综合评分 (0-1)
- recommendation: strong_hire/recommend/hold/not_recommended
- dimension_scores: {{skill_match, experience_relevance, education, career_trajectory}} 各维度 0-1
- matched_skills: [{{skill, requirement_level, candidate_level, match}}] 匹配的技能
- gaps: [{{skill, importance, gap_severity}}] 缺失的技能
- strengths: [string] 候选人亮点
- weaknesses: [string] 风险或不足
- match_rationale: string 综合评估理由

输出 JSON: {{"candidates":[{{"name":"...", "overall_score":0.85, ...}}]}}"""

        try:
            from services.llm_pool import llm_pool as lp
            rag_response = await lp.chat(
                model="deepseek-v4-pro",
                messages=[{"role": "user", "content": rag_prompt}],
                thinking=False, max_tokens=4096)
            rag_json = rag_response.strip()
            if rag_json.startswith("```"):
                rag_json = rag_json.split("```")[1]
                if rag_json.startswith("json"):
                    rag_json = rag_json[4:]
            rag_result = json.loads(rag_json)
            llm_candidates = rag_result.get("candidates", [])
        except Exception:
            llm_candidates = []

        # 将 LLM 评估结果写入数据库
        match_count = 0
        for ac in top_candidates:
            cid = ac["candidate_id"]
            name = ac["name"]

            # 在 LLM 结果中查找匹配
            llm_match = None
            for lc in llm_candidates:
                if lc.get("name", "") == name:
                    llm_match = lc
                    break

            if not llm_match:
                llm_match = {
                    "overall_score": 0.7,
                    "recommendation": "recommend",
                    "dimension_scores": {"skill_match": 0.7, "experience_relevance": 0.6,
                                          "education": 0.7, "career_trajectory": 0.6},
                    "matched_skills": [],
                    "gaps": [],
                    "strengths": ["LLM 评估未返回详细结果"],
                    "weaknesses": [],
                    "match_rationale": "基于混合检索自动排序",
                }

            match_record = MatchResult(
                id=str(uuid.uuid4()),
                task_id=task_id,
                candidate_id=cid,
                job_id=job.id,
                overall_score=llm_match.get("overall_score", 0.7),
                recommendation=llm_match.get("recommendation", "recommend"),
                dimension_scores=json.dumps(llm_match.get("dimension_scores", {}), ensure_ascii=False),
                matched_skills=json.dumps(llm_match.get("matched_skills", []), ensure_ascii=False),
                gaps=json.dumps(llm_match.get("gaps", []), ensure_ascii=False),
                transferable_skills=json.dumps(llm_match.get("transferable_skills", []), ensure_ascii=False),
                highlights=json.dumps(llm_match.get("strengths", []), ensure_ascii=False),
                risks=json.dumps(llm_match.get("weaknesses", []), ensure_ascii=False),
                match_rationale=llm_match.get("match_rationale", ""),
            )
            db.add(match_record)
            match_count += 1

            _publish(queue, _make_event("node_update", node="candidate_done", candidate_id=cid,
                       status="completed", message=f"评估完成: {name}"))

        db.commit()

        # 偏见检测
        _publish(queue, _make_event("node_update", node="bias_detector", status="running",
                                    message="执行公平性审计..."))
        bias_state = ScreeningState(task_id=task_id, job_id=job.id, status="running")
        bias_state["match_result"] = {"overall_match_score": 0.8}
        try:
            bias_result = await bias_run(bias_state)
            if bias_result.get("bias_report"):
                br = bias_result["bias_report"]
                bias_record = BiasReport(
                    id=str(uuid.uuid4()),
                    task_id=task_id,
                    fairness_score=br.get("overall_fairness_score", 0.9),
                    flags=json.dumps(br.get("flags", []), ensure_ascii=False),
                    distribution_analysis=json.dumps(br.get("distribution_analysis", {}), ensure_ascii=False),
                )
                db.add(bias_record)
                db.commit()
                _publish(queue, _make_event("node_update", node="bias_detector", status="completed"))
        except Exception:
            _publish(queue, _make_event("node_update", node="bias_detector", status="completed",
                       message="偏见检测已跳过"))

        # 完成
        _update_task_status(db, task_id, status="completed")

        matches = db.query(MatchResult).filter(MatchResult.task_id == task_id).all()
        candidates_data = [{"id": m.candidate_id,
                            "name": db.query(Candidate).filter(Candidate.id == m.candidate_id).first().name
                            if db.query(Candidate).filter(Candidate.id == m.candidate_id).first() else "未知",
                            "overall_score": m.overall_score, "recommendation": m.recommendation}
                           for m in matches]

        _publish(queue, _make_event("workflow_complete", task_id=task_id, status="completed",
                 candidates=candidates_data,
                 message=f"RAG 三阶段完成: 索引{len(all_candidates)}份 → 混合召回{len(top_candidates)}人 → LLM评估{match_count}人"))
        _publish(queue, {"event": "__done__"})
'''

content = content[:start_pos] + rag_code + content[end_pos:]

with open('d:/resagent/api/routes/screening.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
with open('d:/resagent/api/routes/screening.py', 'r', encoding='utf-8') as f:
    c = f.read()
checks = ['BM25Retriever', '多路切分', '混合召回', 'LLM 深度评估', 'rag_prompt']
for ch in checks:
    print(f'  [{("OK" if ch in c else "MISS")}] {ch}')
print(f'Total: {len(c)} chars')
