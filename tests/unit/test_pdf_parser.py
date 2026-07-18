"""文档解析器单元测试。

测试 PDF/Word 解析服务的核心功能，包括文本提取、空白清理、
Unicode 规范化和不受支持的文件扩展名处理。
"""
import pytest
import os
import tempfile


class TestDocumentParser:
    """文档解析器测试套件。"""

    def test_extract_txt(self):
        """从纯文本文件中提取内容，应能正确读取文件名和人名等关键信息。"""
        from services.pdf_parser import doc_parser
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Test resume content\nName: John Doe\nSkills: Python, AWS")
            tmp_path = f.name
        try:
            text = doc_parser.extract_text(tmp_path)
            assert "John Doe" in text
            assert "Python" in text
        finally:
            # 确保临时文件被清理
            os.unlink(tmp_path)

    def test_clean_text_removes_excess_whitespace(self):
        """clean_text 应将连续多个换行压缩至不超过 3 个。"""
        from services.pdf_parser import doc_parser
        dirty = "Hello\n\n\n\n\nWorld\n\n\n"
        cleaned = doc_parser.clean_text(dirty)
        assert cleaned.count('\n') <= 3

    def test_unsupported_extension(self):
        """传入不支持的扩展名时，应返回包含 'unsupported' 或 'not supported' 的错误信息。"""
        from services.pdf_parser import doc_parser
        result = doc_parser.extract_text("test.xyz")
        assert "not supported" in result.lower() or "unsupported" in result.lower()

    def test_clean_text_normalizes_unicode(self):
        """clean_text 应将全角字符（如 ＂Ｈｅｌｌｏ　Ｗｏｒｌｄ）规范化为半角。"""
        from services.pdf_parser import doc_parser
        text = "Ｈｅｌｌｏ　Ｗｏｒｌｄ"  # 全角字符
        cleaned = doc_parser.clean_text(text)
        assert "Hello World" in cleaned
