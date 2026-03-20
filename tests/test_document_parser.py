import io

import pytest
from docx import Document

from app.core.exceptions import ExtractionError, UnsupportedFileTypeError
from app.services import document_parser


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestFileTypeDetection:
    def test_unsupported_type_raises(self):
        fake_bytes = b"NOTAFILE" * 100
        with pytest.raises(UnsupportedFileTypeError):
            document_parser.parse(fake_bytes, "file.exe")

    def test_docx_detected_by_magic_bytes(self):
        docx_bytes = _make_docx_bytes(["This is a work contract. " * 20])
        result = document_parser.parse(docx_bytes, "contract.docx")
        assert result.file_type == "docx"

    def test_detects_docx_even_with_pdf_extension(self):
        docx_bytes = _make_docx_bytes(["This is a work contract. " * 20])
        # filename says .pdf but magic bytes are DOCX
        result = document_parser.parse(docx_bytes, "contract.pdf")
        assert result.file_type == "docx"


class TestDocxParser:
    def test_extracts_paragraph_text(self):
        text = "The tenant agrees to pay monthly rent of one thousand eight hundred dollars. " * 5
        docx_bytes = _make_docx_bytes([text])
        result = document_parser.parse(docx_bytes, "lease.docx")
        assert "tenant" in result.text.lower()
        assert result.word_count > 0

    def test_empty_docx_raises_extraction_error(self):
        docx_bytes = _make_docx_bytes([])
        with pytest.raises(ExtractionError):
            document_parser.parse(docx_bytes, "empty.docx")

    def test_page_count_estimated(self):
        # ~600 words → should estimate 2 pages (600 // 300)
        long_text = "word " * 600
        docx_bytes = _make_docx_bytes([long_text])
        result = document_parser.parse(docx_bytes, "long.docx")
        assert result.page_count == 2

    def test_extraction_method_label(self):
        docx_bytes = _make_docx_bytes(["Contract text. " * 20])
        result = document_parser.parse(docx_bytes, "contract.docx")
        assert result.extraction_method == "python-docx"
