# tests/rag/test_retriever.py
from rag.retriever import format_context, reciprocal_rank_fusion


def test_rrf_merges_two_lists():
    dense = ["a", "b", "c"]
    sparse = ["b", "c", "a"]
    result = reciprocal_rank_fusion(dense, sparse)
    # "b" appears at rank 2 and 1 — should score highest
    assert result[0] == "b"


def test_rrf_handles_disjoint_lists():
    dense = ["a", "b"]
    sparse = ["c", "d"]
    result = reciprocal_rank_fusion(dense, sparse)
    assert len(result) == 4


def test_rrf_deduplicates_ids():
    dense = ["a", "a", "b"]
    sparse = ["a", "b"]
    result = reciprocal_rank_fusion(dense, sparse)
    assert result.count("a") == 1


def test_format_context_produces_labeled_blocks():
    chunks = [
        {"text": "Port definitions here.", "source_file": "Fw/Com.fpp", "chunk_type": "fpp_block"},
        {"text": "How to connect.", "source_file": "docs/guide.md", "chunk_type": "markdown"},
    ]
    context = format_context(chunks)
    assert "[SOURCE: Fw/Com.fpp | type: fpp_block]" in context
    assert "Port definitions here." in context
