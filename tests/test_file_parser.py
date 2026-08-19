import pytest

from collector.parser import file_parser


def test_parse_txt_returns_title_and_content():
    result = file_parser.parse_file("通知.txt", "这是正文".encode("utf-8"))
    assert result["title"] == "通知"
    assert result["content"] == "这是正文"


def test_parse_md_decodes_gbk_fallback():
    result = file_parser.parse_file("制度.md", "规章制度内容".encode("gbk"))
    assert "规章制度内容" in result["content"]


def test_parse_unsupported_ext_raises():
    with pytest.raises(ValueError):
        file_parser.parse_file("a.xlsx", b"xx")


def test_parse_empty_content_raises():
    with pytest.raises(ValueError):
        file_parser.parse_file("a.txt", b"   ")


def test_parse_pdf_dispatches(monkeypatch):
    monkeypatch.setattr(file_parser, "_extract_pdf", lambda data: "PDF 正文")
    result = file_parser.parse_file("报告.pdf", b"%PDF-x")
    assert result["content"] == "PDF 正文"


def test_parse_docx_roundtrip(tmp_path):
    from docx import Document

    doc = Document()
    doc.add_paragraph("这是 Word 正文")
    p = tmp_path / "t.docx"
    doc.save(str(p))
    result = file_parser.parse_file("t.docx", p.read_bytes())
    assert "这是 Word 正文" in result["content"]
