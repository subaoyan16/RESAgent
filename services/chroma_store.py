"""
Chroma 向量数据库封装 — 候选人与职位嵌入向量的持久化存储与相似度搜索

提供单例 ChromaStore，管理两个集合（candidates / jobs），
支持基于余弦相似度的向量检索和元数据过滤。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import chromadb

logger = logging.getLogger(__name__)

_DEFAULT_PERSIST_DIR = "./data/chroma"


class ChromaStore:
    """ChromaDB 持久化封装，管理 candidates 和 jobs 两个向量集合

    核心设计:
    - 双集合: candidates(候选人简历) / jobs(职位描述)，各自独立索引
    - 余弦距离: HNSW 索引使用 cosine 空间，用于语义相似度搜索
    - 自动建库: 集合不存在时自动创建，无需手动初始化
    - 单例模式: 模块级 chroma_store 全局共享
    """

    def __init__(self, persist_dir: str | None = None) -> None:
        """初始化 ChromaDB 客户端，创建或获取两个向量集合

        Parameters
        ----------
        persist_dir : str | None
            数据持久化目录。默认为 ./data/chroma，可通过 CHROMA_PERSIST_DIR 环境变量覆盖。
        """
        # 持久化目录优先级：参数 > 环境变量 > 默认值
        persist_dir = persist_dir or os.environ.get("CHROMA_PERSIST_DIR", _DEFAULT_PERSIST_DIR)
        logger.info("Initialising ChromaStore at %s", persist_dir)

        # 初始化持久化客户端（数据写入磁盘，进程重启后保留）
        self._client = chromadb.PersistentClient(path=persist_dir)
        # candidates 集合：存储候选人简历的向量 + 元数据
        self._candidates = self._client.get_or_create_collection(
            name="candidates",
            metadata={"hnsw:space": "cosine"},  # 使用余弦距离度量相似度
        )
        # jobs 集合：存储职位描述的向量 + 元数据
        self._jobs = self._client.get_or_create_collection(
            name="jobs",
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------------

    def add_candidate(
        self,
        candidate_id: str,
        document: str,
        metadata: dict[str, Any],
        embedding: list[float] | None = None,
    ) -> None:
        """添加或更新候选人记录

        Parameters
        ----------
        candidate_id : str
            候选人唯一标识。
        document : str
            简历文本内容（用于索引）。
        metadata : dict
            附加的元数据（如姓名、岗位、来源等）。
        embedding : list[float] | None
            预计算的嵌入向量。若为 None，则由 Chroma 内置模型自动计算。
        """
        kwargs: dict[str, Any] = dict(
            ids=[candidate_id],
            documents=[document],
            metadatas=[metadata],
        )
        # 如果传入了预计算向量，则使用它；否则让 Chroma 自动嵌入
        if embedding is not None:
            kwargs["embeddings"] = [embedding]

        self._candidates.upsert(**kwargs)
        logger.debug("Upserted candidate %s", candidate_id)

    def add_job(
        self,
        job_id: str,
        document: str,
        metadata: dict[str, Any],
    ) -> None:
        """添加或更新职位记录

        Parameters
        ----------
        job_id : str
            职位唯一标识。
        document : str
            职位描述文本。
        metadata : dict
            附加的元数据（如公司、薪资范围、地点等）。
        """
        self._jobs.upsert(
            ids=[job_id],
            documents=[document],
            metadatas=[metadata],
        )
        logger.debug("Upserted job %s", job_id)

    # ------------------------------------------------------------------
    # 搜索操作
    # ------------------------------------------------------------------

    def search_candidates(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        where_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """在候选人集合中按向量相似度搜索

        Parameters
        ----------
        query_embedding : list[float]
            查询向量。
        top_k : int
            返回最近邻数量（默认 20）。
        where_filter : dict | None
            可选的元数据过滤条件（Chroma where 子句语法）。

        Returns
        -------
        list[dict]
            每一项包含: {"id": str, "distance": float, "metadata": dict}
        """
        kwargs: dict[str, Any] = dict(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "distances"],
        )
        if where_filter:
            kwargs["where"] = where_filter

        result = self._candidates.query(**kwargs)
        return self._format_results(result)

    def search_jobs(
        self,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """在职位集合中按向量相似度搜索

        Parameters
        ----------
        query_embedding : list[float]
            查询向量。
        top_k : int
            返回最近邻数量（默认 10）。

        Returns
        -------
        list[dict]
            每一项包含: {"id": str, "distance": float, "metadata": dict}
        """
        result = self._jobs.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "distances"],
        )
        return self._format_results(result)

    # ------------------------------------------------------------------
    # 单条记录访问
    # ------------------------------------------------------------------

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        """根据 ID 获取单条候选人记录

        Parameters
        ----------
        candidate_id : str
            候选人唯一标识。

        Returns
        -------
        dict | None
            匹配记录的元数据，未找到时返回 None。
        """
        result = self._candidates.get(
            ids=[candidate_id],
            include=["metadatas"],
        )
        # Chroma 查询结果非空且包含 ID 时才返回有效数据
        if result and result["ids"]:
            return {
                "id": result["ids"][0],
                "metadata": result["metadatas"][0] if result["metadatas"] else {},
            }
        return None

    # ------------------------------------------------------------------
    # 维护操作
    # ------------------------------------------------------------------

    def delete_candidate(self, candidate_id: str) -> None:
        """根据 ID 删除候选人记录

        Parameters
        ----------
        candidate_id : str
            要删除的候选人唯一标识。
        """
        self._candidates.delete(ids=[candidate_id])
        logger.debug("Deleted candidate %s", candidate_id)

    def count_candidates(self) -> int:
        """返回候选人集合中的记录总数

        Returns
        -------
        int
            候选人数量。
        """
        return self._candidates.count()

    def reset(self) -> None:
        """清空并重建两个向量集合

        用于测试环境或在数据需要完全刷新时调用。
        会删除现有集合并重新创建空集合。
        """
        logger.info("Resetting ChromaStore collections")
        # 删除旧集合
        self._client.delete_collection("candidates")
        self._client.delete_collection("jobs")
        # 重建空集合
        self._candidates = self._client.create_collection(
            name="candidates",
            metadata={"hnsw:space": "cosine"},
        )
        self._jobs = self._client.create_collection(
            name="jobs",
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _format_results(result: dict[str, Any]) -> list[dict[str, Any]]:
        """将 ChromaDB 原始查询结果展平为干净的列表字典格式

        ChromaDB 返回的嵌套结构包含 ids/distances/metadatas 各为 list[list]，
        此方法提取每个位置的值并组装为统一的字典列表。

        Parameters
        ----------
        result : dict
            ChromaDB query() 的原始返回结果。

        Returns
        -------
        list[dict]
            展平后的结果列表。
        """
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]

        formatted: list[dict[str, Any]] = []
        for i in range(len(ids)):
            formatted.append(
                {
                    "id": ids[i],
                    "distance": distances[i] if distances else 0.0,
                    "metadata": metadatas[i] if metadatas else {},
                }
            )
        return formatted


# 模块级单例 — 全局共享 ChromaStore 实例
chroma_store = ChromaStore()
