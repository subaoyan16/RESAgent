"""
resagent 服务层 — LLM 调用、向量数据库、文档解析、嵌入等核心服务

提供模块级单例（llm_pool, chroma_store, doc_parser, embedding_service 等），
供上层 Agent 及业务代码直接导入使用。
"""
