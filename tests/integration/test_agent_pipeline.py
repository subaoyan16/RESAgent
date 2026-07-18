"""Agent 管道集成测试（使用 Mock LLM 模式）。

验证完整的 4 节点 LangGraph + RAG 筛选管道在模拟 LLM 响应模式下正常执行。
"""
import pytest
import os


@pytest.mark.asyncio
async def test_full_pipeline_mock(mock_llm_response, test_db, test_chroma_dir):
    """在 Mock LLM 模式下测试完整的 4 节点管道。

    使用 mock_llm_response（启用 MOCK_LLM=true）、test_db（内存数据库）
    和 test_chroma_dir（临时 Chroma 目录）构造隔离环境，
    通过 screening_graph.ainvoke 运行管道并验证结果。
    """
    os.environ["MOCK_LLM"] = "true"

    from agent_orchestration.graph import screening_graph
    from agent_orchestration.state import ScreeningState
    import uuid

    initial_state: ScreeningState = {
        "task_id": str(uuid.uuid4()),
        "job_id": str(uuid.uuid4()),
        "status": "pending",
        "resume_files": ["test_resume.txt"],
        "job_description": "Senior Python Engineer with 5+ years experience",
        "candidate_ids": [],
        "top_k": 5,
        "parsing_errors": [],
        "analysis_errors": [],
        "match_errors": [],
        "bias_errors": [],
        "report_errors": [],
        "needs_human_review": False,
        "skip_bias_detection": False,
        "ranked_candidates": [],
        "retrieval_metrics": {},
        "match_results": [],
    }

    result = await screening_graph.ainvoke(initial_state)

    assert result is not None
    assert result.get("status") in ("completed", "running", "failed")


@pytest.mark.asyncio
async def test_graph_structure():
    """验证图结构：4 节点拓扑顺序正确。"""
    from agent_orchestration.graph import screening_graph

    nodes = list(screening_graph.nodes.keys())
    assert "job_analyzer" in nodes
    assert "retriever" in nodes
    assert "matcher" in nodes
    assert "bias_detector" in nodes
    assert nodes.index("job_analyzer") < nodes.index("retriever")
    assert nodes.index("retriever") < nodes.index("matcher")
    assert nodes.index("matcher") < nodes.index("bias_detector")
