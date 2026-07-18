"""
嵌入向量服务 — BGE-M3 本地模型优先，零向量兜底。

优先级:
  1. BGE-M3 本地模型（sentence-transformers，1024 维，L2 归一化）
  2. 零向量兜底（模型加载失败时保证服务不崩溃）

设计要点:
  - 使用 local_files_only=True 避免首次运行时下载模型
  - CPU 推理以确保兼容性（可通过修改 device 参数切换到 GPU）
  - embed() 返回的向量已做 L2 归一化，可直接用于余弦相似度计算
"""

from __future__ import annotations

import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

_EMBEDDING_DIM = 1024  # BGE-M3 输出维度


class EmbeddingService:
    """嵌入向量引擎 — BGE-M3 优先"""

    def __init__(self) -> None:
        self.local_model = None
        try:
            from sentence_transformers import SentenceTransformer
            self.local_model = SentenceTransformer(
                "BAAI/bge-m3",
                device="cpu",
                local_files_only=True,
            )
            logger.info("BGE-M3 loaded successfully (dim=%d)", _EMBEDDING_DIM)
        except Exception as exc:
            logger.warning("Failed to load BGE-M3: %s", exc)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转换为嵌入向量。

        如果 BGE-M3 模型可用，使用它生成 1024 维 L2 归一化向量；
        否则返回全零向量作为降级方案。

        Args:
            texts: 待嵌入的文本列表

        Returns:
            与 texts 等长的向量列表，每个向量为 1024 维 float 列表
        """
        if not texts:
            return []

        if self.local_model is not None:
            embeddings = self.local_model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            if isinstance(embeddings, np.ndarray):
                return embeddings.tolist()
            return [e.tolist() for e in embeddings]

        return [[0.0] * _EMBEDDING_DIM for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        """嵌入单条查询文本。

        等价于 embed([text])[0]，是单文本查询的便捷方法。

        Args:
            text: 待嵌入的单条文本

        Returns:
            1024 维 float 列表
        """
        return self.embed([text])[0]


embedding_service = EmbeddingService()
