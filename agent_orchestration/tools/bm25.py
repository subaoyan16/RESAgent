"""BM25 关键词检索器 — 轻量级全文检索。

使用 jieba 进行中文分词，与 Chroma 向量检索组合构建混合召回。
"""

from __future__ import annotations

import math
import re
import logging
from collections import defaultdict

import jieba

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """中英文混合分词。

    中文使用 jieba 分词，英文按词分割。

    Args:
        text: 待分词的原始文本。

    Returns:
        小写化的 token 列表。
    """
    tokens: list[str] = []
    # 按中文字符、英文单词、数字分别提取
    parts = re.findall(r"[一-鿿]+|[a-zA-Z]+|\d+", text.lower())
    for part in parts:
        if re.match(r"[一-鿿]", part):
            # 中文: jieba 分词
            tokens.extend(jieba.lcut(part))
        else:
            tokens.append(part)
    return [t for t in tokens if len(t.strip()) > 0]


class BM25Retriever:
    """轻量级 BM25 全文检索器。

    支持增量添加文档，build() 后执行 search()。
    线程不安全——单线程使用。

    Parameters
    ----------
    k1 : float
        词频饱和参数，默认 1.5。
    b : float
        文档长度归一化参数，默认 0.75。
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.documents: list[dict] = []
        self._doc_freqs: defaultdict[str, int] = defaultdict(int)
        self._doc_lengths: list[int] = []
        self._tokenized_docs: list[list[str]] = []
        self._avgdl: float = 0.0
        self._N: int = 0
        self._built: bool = False

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    @property
    def doc_count(self) -> int:
        """已索引的文档数量。"""
        return len(self.documents)

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """向索引中添加一篇文档。

        Args:
            doc_id: 文档唯一标识（通常为候选人 ID）。
            text:  用于检索的文本内容。
            metadata: 附加元数据，search() 返回时会附带。
        """
        if not text.strip():
            return
        self.documents.append(
            {"id": doc_id, "text": text, "metadata": metadata or {}}
        )
        self._built = False

    def build(self) -> None:
        """构建倒排索引。

        在添加完所有文档后调用一次。重复调用会重建索引。
        """
        self._N = len(self.documents)
        self._doc_freqs.clear()
        self._doc_lengths.clear()
        self._tokenized_docs.clear()

        if self._N == 0:
            self._built = True
            return

        for doc in self.documents:
            tokens = _tokenize(doc["text"])
            self._tokenized_docs.append(tokens)
            self._doc_lengths.append(len(tokens))
            for term in set(tokens):
                self._doc_freqs[term] += 1

        self._avgdl = sum(self._doc_lengths) / self._N if self._N > 0 else 1.0
        self._built = True
        logger.debug("BM25 index built: %d docs, avgdl=%.1f", self._N, self._avgdl)

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """检索与查询最相关的 Top-K 文档。

        Args:
            query: 查询文本。
            top_k: 返回的最大文档数。

        Returns:
            按 BM25 分数降序排列的结果列表，
            每项为 ``{"id": str, "score": float, "metadata": dict}``。
        """
        if not self._built:
            self.build()

        if self._N == 0:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[int, float]] = []
        for i, doc_tokens in enumerate(self._tokenized_docs):
            term_freqs: defaultdict[str, int] = defaultdict(int)
            for t in doc_tokens:
                term_freqs[t] += 1

            score = 0.0
            doc_len = self._doc_lengths[i]
            for qt in query_tokens:
                f = term_freqs.get(qt, 0)
                if f == 0:
                    continue
                idf = self._idf(qt)
                numerator = f * (self.k1 + 1)
                denominator = f + self.k1 * (
                    1 - self.b + self.b * doc_len / max(self._avgdl, 1)
                )
                score += idf * numerator / denominator
            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results: list[dict] = []
        for idx, score in scores[:top_k]:
            doc = self.documents[idx]
            results.append(
                {"id": doc["id"], "score": score, "metadata": doc["metadata"]}
            )
        return results

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _idf(self, term: str) -> float:
        n = self._doc_freqs.get(term, 0)
        return math.log((self._N - n + 0.5) / (n + 0.5) + 1.0)
