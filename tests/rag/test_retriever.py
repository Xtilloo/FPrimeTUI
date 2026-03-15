# tests/rag/test_retriever.py
from rag.retriever import (
    extract_keywords,
    format_context,
    keyword_score,
    reciprocal_rank_fusion,
    tokenize,
)


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


def test_tokenize_expands_camel_case():
    tokens = tokenize("ActiveComponent FwCom")
    assert "activecomponent" in tokens
    assert "active" in tokens
    assert "component" in tokens
    assert "fwcom" in tokens


def test_tokenize_strips_punctuation():
    tokens = tokenize("ActiveComponent.")
    assert "activecomponent" in tokens
    assert "activecomponent." not in tokens


def test_tokenize_plain_text_unchanged():
    tokens = tokenize("active component foo")
    assert tokens == ["active", "component", "foo"]


def test_extract_keywords_finds_camel_case():
    keywords = extract_keywords("What is an ActiveComponent in fprime?")
    assert "activecomponent" in keywords


def test_extract_keywords_includes_spaced_form():
    # 'active component' allows matching .fpp chunks: 'active component Foo { }'
    keywords = extract_keywords("What is an ActiveComponent in fprime?")
    assert "active component" in keywords


def test_extract_keywords_ignores_sentence_capitals():
    # 'What' starts with uppercase but has no lowercase→uppercase transition
    keywords = extract_keywords("What is an ActiveComponent in fprime?")
    assert "what" not in keywords
    assert "is" not in keywords
    assert "an" not in keywords


def test_extract_keywords_matches_fwcom_style():
    # Two-letter prefix + CamelCase (e.g. FwCom) should match
    keywords = extract_keywords("How does FwCom work?")
    assert "fwcom" in keywords
    assert "fw com" in keywords


def test_extract_keywords_finds_quoted_phrases():
    keywords = extract_keywords('How does "rate group" work?')
    assert "rate group" in keywords


def test_keyword_score_exact_match():
    score = keyword_score("An ActiveComponent runs in its own thread.", ["activecomponent"])
    assert score == 1.0


def test_keyword_score_no_match():
    score = keyword_score("This is about subtopologies and baremetal.", ["activecomponent"])
    assert score == 0.0


def test_keyword_score_partial_match():
    score = keyword_score("ActiveComponent and PassiveComponent differ.", ["activecomponent", "queuedcomponent"])
    assert 0.0 < score < 1.0
