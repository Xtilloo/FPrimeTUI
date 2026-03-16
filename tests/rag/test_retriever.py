# tests/rag/test_retriever.py
from rag.retriever import (
    apply_diversity_filter,
    classify_query,
    composite_score,
    extract_keywords,
    format_context,
    get_content_type_boost,
    get_source_category,
    get_source_category_boost,
    keyword_score,
    reciprocal_rank_fusion,
    tokenize,
)


def test_rrf_merges_two_lists():
    dense = ["a", "b", "c"]
    sparse = ["b", "c", "a"]
    result = reciprocal_rank_fusion(dense, sparse)
    # Returns dict[str, float] now
    assert isinstance(result, dict)
    # "b" appears at rank 2 and 1 — should score highest
    sorted_ids = sorted(result, key=lambda x: result[x], reverse=True)
    assert sorted_ids[0] == "b"


def test_rrf_handles_disjoint_lists():
    dense = ["a", "b"]
    sparse = ["c", "d"]
    result = reciprocal_rank_fusion(dense, sparse)
    assert len(result) == 4
    assert all(isinstance(v, float) for v in result.values())


def test_rrf_deduplicates_ids():
    dense = ["a", "a", "b"]
    sparse = ["a", "b"]
    result = reciprocal_rank_fusion(dense, sparse)
    assert "a" in result
    assert "b" in result


def test_format_context_produces_labeled_blocks():
    chunks = [
        {"text": "Port definitions here.", "source_file": "Fw/Com.fpp", "chunk_type": "fpp_block", "content_type": "code"},
        {"text": "How to connect.", "source_file": "docs/guide.md", "chunk_type": "markdown", "content_type": "concept"},
    ]
    context = format_context(chunks)
    assert "[SOURCE: Fw/Com.fpp | type: fpp_block | content: code]" in context
    assert "[SOURCE: docs/guide.md | type: markdown | content: concept]" in context
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



def test_get_source_category_framework_core():
    assert get_source_category("Fw/Comp/docs/sdd.md") == "framework_core"
    assert get_source_category("Os/Task/Task.hpp") == "framework_core"


def test_get_source_category_docs_tutorial():
    assert get_source_category("docs/getting-started/install.md") == "docs_tutorial"
    assert get_source_category("docs/how-to/add-component.md") == "docs_tutorial"


def test_get_source_category_docs_reference():
    assert get_source_category("docs/reference/fpp-grammar.md") == "docs_reference"
    assert get_source_category("docs/user-manual/overview.md") == "docs_reference"


def test_get_source_category_fpp_spec():
    assert get_source_category("Fw/Comp/Comp.fpp") == "fpp_spec"


def test_get_source_category_service_docs():
    assert get_source_category("Svc/FileManager/docs/sdd.md") == "service_docs"


def test_get_source_category_test_projects():
    assert get_source_category("FppTestProject/FppTest/component/README.md") == "test_projects"


def test_get_source_category_tools():
    assert get_source_category("fprime-tools/src/fprime/fpp/utils.py") == "tools"


def test_get_source_category_unknown_defaults_to_service_docs():
    # Unknown paths get neutral boost (1.0)
    assert get_source_category("some/random/path.txt") == "service_docs"


def test_source_category_boost_framework_core_highest():
    fw_boost = get_source_category_boost("Fw/Comp/docs/sdd.md")
    svc_boost = get_source_category_boost("Svc/FileManager/docs/sdd.md")
    assert fw_boost > svc_boost


def test_source_category_boost_test_projects_below_neutral():
    test_boost = get_source_category_boost("FppTestProject/README.md")
    assert test_boost < 1.0


def test_content_type_boost_code_for_code_seeking():
    assert get_content_type_boost("code", "code_seeking") == 1.2


def test_content_type_boost_concept_for_code_seeking():
    # concept chunks are not boosted for code queries
    assert get_content_type_boost("concept", "code_seeking") == 1.0


def test_content_type_boost_concept_for_concept_seeking():
    assert get_content_type_boost("concept", "concept_seeking") == 1.2


def test_content_type_boost_tutorial_for_concept_seeking():
    assert get_content_type_boost("tutorial", "concept_seeking") == 1.2


def test_content_type_boost_reference_for_comparison():
    assert get_content_type_boost("reference", "comparison") == 1.1


def test_content_type_boost_general_query_no_boost():
    assert get_content_type_boost("code", "general") == 1.0
    assert get_content_type_boost("concept", "general") == 1.0


def test_content_type_boost_file_specific_no_boost():
    assert get_content_type_boost("code", "file_specific") == 1.0


def test_content_type_boost_component_specific_no_boost():
    assert get_content_type_boost("code", "component_specific") == 1.0


def test_classify_query_file_specific():
    entities = {"filemanager", "health", "cmddispatcher"}
    qtype, entity = classify_query("Explain the FileManager/docs/sdd.md file", entities)
    assert qtype == "file_specific"
    assert entity == "filemanager"


def test_classify_query_file_extension():
    entities: set[str] = set()
    qtype, entity = classify_query("Explain the sdd.md file format", entities)
    assert qtype == "file_specific"


def test_classify_query_component_via_camelcase():
    # CamelCase identifier in known_entities → component_specific (no file extension)
    entities = {"filemanager", "health"}
    qtype, entity = classify_query("What does FileManager do?", entities)
    assert qtype == "component_specific"
    assert entity == "filemanager"


def test_classify_query_component_specific():
    entities = {"buffermanager", "cmddispatcher"}
    qtype, entity = classify_query("How does BufferManager allocate buffers?", entities)
    assert qtype == "component_specific"
    assert entity == "buffermanager"


