"""文件解析：PDF/Word/纯文本/Markdown → {title, content}。"""
from pathlib import Path


def parse_file(filename: str, data: bytes) -> dict:
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md"):
        content = _decode_text(data)
    elif ext == ".pdf":
        content = _extract_pdf(data)
    elif ext == ".docx":
        content = _extract_docx(data)
    else:
        raise ValueError(f"不支持的文件类型: {ext or '(无扩展名)'}")
    if not content.strip():
        raise ValueError("文件解析结果为空")
    return {"title": Path(filename).stem, "content": content}


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gbk")


def _extract_pdf(data: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)
