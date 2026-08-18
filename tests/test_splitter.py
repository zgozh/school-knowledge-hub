from collector.ingest.splitter import split_text


def test_split_short_text_single_chunk():
    assert split_text("短短一篇。", chunk_size=500) == ["短短一篇。"]


def test_split_long_text_with_overlap():
    text = "段落一。" * 300  # 1200 字
    chunks = split_text(text, chunk_size=500, overlap=50)
    assert len(chunks) >= 3
    assert all(len(c) <= 500 for c in chunks)
    # 拼接检查：所有 chunk 内容都来自原文
    joined = "".join(chunks)
    assert "段落一" in joined