def test_classify_query_component_not_in_index_falls_back():
    entities = {"health", "cmddispatcher"}  # BufferManager NOT in index
    qtype, _ = classify_query("How does BufferManager allocate buffers?", entities)
    # BufferManager not in known_entities, so falls through
    assert qtype != "component_specific"


def test_classify_query_comparison():
    entities: set[str] = set()
    qtype, _ = classify_query("What is the difference between active and passive components?", entities)
    assert qtype == "comparison"


def test_classify_query_comparison_vs():
    entities: set[str] = set()
    qtype, _ = classify_query("Active vs passive components", entities)
    assert qtype == "comparison"


def test_classify_query_code_seeking():
    entities: set[str] = set()
    qtype, _ = classify_query("How to implement a command handler?", entities)
    assert qtype == "code_seeking"


def test_classify_query_code_seeking_example():
    entities: set[str] = set()
    qtype, _ = classify_query("Show me an example of telemetry write", entities)
    assert qtype == "code_seeking"


def test_classify_query_concept_seeking():
    entities: set[str] = set()
    qtype, _ = classify_query("What is a rate group?", entities)
    assert qtype == "concept_seeking"


def test_classify_query_general():
    entities: set[str] = set()
    qtype, _ = classify_query("Tell me about fprime", entities)
    assert qtype == "general"


def test_classify_query_precedence_component_over_comparison():
    # "FileManager" is a known CamelCase entity AND "difference" is present
    # Component-specific has higher precedence than comparison
    entities = {"filemanager"}
    qtype, _ = classify_query("What is the difference in FileManager?", entities)
    assert qtype == "component_specific"


def test_classify_query_precedence_comparison_over_concept():
    entities: set[str] = set()
    qtype, _ = classify_query("What is the difference between ports and channels?", entities)
    assert qtype == "comparison"


def test_composite_score_combines_signals_multiplicatively():
    chunk = {
        "text": "ActiveComponent runs in its own thread.",
        "source_file": "Fw/Comp/docs/sdd.md",
        "content_type": "concept",
    }
    kws = ["activecomponent"]
    score = composite_score(0.02, chunk, kws, "concept_seeking")
    # Base: 0.02
    # Source boost (framework_core): * 1.3
    # Content boost (concept for concept_seeking): * 1.2
    # Keyword (1.0 match * 0.3 weight): * 1.3
    expected_approx = 0.02 * 1.3 * 1.2 * 1.3
    assert abs(score - expected_approx) < 0.001


def test_composite_score_no_keyword_match():
    chunk = {
        "text": "Subtopology configuration guide.",
        "source_file": "docs/how-to/subtopologies.md",
        "content_type": "tutorial",
    }
    score = composite_score(0.02, chunk, ["activecomponent"], "code_seeking")
    # Source boost (docs_tutorial): * 1.2
    # Content boost (tutorial for code_seeking): * 1.0
    # Keyword (0.0 match): * 1.0
    expected_approx = 0.02 * 1.2 * 1.0 * 1.0
    assert abs(score - expected_approx) < 0.001


def test_diversity_filter_general_max_2():
    chunks = [
        {"source_file": "A.md", "score": 0.05},
        {"source_file": "A.md", "score": 0.04},
        {"source_file": "A.md", "score": 0.03},  # should be filtered
        {"source_file": "B.md", "score": 0.02},
    ]
    result = apply_diversity_filter(chunks, "general", "", 5)
    sources = [c["source_file"] for c in result]
    assert sources.count("A.md") <= 2
    assert len(result) == 3  # 2 from A + 1 from B


def test_diversity_filter_comparison_max_1():
    chunks = [
        {"source_file": "A.md", "score": 0.05},
        {"source_file": "A.md", "score": 0.04},  # should be filtered
        {"source_file": "B.md", "score": 0.03},
        {"source_file": "C.md", "score": 0.02},
    ]
    result = apply_diversity_filter(chunks, "comparison", "", 5)
    sources = [c["source_file"] for c in result]
    assert sources.count("A.md") == 1


def test_diversity_filter_file_specific_relaxed():
    chunks = [
        {"source_file": "Svc/FileManager/docs/sdd.md", "score": 0.05},
        {"source_file": "Svc/FileManager/docs/sdd.md", "score": 0.04},
        {"source_file": "Svc/FileManager/docs/sdd.md", "score": 0.03},
        {"source_file": "Svc/FileManager/docs/sdd.md", "score": 0.02},
        {"source_file": "B.md", "score": 0.01},
    ]
    result = apply_diversity_filter(chunks, "file_specific", "filemanager", 5)
    sources = [c["source_file"] for c in result]
    # All 4 from FileManager should pass (up to FINAL_K)
    assert sources.count("Svc/FileManager/docs/sdd.md") == 4


def test_diversity_filter_preserves_order():
    chunks = [
        {"source_file": "A.md", "score": 0.05},
        {"source_file": "B.md", "score": 0.04},
        {"source_file": "A.md", "score": 0.03},
        {"source_file": "C.md", "score": 0.02},
    ]
    result = apply_diversity_filter(chunks, "general", "", 5)
    scores = [c["score"] for c in result]
    assert scores == sorted(scores, reverse=True)


def test_curated_qa_gets_curated_knowledge_category():
    assert get_source_category("rag/curated_qa.md") == "curated_knowledge"


def test_curated_knowledge_boost_is_1_15():
    assert get_source_category_boost("rag/curated_qa.md") == 1.15
