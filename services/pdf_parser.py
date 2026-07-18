"""
PDF/Word 文档文本提取服务 — 支持简历、职位描述等文档的解析与清洗

提供单例 DocumentParser，支持 PDF（PyMuPDF）、DOCX（python-docx）、
纯文本等多种格式的文本提取，并带有 Unicode 归一化、页眉页脚去除等清洗功能。
图片 OCR 需由子类或外部服务实现。
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata

logger = logging.getLogger(__name__)

# 支持的文件扩展名集合，检查文件时用于快速判断
_SUPPORTED_EXTENSIONS = frozenset({".pdf", ".docx", ".doc", ".txt", ".png", ".jpg", ".jpeg"})


class DocumentParser:
    """文档解析器 — 从简历、职位描述等文件中提取并清洗文本

    支持格式: PDF / DOCX / DOC / TXT / 图片（图片仅占位，OCR 需外部扩展）
    核心流程: 格式识别 -> 专用提取器 -> 文本清洗（归一化、去噪）
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_text(self, file_path: str) -> str:
        """根据文件扩展名提取原始文本

        Parameters
        ----------
        file_path : str
            文档路径。

        Returns
        -------
        str
            提取的文本内容。

        Raises
        ------
        ValueError
            不支持的文件扩展名。
        FileNotFoundError
            文件不存在。
        """
        # 前置检查：文件必须存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")

        # 通过扩展名路由到对应的提取方法
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension '{ext}'. "
                f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
            )

        if ext == ".pdf":
            return self._extract_pdf(file_path)
        if ext in (".docx", ".doc"):
            return self._extract_docx(file_path)
        if ext == ".txt":
            return self._extract_txt(file_path)
        # 图片格式 — 基础解析器不提供 OCR 能力
        return "Image OCR not supported in base parser"

    def clean_text(self, raw_text: str) -> str:
        """归一化并清洗提取后的文本

        处理步骤:
        1. Unicode NFC 归一化
        2. 全角 ASCII 转半角
        3. 压缩过多换行（3+ -> 2）
        4. 去除常见页眉页脚（页码、版权声明等）
        5. 去除首尾空白

        Parameters
        ----------
        raw_text : str
            extract_text 提取的原始文本。

        Returns
        -------
        str
            清洗后的文本。
        """
        # Unicode NFC 标准化，确保字符表示一致
        text = unicodedata.normalize("NFC", raw_text)

        # 全角 -> 半角转换（针对 ASCII 字符范围）
        text = self._fullwidth_to_halfwidth(text)

        # 连续 3 个以上换行压缩为 2 个（段落分隔）
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 去除常见页眉页脚模式
        text = re.sub(
            r"(?m)^\s*"
            r"(?:"
            r"Page\s+\d+\s*(?:of|/)\s*\d+"        # Page 1 of 5 / Page 1/5
            r"|Confidential"
            r"|\d+\s*/\s*\d+"
            r"|©.*"
            r"|All\s+[Rr]ights\s+[Rr]eserved"
            r")\s*$",
            "",
            text,
        )

        return text.strip()

    # ------------------------------------------------------------------
    # 各格式提取器
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        """使用 PyMuPDF (fitz) 提取 PDF 文本

        Parameters
        ----------
        file_path : str
            PDF 文件路径。

        Returns
        -------
        str
            按页面顺序拼接的文本。
        """
        import fitz  # PyMuPDF  # type: ignore[import-untyped]

        doc = fitz.open(file_path)
        pages: list[str] = []
        for page in doc:
            text = page.get_text()
            if text:
                pages.append(text)
        doc.close()
        return "\n".join(pages)

    @staticmethod
    def _extract_docx(file_path: str) -> str:
        """使用 python-docx 提取 DOCX 文本

        Parameters
        ----------
        file_path : str
            DOCX 文件路径。

        Returns
        -------
        str
            按段落顺序拼接的文本。
        """
        from docx import Document  # type: ignore[import-untyped]

        doc = Document(file_path)
        paragraphs: list[str] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        return "\n".join(paragraphs)

    @staticmethod
    def _extract_txt(file_path: str) -> str:
        """读取纯文本文件，自动尝试多种编码

        编码尝试顺序: UTF-8 -> GBK(中文Windows常用) -> Latin-1(兜底)
        全部失败后使用 UTF-8 + errors=replace 强制读取。

        Parameters
        ----------
        file_path : str
            文本文件路径。

        Returns
        -------
        str
            文件内容。
        """
        # 依次尝试 UTF-8、GBK、Latin-1 编码
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                with open(file_path, encoding=encoding) as fh:
                    return fh.read()
            except (UnicodeDecodeError, LookupError):
                continue
        # 最后手段：UTF-8 模式，替换无法解码的字符
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    # ------------------------------------------------------------------
    # 文本归一化工具
    # ------------------------------------------------------------------

    @staticmethod
    def _fullwidth_to_halfwidth(text: str) -> str:
        """将全角 ASCII 字符转换为半角

        全角字符范围 FF01-FF5E 映射到半角 U+0021-U+007E（可打印 ASCII），
        全角空格（U+3000）映射为普通半角空格。

        Parameters
        ----------
        text : str
            输入文本。

        Returns
        -------
        str
            半角化后的文本。
        """
        result: list[str] = []
        for ch in text:
            cp = ord(ch)
            # 全角可打印 ASCII -> 半角
            if 0xFF01 <= cp <= 0xFF5E:
                result.append(chr(cp - 0xFEE0))
            # 全角空格 -> 半角空格
            elif cp == 0x3000:
                result.append(" ")
            else:
                result.append(ch)
        return "".join(result)


# 模块级单例 — 全局共享 DocumentParser 实例
doc_parser = DocumentParser()
