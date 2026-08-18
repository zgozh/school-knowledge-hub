from qa_api.retriever.hybrid import ScoredChunk, cliff_cutoff


def make_chunk(cid, score):
    return ScoredChunk(chunk_id=cid, doc_id="d", text="t", score=score,
                       dense_score=score, sparse_score=score)


def test_cliff_cutoff_stops_at_drop():
    chunks = [make_chunk("a", 0.9), make_chunk("b", 0.85), make_chunk("c", 0.3), make_chunk("d", 0.28)]
    kept = cliff_cutoff(chunks, ratio=0.3)
    assert [c.chunk_id for c in kept] == ["a", "b"]


def test_cliff_cutoff_keeps_at_least_one():
    chunks = [make_chunk("a", 0.9)]
    kept = cliff_cutoff(chunks, ratio=0.3)
    assert len(kept) == 1


def test_cliff_cutoff_no_drop_keeps_all():
    chunks = [make_chunk("a", 0.9), make_chunk("b", 0.88), make_chunk("c", 0.86)]
    kept = cliff_cutoff(chunks, ratio=0.3)
    assert len(kept) == 3
