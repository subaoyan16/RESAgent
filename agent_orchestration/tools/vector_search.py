"""LangChain 工具：基于 Chroma 的向量搜索，用于候选人匹配。

通过语义向量检索找到与查询最相似的候选人，
支持按工作年限过滤和自定义返回数量。
"""
from langchain_core.tools import tool
from services.chroma_store import chroma_store
from services.embedding import embedding_service


@tool
def search_similar_candidates(query: str, top_k: int = 20, min_years: float = 0) -> list[dict]:
    """在 Chroma 中搜索与查询相似的候选人（查询文本可为职位描述或技能描述）。

    Args:
        query: 搜索查询文本（职位要求、技能描述等）
        top_k: 返回的候选人数量上限（默认 20）
        min_years: 最低工作年限过滤条件（默认 0 表示不限制）

    Returns:
        候选人字典列表，包含 id、score（相似度分数）和 metadata（元数据）
    """
    # 将查询文本转换为向量嵌入
    query_embedding = embedding_service.embed_query(query)

    # 构建元数据过滤条件：如果设置了最低年限，则添加过滤
    where_filter = None
    if min_years > 0:
        where_filter = {"years_of_experience": {"$gte": min_years}}

    # 在 Chroma 向量库中执行搜索
    results = chroma_store.search_candidates(
        query_embedding=query_embedding,
        top_k=top_k,
        where_filter=where_filter
    )
    return results
