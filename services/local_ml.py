"""
本地 ML 推理层 — BGE-Reranker 交叉编码重排序

在 Chroma 向量粗筛之后、LLM 精排之前，对 Top-20 候选人进行精确重排序。
模型不可用时降级为透传（不做重排序，直接返回原始结果）。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LocalMLPipeline:
    """本地推理管道 — BGE-Reranker-v2-m3 交叉编码器"""

    def __init__(self, device: str = "auto") -> None:
        self._device = self._detect_device() if device == "auto" else device
        self.reranker: Any = None

        try:
            from sentence_transformers import CrossEncoder

            self.reranker = CrossEncoder(
                "BAAI/bge-reranker-v2-m3",
                device=self._device,
                local_files_only=True,
            )
            logger.info("Loaded BGE-Reranker-v2-m3 on %s", self._device)
        except Exception as exc:
            logger.warning("Failed to load BGE-Reranker-v2-m3: %s", exc)
            self.reranker = None

    @staticmethod
    def _detect_device() -> str:
        """自动检测最优设备：CUDA > MPS > CPU"""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def is_available(self) -> bool:
        """重排序模型是否可用"""
        return self.reranker is not None

    def rerank(self, query: str, documents: list[str], top_k: int = 5) -> list[dict]:
        """使用 BGE-Reranker 对候选文档按查询相关性重排序。

        模型不可用时降级为透传模式，直接返回原始顺序的前 top_k 个文档。

        Args:
            query: 查询文本（通常为岗位描述）
            documents: 候选文档列表（通常为简历文本）
            top_k: 返回前 K 个最相关的结果（默认 5）

        Returns:
            按相关性降序排列的结果列表，每项包含 index、score、document 三个字段
        """
        if not self.reranker or not documents:
            return [
                {"index": i, "score": 1.0, "document": doc}
                for i, doc in enumerate(documents)
            ][:top_k]

        pairs = [[query, doc] for doc in documents]
        scores = self.reranker.predict(pairs, show_progress_bar=False)
        ranked = sorted(
            [
                {"index": i, "score": float(s), "document": doc}
                for i, (s, doc) in enumerate(zip(scores, documents))
            ],
            key=lambda x: x["score"],
            reverse=True,
        )
        return ranked[:top_k]


# 延迟初始化（避免模块导入时尝试加载模型）
_local_ml_instance = None

def get_local_ml() -> LocalMLPipeline:
    """获取本地 ML 管道单例（首次调用时初始化）"""
    global _local_ml_instance
    if _local_ml_instance is None:
        _local_ml_instance = LocalMLPipeline()
    return _local_ml_instance
