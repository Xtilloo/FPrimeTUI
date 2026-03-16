# RAG Accuracy Improvement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve RAG retrieval accuracy from 29% pass rate to significantly higher by fixing retrieval ranking, expanding index coverage, and improving prompt framing.

**Architecture:** Three-layer improvement — retrieval pipeline refactoring (source-category boosting, composite scoring, adaptive diversity filter, query-type classification), indexer expansion (C++ header/source/autocoded file parsing, content-type tagging), and prompt strengthening (query-type instructions, enhanced source labels, stronger context-use directive). All changes are deterministic — no LLM calls in the retrieval pipeline.

**Tech Stack:** Python 3.9+, ChromaDB, rank-bm25, nomic-embed-text (ollama), regex-based C++ parsing

**Spec:** `docs/planning/v0.03/2026-03-15-rag-accuracy-improvement-design.md`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `TUI/rag/config.py` | Tier configuration constants (TIERS, DEFAULT_TIER, RERANK_K, KEYWORD_WEIGHT) | Create |
| `TUI/rag/retriever.py` | Retrieval pipeline — RRF, composite scoring, query classification, diversity filter, format_context | Modify |
| `TUI/rag/chunker.py` | Chunking strategies — markdown, fpp, python, C++ headers, C++ source, autocoded API extraction, content-type tagging | Modify |
| `TUI/rag/indexer.py` | Index builder — source acquisition, file routing, metadata storage | Modify |
| `TUI/fprime_ai_client.py` | System prompt — context-use instruction | Modify |
| `tests/rag/test_retriever.py` | Retriever unit tests | Modify |
| `tests/rag/test_chunker.py` | Chunker unit tests | Modify |

---

## Chunk 1: Config and Retriever Foundation

### Task 1: Create config.py with tier constants

**Files:**
- Create: `TUI/rag/config.py`
- Test: `tests/rag/test_config.py`

- [ ] **Step 1: Write the test**

```python
# tests/rag/test_config.py
from rag.config import DEFAULT_TIER, KEYWORD_WEIGHT, RERANK_K, TIERS


def test_tiers_has_three_levels():
    assert set(TIERS.keys()) == {1, 2, 3}


def test_each_tier_has_final_k():
    for tier in TIERS.values():
        assert "final_k" in tier
        assert isinstance(tier["final_k"], int)
        assert tier["final_k"] > 0


def test_tier_final_k_increases_with_level():
    assert TIERS[1]["final_k"] < TIERS[2]["final_k"] < TIERS[3]["final_k"]


def test_default_tier_is_valid():
    assert DEFAULT_TIER in TIERS


def test_rerank_k_is_large_enough():
    max_final_k = max(t["final_k"] for t in TIERS.values())
    # Must accommodate max tier + comparison adjustment (+2)
    assert RERANK_K >= max_final_k + 2


def test_keyword_weight_is_positive():
    assert 0 < KEYWORD_WEIGHT <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rag.config'`

- [ ] **Step 3: Write the implementation**

```python
# TUI/rag/config.py
"""RAG tier configuration. Imported by retriever.py."""

from typing import Any

TIERS: dict[int, dict[str, Any]] = {
    1: {"final_k": 5, "label": "lightweight", "target_models": "≤8B"},
    2: {"final_k": 7, "label": "standard", "target_models": "14B–32B"},
    3: {"final_k": 10, "label": "full", "target_models": "70B+"},
}

DEFAULT_TIER: int = 1

RERANK_K: int = 50  # Fixed — large enough for all tiers + query adjustments

KEYWORD_WEIGHT: float = 0.3  # Multiplicative tiebreaker: score *= (1 + kw * weight)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_config.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/config.py tests/rag/test_config.py
git commit -m "feat(rag): add tier configuration constants"
```

---

### Task 2: Add source-category boosting function

**Files:**
- Modify: `TUI/rag/retriever.py`
- Test: `tests/rag/test_retriever.py`

**Context:** The `get_source_category()` function maps a chunk's `source_file` path to a category string. `get_source_category_boost()` returns the multiplicative boost for that category. These are pure functions with no dependencies on the index.

- [ ] **Step 1: Write the tests**

Append to `tests/rag/test_retriever.py`:

```python
from rag.retriever import get_source_category, get_source_category_boost


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py::test_get_source_category_framework_core -v`
Expected: FAIL with `ImportError: cannot import name 'get_source_category'`

- [ ] **Step 3: Write the implementation**

Add to `TUI/rag/retriever.py` after the `extract_keywords` function (after line 65):

```python
# Source-category boost weights — applied at retrieval time, not stored in index.
# Categories are matched by prefix against the chunk's source_file path.
_SOURCE_CATEGORY_RULES: list[tuple[str, str]] = [
    # Order matters: first match wins. More specific patterns first.
    ("FppTestProject/", "test_projects"),
    ("fprime-tools/", "tools"),
    ("Fw/", "framework_core"),
    ("Os/", "framework_core"),
    ("Svc/Cmd", "framework_core"),
    ("Svc/Health", "framework_core"),
    ("docs/getting-started/", "docs_tutorial"),
    ("docs/how-to/", "docs_tutorial"),
    ("docs/reference/", "docs_reference"),
    ("docs/user-manual/", "docs_reference"),
]

_SOURCE_CATEGORY_BOOSTS: dict[str, float] = {
    "framework_core": 1.3,
    "docs_tutorial": 1.2,
    "docs_reference": 1.15,
    "fpp_spec": 1.25,
    "service_docs": 1.0,
    "test_projects": 0.85,
    "tools": 0.9,
}


def get_source_category(source_file: str) -> str:
    """Map a source_file path to its category. Computed at retrieval time."""
    if source_file.endswith(".fpp"):
        return "fpp_spec"
    for prefix, category in _SOURCE_CATEGORY_RULES:
        if source_file.startswith(prefix):
            return category
    if source_file.startswith("Svc/") and "/docs/" in source_file:
        return "service_docs"
    return "service_docs"  # Unknown paths get neutral boost


def get_source_category_boost(source_file: str) -> float:
    """Return the boost multiplier for a source file's category."""
    category = get_source_category(source_file)
    return _SOURCE_CATEGORY_BOOSTS.get(category, 1.0)
```

- [ ] **Step 4: Run all retriever tests to verify they pass**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py -v`
Expected: all PASS (existing tests unaffected, new tests pass)

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/retriever.py tests/rag/test_retriever.py
git commit -m "feat(rag): add source-category boosting functions"
```

---

### Task 3: Add content-type boosting function

**Files:**
- Modify: `TUI/rag/retriever.py`
- Test: `tests/rag/test_retriever.py`

**Context:** `get_content_type_boost()` returns a boost multiplier based on whether a chunk's `content_type` matches the query type. It's a pure function — just a lookup table.

- [ ] **Step 1: Write the tests**

Append to `tests/rag/test_retriever.py`:

```python
from rag.retriever import get_content_type_boost


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py::test_content_type_boost_code_for_code_seeking -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the implementation**

Add to `TUI/rag/retriever.py` after the source-category functions:

```python
# Content-type boost — matches chunk content_type to query_type.
_CONTENT_TYPE_BOOSTS: dict[str, dict[str, float]] = {
    "code_seeking": {"code": 1.2, "reference": 1.2},
    "concept_seeking": {"concept": 1.2, "tutorial": 1.2},
    "comparison": {"concept": 1.1, "reference": 1.1},
}


def get_content_type_boost(content_type: str, query_type: str) -> float:
    """Return boost multiplier for a content_type given the query_type."""
    boosts = _CONTENT_TYPE_BOOSTS.get(query_type, {})
    return boosts.get(content_type, 1.0)
```

- [ ] **Step 4: Run all retriever tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/retriever.py tests/rag/test_retriever.py
git commit -m "feat(rag): add content-type boosting function"
```

---

### Task 4: Add query-type classifier

**Files:**
- Modify: `TUI/rag/retriever.py`
- Test: `tests/rag/test_retriever.py`

**Context:** `classify_query()` takes the query text and a `known_entities` set, returns a `(query_type, target_entity)` tuple. Uses regex/keyword heuristics only — no LLM. Precedence: file_specific > component_specific > comparison > code_seeking > concept_seeking > general.

- [ ] **Step 1: Write the tests**

Append to `tests/rag/test_retriever.py`:

```python
from rag.retriever import classify_query


def test_classify_query_file_specific():
    entities = {"filemanager", "health", "cmddispatcher"}
    qtype, entity = classify_query("Explain the FileManager/docs/sdd.md file", entities)
    assert qtype == "file_specific"
    assert entity == "filemanager"


def test_classify_query_file_extension():
    entities = set()
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
    entities = set()
    qtype, _ = classify_query("What is the difference between active and passive components?", entities)
    assert qtype == "comparison"


def test_classify_query_comparison_vs():
    entities = set()
    qtype, _ = classify_query("Active vs passive components", entities)
    assert qtype == "comparison"


def test_classify_query_code_seeking():
    entities = set()
    qtype, _ = classify_query("How to implement a command handler?", entities)
    assert qtype == "code_seeking"


def test_classify_query_code_seeking_example():
    entities = set()
    qtype, _ = classify_query("Show me an example of telemetry write", entities)
    assert qtype == "code_seeking"


def test_classify_query_concept_seeking():
    entities = set()
    qtype, _ = classify_query("What is a rate group?", entities)
    assert qtype == "concept_seeking"


def test_classify_query_general():
    entities = set()
    qtype, _ = classify_query("Tell me about fprime", entities)
    assert qtype == "general"


def test_classify_query_precedence_component_over_comparison():
    # "FileManager" is a known CamelCase entity AND "difference" is present
    # Component-specific has higher precedence than comparison
    entities = {"filemanager"}
    qtype, _ = classify_query("What is the difference in FileManager?", entities)
    assert qtype == "component_specific"


def test_classify_query_precedence_comparison_over_concept():
    entities = set()
    qtype, _ = classify_query("What is the difference between ports and channels?", entities)
    assert qtype == "comparison"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py::test_classify_query_file_specific -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the implementation**

Add to `TUI/rag/retriever.py`:

```python
import re  # already imported at top

# Query-type classification patterns. Checked in precedence order.
_FILE_EXTENSION_PATTERN = re.compile(r"\b[\w/]+\.\w{1,4}\b")
_COMPARISON_PATTERNS = re.compile(
    r"\b(?:difference|differences|differ|vs\.?|versus|compare|comparing|comparison|between\s+\w+\s+and)\b",
    re.IGNORECASE,
)
_CODE_SEEKING_PATTERNS = re.compile(
    r"\b(?:how\s+to\s+implement|how\s+to\s+write|how\s+to\s+create|how\s+to\s+add|"
    r"example|syntax|code\s+for|write\s+a|implement|show\s+me|snippet)\b",
    re.IGNORECASE,
)
_CONCEPT_SEEKING_PATTERNS = re.compile(
    r"\b(?:what\s+is|what\s+are|explain|describe|overview|purpose\s+of|define)\b",
    re.IGNORECASE,
)


def classify_query(
    text: str, known_entities: set[str]
) -> tuple[str, str]:
    """
    Classify a query into a type using keyword/regex heuristics.

    Returns (query_type, target_entity). target_entity is non-empty only
    for file_specific and component_specific types.

    Precedence: file_specific > component_specific > comparison >
                code_seeking > concept_seeking > general
    """
    text_lower = text.lower()

    # 1. File-specific: check for file extensions or known entity names
    if _FILE_EXTENSION_PATTERN.search(text):
        # Extract potential entity from filename
        for entity in known_entities:
            if entity in text_lower:
                return ("file_specific", entity)
        return ("file_specific", "")

    # 2. Component-specific: CamelCase identifiers that exist in the index
    for word in re.findall(r"\b[A-Z][a-zA-Z0-9]*[a-z][A-Z][a-zA-Z0-9]*\b", text):
        word_lower = word.lower()
        if word_lower in known_entities:
            return ("component_specific", word_lower)

    # Also check for non-CamelCase entity matches (e.g., user writes "Health")
    # Use word boundaries to avoid substring false positives ("os" matching "most")
    for entity in known_entities:
        if len(entity) < 3:
            continue  # Skip short names like "os", "fw" — too many false positives
        if re.search(r"\b" + re.escape(entity) + r"\b", text_lower):
            return ("component_specific", entity)

    # 3. Comparison
    if _COMPARISON_PATTERNS.search(text):
        return ("comparison", "")

    # 4. Code-seeking
    if _CODE_SEEKING_PATTERNS.search(text):
        return ("code_seeking", "")

    # 5. Concept-seeking
    if _CONCEPT_SEEKING_PATTERNS.search(text):
        return ("concept_seeking", "")

    # 6. General
    return ("general", "")
```

- [ ] **Step 4: Run all retriever tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/retriever.py tests/rag/test_retriever.py
git commit -m "feat(rag): add query-type classifier with precedence ordering"
```

---

### Task 5: Refactor RRF to return scores and add composite_score

**Files:**
- Modify: `TUI/rag/retriever.py`
- Modify: `tests/rag/test_retriever.py`

**Context:** Currently `reciprocal_rank_fusion()` returns `list[str]` (IDs only). Must return `dict[str, float]` (ID → score) so composite scoring can multiply boosts onto the RRF base score. The existing `keyword_score` re-sort is replaced by the composite function.

- [ ] **Step 1: Update existing RRF tests for new return type**

Replace the three existing RRF tests in `tests/rag/test_retriever.py`:

```python
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
```

- [ ] **Step 2: Add composite_score test**

Append to `tests/rag/test_retriever.py`:

```python
from rag.retriever import composite_score


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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py::test_rrf_merges_two_lists tests/rag/test_retriever.py::test_composite_score_combines_signals_multiplicatively -v`
Expected: FAIL (RRF returns list not dict, composite_score not defined)

- [ ] **Step 4: Refactor reciprocal_rank_fusion return type**

In `TUI/rag/retriever.py`, change `reciprocal_rank_fusion` (currently lines 76-83):

```python
def reciprocal_rank_fusion(dense_ids: list[str], sparse_ids: list[str]) -> dict[str, float]:
    """Merge two ranked lists using Reciprocal Rank Fusion. Returns {id: score}."""
    scores: dict[str, float] = {}
    for rank, doc_id in enumerate(dense_ids):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (RRF_K + rank + 1)
    for rank, doc_id in enumerate(sparse_ids):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (RRF_K + rank + 1)
    return scores
```

- [ ] **Step 5: Add composite_score function**

Add after `get_content_type_boost`:

```python
from rag.config import KEYWORD_WEIGHT


def composite_score(
    rrf_score: float,
    chunk: dict,
    keywords: list[str],
    query_type: str,
) -> float:
    """Combine all ranking signals into a single score per candidate."""
    score = rrf_score
    score *= get_source_category_boost(chunk["source_file"])
    score *= get_content_type_boost(chunk.get("content_type", ""), query_type)
    score *= (1 + keyword_score(chunk["text"], keywords) * KEYWORD_WEIGHT)
    return score
```

- [ ] **Step 6: Run all retriever tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add TUI/rag/retriever.py tests/rag/test_retriever.py
git commit -m "refactor(rag): RRF returns scores dict, add composite_score function"
```

---

### Task 6: Add adaptive diversity filter

**Files:**
- Modify: `TUI/rag/retriever.py`
- Test: `tests/rag/test_retriever.py`

**Context:** The diversity filter limits how many chunks from the same source file can appear in the final results. The limit varies by query type: file_specific/component_specific allow up to FINAL_K from the target; comparison allows max 1; others allow max 2.

- [ ] **Step 1: Write the tests**

Append to `tests/rag/test_retriever.py`:

```python
from rag.retriever import apply_diversity_filter


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py::test_diversity_filter_general_max_2 -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the implementation**

Add to `TUI/rag/retriever.py`:

```python
# Diversity limits per query type.
_DIVERSITY_LIMITS: dict[str, int] = {
    "file_specific": -1,      # -1 means no limit (up to FINAL_K)
    "component_specific": -1,
    "comparison": 1,
    "code_seeking": 2,
    "concept_seeking": 2,
    "general": 2,
}


def apply_diversity_filter(
    candidates: list[dict],
    query_type: str,
    target_entity: str,
    final_k: int,
) -> list[dict]:
    """
    Filter candidates to limit chunks per source file.

    Candidates must be pre-sorted by score (descending).
    For file_specific/component_specific, the target entity's source files
    are exempt from the limit.
    """
    max_per_source = _DIVERSITY_LIMITS.get(query_type, 2)
    source_counts: dict[str, int] = {}
    result: list[dict] = []

    for chunk in candidates:
        src = chunk["source_file"]
        count = source_counts.get(src, 0)

        # Check if this source is the target entity (exempt from limit)
        is_target = False
        if target_entity and query_type in ("file_specific", "component_specific"):
            is_target = target_entity in src.lower()

        if is_target or max_per_source == -1 or count < max_per_source:
            result.append(chunk)
            source_counts[src] = count + 1

    return result
```

- [ ] **Step 4: Run all retriever tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/retriever.py tests/rag/test_retriever.py
git commit -m "feat(rag): add adaptive diversity filter by query type"
```

---

### Task 7: Update format_context with content_type label

**Files:**
- Modify: `TUI/rag/retriever.py`
- Modify: `tests/rag/test_retriever.py`

**Context:** The `format_context()` function currently outputs `[SOURCE: path | type: chunk_type]`. Add the `content_type` field: `[SOURCE: path | type: chunk_type | content: content_type]`.

- [ ] **Step 1: Update the existing test**

Replace `test_format_context_produces_labeled_blocks` in `tests/rag/test_retriever.py`:

```python
def test_format_context_produces_labeled_blocks():
    chunks = [
        {"text": "Port definitions here.", "source_file": "Fw/Com.fpp", "chunk_type": "fpp_block", "content_type": "code"},
        {"text": "How to connect.", "source_file": "docs/guide.md", "chunk_type": "markdown", "content_type": "concept"},
    ]
    context = format_context(chunks)
    assert "[SOURCE: Fw/Com.fpp | type: fpp_block | content: code]" in context
    assert "[SOURCE: docs/guide.md | type: markdown | content: concept]" in context
    assert "Port definitions here." in context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py::test_format_context_produces_labeled_blocks -v`
Expected: FAIL (old format doesn't include content_type)

- [ ] **Step 3: Update format_context**

In `TUI/rag/retriever.py`, replace the `format_context` function:

```python
def format_context(chunks: list[dict], query_type: str = "general") -> str:
    """Format retrieved chunks into labeled context blocks for the prompt."""
    # Query-type instruction prefix
    _QUERY_INSTRUCTIONS: dict[str, str] = {
        "code_seeking": "Prioritize code examples and exact syntax from the sources below.",
        "concept_seeking": "Explain the concept using the sources below. Cite specific F' terminology.",
        "file_specific": "Answer using the content from the requested file below.",
        "comparison": "Compare using specific details from the sources below.",
    }
    blocks = []
    instruction = _QUERY_INSTRUCTIONS.get(query_type, "")
    if instruction:
        blocks.append(instruction)
    for chunk in chunks:
        content_type = chunk.get("content_type", "")
        header = f"[SOURCE: {chunk['source_file']} | type: {chunk['chunk_type']} | content: {content_type}]"
        blocks.append(f"{header}\n{chunk['text']}")
    return "\n\n".join(blocks)
```

- [ ] **Step 4: Run all retriever tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/retriever.py tests/rag/test_retriever.py
git commit -m "feat(rag): add content_type and query instruction to format_context"
```

---

### Task 8: Rewire the query() function with new pipeline

**Files:**
- Modify: `TUI/rag/retriever.py`

**Context:** This is the big integration step. The `query()` function currently uses the old pipeline (RRF → keyword sort → take FINAL_K=3). Replace it with the new pipeline: classify_query → RRF (returns scores) → composite scoring → sort → diversity filter → take tiered FINAL_K. Also build the `known_entities` set from loaded chunks.

- [ ] **Step 1: Update the query() function**

Replace the entire `query()` function in `TUI/rag/retriever.py`:

```python
from typing import Optional

from rag.config import DEFAULT_TIER, RERANK_K, TIERS

# Module-level cache for known entities (built once on first query)
_known_entities: Optional[set[str]] = None


def _build_known_entities(chunks: dict[str, dict]) -> set[str]:
    """Extract entity names from chunk metadata for query classification."""
    entities: set[str] = set()
    for chunk in chunks.values():
        # From component_name
        name = chunk.get("component_name", "")
        if name:
            entities.add(name.lower())
        # From source_file: extract last dir before /docs/ or filename stem
        src = chunk.get("source_file", "")
        parts = src.replace("\\", "/").split("/")
        for i, part in enumerate(parts):
            if part == "docs" and i > 0:
                entities.add(parts[i - 1].lower())
                break
        else:
            # No /docs/ — use filename stem
            if parts:
                stem = parts[-1].rsplit(".", 1)[0]
                if stem:
                    entities.add(stem.lower())
    return entities


def query(text: str, tier: int = DEFAULT_TIER) -> dict:
    """
    Public interface for the TUI.
    Returns {"answer_context": str, "sources": list[str], "query_type": str}
    Raises FileNotFoundError if index has not been built yet.
    """
    global _known_entities

    if not os.path.exists(BM25_PATH):
        raise FileNotFoundError(
            "RAG index not found. Run: python -m rag.indexer"
        )

    collection, bm25_data = _load_index()
    all_chunks: dict[str, dict] = bm25_data["chunks"]
    bm25: BM25Okapi = bm25_data["bm25"]
    chunk_ids: list[str] = bm25_data["ids"]

    # Build known_entities cache on first call
    if _known_entities is None:
        _known_entities = _build_known_entities(all_chunks)

    # 1. Classify query
    query_type, target_entity = classify_query(text, _known_entities)

    # 2. Dense retrieval
    query_embedding = _embed(text)
    dense_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(DENSE_K, collection.count()),
    )
    dense_ids = dense_results["ids"][0]

    # 3. Sparse retrieval
    tokenized = tokenize(text)
    bm25_scores = bm25.get_scores(tokenized)
    top_sparse_indices = sorted(
        range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
    )[:SPARSE_K]
    sparse_ids = [chunk_ids[i] for i in top_sparse_indices]

    # 4. RRF merge → dict[str, float]
    rrf_scores = reciprocal_rank_fusion(dense_ids, sparse_ids)

    # Take top RERANK_K candidates
    sorted_by_rrf = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:RERANK_K]
    candidates = []
    for cid in sorted_by_rrf:
        if cid in all_chunks:
            chunk = dict(all_chunks[cid])  # copy to avoid mutating index
            chunk["_rrf_score"] = rrf_scores[cid]
            candidates.append(chunk)

    # 5. Composite scoring
    kws = extract_keywords(text)
    for c in candidates:
        c["_score"] = composite_score(c["_rrf_score"], c, kws, query_type)

    # 6. Sort by composite score
    candidates.sort(key=lambda c: c["_score"], reverse=True)

    # 7. Adaptive diversity filter
    tier_config = TIERS.get(tier, TIERS[DEFAULT_TIER])
    base_k = tier_config["final_k"]
    # Comparison queries get +2
    final_k = base_k + 2 if query_type == "comparison" else base_k
    candidates = apply_diversity_filter(candidates, query_type, target_entity, final_k)

    # 8. Take top FINAL_K
    top_chunks = candidates[:final_k]

    # 9. Format with query-type instruction
    return {
        "answer_context": format_context(top_chunks, query_type),
        "sources": [c["source_file"] for c in top_chunks],
        "query_type": query_type,
    }
```

- [ ] **Step 2: Update constant declarations at top of file**

Remove the old `FINAL_K` and `RERANK_K` constants (lines 13-14). The `RERANK_K` now comes from `config.py`. `FINAL_K` is no longer a module constant — it's computed per-query from the tier config.

Update the imports at the top of the file:

```python
from rag.config import DEFAULT_TIER, KEYWORD_WEIGHT, RERANK_K, TIERS
```

- [ ] **Step 3: Run all retriever tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_retriever.py -v`
Expected: all PASS

- [ ] **Step 4: Run full test suite to check for regressions**

Run: `PYTHONPATH=./TUI python -m pytest tests/ -v`
Expected: all PASS (app.py tests use MockAIClient, no real RAG calls)

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/retriever.py
git commit -m "feat(rag): rewire query() with composite scoring and tiered FINAL_K"
```

---

## Chunk 2: Chunker Improvements

### Task 9: Add content-type detection function

**Files:**
- Modify: `TUI/rag/chunker.py`
- Test: `tests/rag/test_chunker.py`

**Context:** Each chunk gets a `content_type` field (`code`, `concept`, `reference`, `tutorial`) based on heuristics. This is a pure function that examines the chunk text and source file extension.

- [ ] **Step 1: Write the tests**

Append to `tests/rag/test_chunker.py`:

```python
from rag.chunker import detect_content_type


def test_detect_content_type_code_by_extension():
    assert detect_content_type("int main() {}", "main.cpp") == "code"
    assert detect_content_type("component A {}", "A.fpp") == "code"
    assert detect_content_type("class Foo:", "foo.py") == "code"


def test_detect_content_type_code_by_fenced_blocks():
    text = "Some text\n```cpp\nint x = 5;\nint y = 10;\nint z = 15;\n```\nMore text"
    assert detect_content_type(text, "guide.md") == "code"


def test_detect_content_type_concept():
    text = "## Overview\nF Prime is a flight software framework designed for reusability and portability."
    assert detect_content_type(text, "overview.md") == "concept"


def test_detect_content_type_reference_table():
    text = "| Parameter | Type | Default |\n|---|---|---|\n| timeout | int | 5 |"
    assert detect_content_type(text, "config.md") == "reference"


def test_detect_content_type_tutorial():
    text = "1. First, create the component\n2. Then, add ports\n3. Finally, build"
    assert detect_content_type(text, "docs/how-to/add-comp.md") == "tutorial"


def test_detect_content_type_tutorial_by_path():
    text = "Some general text about setup."
    assert detect_content_type(text, "docs/getting-started/install.md") == "tutorial"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py::test_detect_content_type_code_by_extension -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the implementation**

Add to `TUI/rag/chunker.py`:

```python
_CODE_EXTENSIONS = {".fpp", ".hpp", ".h", ".cpp", ".py"}


def detect_content_type(text: str, source_file: str) -> str:
    """Classify chunk content as code, concept, reference, or tutorial."""
    # 1. Code files by extension
    for ext in _CODE_EXTENSIONS:
        if source_file.endswith(ext):
            return "code"

    # 2. Tutorial by path
    if "how-to/" in source_file or "getting-started/" in source_file:
        return "tutorial"

    lines = text.strip().split("\n")
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return "concept"

    # 3. Code by fenced block ratio (>50% of lines inside ```)
    in_fence = False
    code_lines = 0
    for line in non_empty:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            code_lines += 1
    if code_lines > len(non_empty) / 2:
        return "code"

    # 4. Reference: tables or enum-like listings
    table_lines = sum(1 for line in non_empty if "|" in line and line.strip().startswith("|"))
    if table_lines > 2:
        return "reference"

    # 5. Tutorial: numbered steps
    numbered = sum(1 for line in non_empty if re.match(r"^\s*\d+[\.\)]\s", line))
    if numbered >= 3:
        return "tutorial"

    return "concept"
```

- [ ] **Step 4: Run all chunker tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/chunker.py tests/rag/test_chunker.py
git commit -m "feat(rag): add content-type detection for chunks"
```

---

### Task 10: Add content_type to all existing chunk functions

**Files:**
- Modify: `TUI/rag/chunker.py`
- Modify: `tests/rag/test_chunker.py`

**Context:** Every chunk dict must now include `content_type`. Update `chunk_markdown`, `chunk_fpp`, and `chunk_python` to call `detect_content_type` and include the result.

- [ ] **Step 1: Write the test**

Append to `tests/rag/test_chunker.py`:

```python
def test_chunk_markdown_includes_content_type():
    text = "## Overview\nF Prime is a framework for flight software."
    chunks = chunk_markdown(text, source="overview.md")
    assert "content_type" in chunks[0]
    assert chunks[0]["content_type"] == "concept"


def test_chunk_fpp_content_type_is_code():
    text = "component A {\n  port p: Fw.Com\n}"
    chunks = chunk_fpp(text, source="Comp.fpp")
    assert chunks[0]["content_type"] == "code"


def test_chunk_python_content_type_is_code():
    text = "class Foo:\n    def bar(self):\n        pass\n"
    chunks = chunk_python(text, source="example.py")
    assert chunks[0]["content_type"] == "code"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py::test_chunk_markdown_includes_content_type -v`
Expected: FAIL with `KeyError: 'content_type'`

- [ ] **Step 3: Update chunk functions**

In `TUI/rag/chunker.py`, add `content_type` to each chunk dict in `chunk_markdown`, `chunk_fpp`, and `chunk_python`:

For `chunk_markdown` (update the `chunks.append` call):
```python
        truncated = _truncate(section)
        chunks.append({
            "text": truncated,
            "source_file": source,
            "chunk_type": "markdown",
            "component_name": "",
            "content_type": detect_content_type(truncated, source),
        })
```

For `chunk_fpp` (both the match branch and fallback):
```python
        chunks.append({
            "text": _truncate(block),
            "source_file": source,
            "chunk_type": "fpp_block",
            "component_name": name,
            "content_type": "code",
        })
```

For `chunk_python`:
```python
        chunks.append({
            "text": _truncate(section),
            "source_file": source,
            "chunk_type": "python",
            "component_name": "",
            "content_type": "code",
        })
```

- [ ] **Step 4: Run all chunker tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/chunker.py tests/rag/test_chunker.py
git commit -m "feat(rag): add content_type field to all chunk functions"
```

---

### Task 11: Add C++ header/source chunker

**Files:**
- Modify: `TUI/rag/chunker.py`
- Test: `tests/rag/test_chunker.py`

**Context:** New `chunk_cpp()` function splits hand-written `.hpp`/`.cpp` files on class/struct, enum, and namespace boundaries. Preserves enclosing namespace/class as context prefix. Skips preprocessor noise.

**Known limitation:** The regex splitter splits at every `class/struct/enum` keyword, including enums nested inside classes. This can separate a class from its inner enum members. Acceptable for v0.03 — the chunks are still indexed and searchable, just not perfectly grouped. Can be improved with brace-depth tracking in a future iteration.

- [ ] **Step 1: Write the tests**

Append to `tests/rag/test_chunker.py`:

```python
from rag.chunker import chunk_cpp


def test_chunk_cpp_splits_on_class():
    text = """
#ifndef GUARD_HPP
#define GUARD_HPP

#include <FpConfig.hpp>

namespace Os {

class Task {
  public:
    enum State { RUNNING, IDLE, EXITED };
    void start();
    void stop();
};

class Mutex {
  public:
    void lock();
    void unlock();
};

}  // namespace Os
"""
    chunks = chunk_cpp(text, source="Os/Task/Task.hpp")
    # Should get chunks for Task and Mutex classes
    assert len(chunks) >= 2
    # Task class chunk should mention namespace
    task_chunk = [c for c in chunks if "Task" in c["text"]][0]
    assert "Os" in task_chunk["text"]  # namespace context preserved
    assert task_chunk["content_type"] == "code"
    assert task_chunk["source_file"] == "Os/Task/Task.hpp"


def test_chunk_cpp_splits_on_enum():
    text = """
namespace Fw {

enum class CmdResponse {
    OK,
    VALIDATION_ERROR,
    EXECUTION_ERROR,
};

}  // namespace Fw
"""
    chunks = chunk_cpp(text, source="Fw/Cmd/CmdResponse.hpp")
    assert len(chunks) >= 1
    assert "CmdResponse" in chunks[0]["text"]


def test_chunk_cpp_skips_preprocessor():
    text = """
#ifndef GUARD
#define GUARD
#include <stdio.h>
#include "FpConfig.hpp"

class Foo {
  public:
    void bar();
};
#endif
"""
    chunks = chunk_cpp(text, source="test.hpp")
    for chunk in chunks:
        assert "#ifndef" not in chunk["text"]
        assert "#define GUARD" not in chunk["text"]
        assert "#include" not in chunk["text"]


def test_chunk_cpp_fallback_whole_file():
    # If no class/enum/namespace found, treat whole file as one chunk
    text = "void standalone_function() { return; }"
    chunks = chunk_cpp(text, source="util.cpp")
    assert len(chunks) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py::test_chunk_cpp_splits_on_class -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the implementation**

Add to `TUI/rag/chunker.py`:

```python
# Patterns for C++ chunking
_CPP_PREPROCESSOR = re.compile(r"^\s*#\s*(?:ifndef|define|endif|include|pragma)\b.*$", re.MULTILINE)
_CPP_NAMESPACE = re.compile(r"namespace\s+([\w:]+)\s*\{")
_CPP_CLASS_OR_STRUCT = re.compile(r"(?:class|struct)\s+(\w+)(?:\s*:\s*(?:public|protected|private)\s+[\w:]+)?\s*\{")
_CPP_ENUM = re.compile(r"enum\s+(?:class\s+)?(\w+)\s*\{")
_CPP_SPLIT = re.compile(r"(?=(?:class|struct|enum)\s+\w+)")


def chunk_cpp(text: str, source: str) -> list[dict]:
    """Split C++ header/source files on class, struct, and enum boundaries."""
    # Strip preprocessor lines
    cleaned = _CPP_PREPROCESSOR.sub("", text)

    # Detect enclosing namespace for context prefix
    ns_match = _CPP_NAMESPACE.search(cleaned)
    ns_prefix = f"namespace {ns_match.group(1)} :: " if ns_match else ""

    # Split on class/struct/enum declarations
    sections = _CPP_SPLIT.split(cleaned)
    chunks: list[dict] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Determine component name from class/struct/enum
        comp_name = ""
        class_match = _CPP_CLASS_OR_STRUCT.search(section)
        enum_match = _CPP_ENUM.search(section)
        if class_match:
            comp_name = class_match.group(1)
        elif enum_match:
            comp_name = enum_match.group(1)

        # Only keep sections that contain a declaration (skip preamble noise)
        if not comp_name:
            continue

        # Prepend namespace context
        chunk_text = f"{ns_prefix}{section}" if ns_prefix else section

        chunks.append({
            "text": _truncate(chunk_text),
            "source_file": source,
            "chunk_type": "cpp",
            "component_name": comp_name,
            "content_type": "code",
        })

    if not chunks:
        # Fallback: whole file as one chunk
        chunks.append({
            "text": _truncate(cleaned),
            "source_file": source,
            "chunk_type": "cpp",
            "component_name": "",
            "content_type": "code",
        })

    return chunks
```

- [ ] **Step 4: Run all chunker tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/chunker.py tests/rag/test_chunker.py
git commit -m "feat(rag): add C++ header/source chunker"
```

---

### Task 12: Add autocoded file API extraction chunker

**Files:**
- Modify: `TUI/rag/chunker.py`
- Test: `tests/rag/test_chunker.py`

**Context:** `chunk_autocoded_cpp()` extracts only public/protected method signatures from `*Ac.hpp`/`*Ac.cpp` files. Skips serialization boilerplate, dispatch logic, constructors/destructors. Groups signatures by component.

- [ ] **Step 1: Write the tests**

Append to `tests/rag/test_chunker.py`:

```python
from rag.chunker import chunk_autocoded_cpp


def test_chunk_autocoded_api_extracts_signatures():
    text = """
class HealthComponentBase : public Fw::ActiveComponentBase {
  public:
    HealthComponentBase(const char* name);
    ~HealthComponentBase();
    void init(NATIVE_INT_TYPE instance = 0);

  protected:
    void log_WARNING_HI_PingLate(const Fw::StringBase& entry);
    void tlmWrite_PingLateWarnings(U32 count);
    void cmdResponse_out(FwOpcodeType opCode, U32 cmdSeq, Fw::CmdResponse response);
    void pingIn_handler(NATIVE_INT_TYPE portNum, U32 key);

  private:
    void m_p_cmdIn_in(Fw::PassiveComponentBase* callComp, FwIndexType portNum);
    FW_SERIALIZE_STATUS serialize();
};
"""
    chunks = chunk_autocoded_cpp(text, source="Svc/Health/HealthComponentAc.hpp")
    assert len(chunks) >= 1
    chunk_text = chunks[0]["text"]
    # Should include protected methods (the API surface)
    assert "log_WARNING_HI_PingLate" in chunk_text
    assert "tlmWrite_PingLateWarnings" in chunk_text
    assert "cmdResponse_out" in chunk_text
    assert "pingIn_handler" in chunk_text
    # Should skip private methods and constructors
    assert "m_p_cmdIn_in" not in chunk_text
    assert "serialize" not in chunk_text
    assert chunks[0]["chunk_type"] == "cpp_api"


def test_chunk_autocoded_skips_boilerplate():
    text = """
class FooComponentBase {
  public:
    FooComponentBase(const char* name);
    ~FooComponentBase();

  protected:
    void log_ACTIVITY_HI_SomeEvent(U32 arg);

  private:
    void dispatchMsg(ComponentIpcSerializableBuffer& msg);
    FW_SERIALIZE_STATUS __serialize(NATIVE_INT_TYPE id);
    void __deserialize(Fw::SerialBuffer& buffer);
};
"""
    chunks = chunk_autocoded_cpp(text, source="FooAc.hpp")
    chunk_text = chunks[0]["text"]
    assert "log_ACTIVITY_HI_SomeEvent" in chunk_text
    assert "dispatchMsg" not in chunk_text
    assert "__serialize" not in chunk_text


def test_chunk_autocoded_empty_api():
    text = """
class BarBase {
  private:
    void internal();
};
"""
    chunks = chunk_autocoded_cpp(text, source="BarAc.hpp")
    # Even with no public/protected methods, should return something
    assert len(chunks) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py::test_chunk_autocoded_api_extracts_signatures -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the implementation**

Add to `TUI/rag/chunker.py`:

```python
_AC_METHOD_PATTERN = re.compile(
    r"^\s+(?:virtual\s+)?(?:[\w:]+\s+)+(\w+)\s*\([^)]*\)(?:\s*(?:const|override|=\s*0))?\s*;",
    re.MULTILINE,
)
# Skip patterns: constructors, destructors, serialization, dispatch, private helpers
_AC_SKIP_PATTERNS = re.compile(
    r"(?:~?\w+ComponentBase|serialize|deserialize|dispatchMsg|__\w+|m_p_\w+)"
)


def chunk_autocoded_cpp(text: str, source: str) -> list[dict]:
    """Extract public/protected API signatures from autocoded *Ac.hpp/*Ac.cpp files."""
    # Find class name
    class_match = _CPP_CLASS_OR_STRUCT.search(text)
    comp_name = class_match.group(1) if class_match else ""

    # Extract sections by visibility
    # Split into public/protected/private sections
    signatures: list[str] = []
    in_api_section = False

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("public:") or stripped.startswith("protected:"):
            in_api_section = True
            continue
        elif stripped.startswith("private:"):
            in_api_section = False
            continue

        if not in_api_section:
            continue

        # Check if line looks like a method signature
        method_match = _AC_METHOD_PATTERN.match(line)
        if method_match:
            method_name = method_match.group(1)
            # Skip constructors, destructors, serialization boilerplate
            if _AC_SKIP_PATTERNS.search(method_name):
                continue
            signatures.append(stripped.rstrip(";").strip())

    if signatures:
        header = f"Component {comp_name} API:" if comp_name else "API:"
        sig_text = header + "\n" + "\n".join(f"  {sig}" for sig in signatures)
    else:
        sig_text = f"Component {comp_name}: no public/protected API extracted" if comp_name else text[:200]

    return [{
        "text": _truncate(sig_text),
        "source_file": source,
        "chunk_type": "cpp_api",
        "component_name": comp_name.replace("ComponentBase", "").replace("Base", ""),
        "content_type": "reference",
    }]
```

- [ ] **Step 4: Run all chunker tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/chunker.py tests/rag/test_chunker.py
git commit -m "feat(rag): add autocoded file API extraction chunker"
```

---

### Task 13: Add FPP spec larger chunk support

**Files:**
- Modify: `TUI/rag/chunker.py`
- Test: `tests/rag/test_chunker.py`

**Context:** FPP spec files (`docs/reference/fpp-*`, `docs/user-manual/fpp-*`) need larger chunks (~500 tokens = 2000 chars) because splitting dense DSL documentation at 1200 chars loses context. The `_truncate()` function already accepts `max_chars` — callers just need to pass it.

- [ ] **Step 1: Write the test**

Append to `tests/rag/test_chunker.py`:

```python
def test_fpp_spec_larger_chunks():
    # Create content longer than 1200 chars but under 2000
    text = "## FPP Keyword: active component\n" + ("x " * 700)  # ~1400 chars
    chunks = chunk_markdown(text, source="docs/reference/fpp-user-guide.md")
    # Should NOT be truncated at 1200 — FPP spec gets 2000 char limit
    assert len(chunks[0]["text"]) > 1200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py::test_fpp_spec_larger_chunks -v`
Expected: FAIL (text truncated at 1200)

- [ ] **Step 3: Update chunk_markdown to use larger limit for FPP specs**

In `TUI/rag/chunker.py`, modify `chunk_markdown`:

```python
_FPP_SPEC_PREFIXES = ("docs/reference/fpp-", "docs/user-manual/fpp-")
FPP_SPEC_MAX_CHARS = 2000  # ~500 tokens — dense DSL docs need larger chunks


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split markdown on ## headers. Each section becomes one chunk."""
    max_chars = FPP_SPEC_MAX_CHARS if source.startswith(_FPP_SPEC_PREFIXES) else TARGET_TOKENS * CHARS_PER_TOKEN
    sections = re.split(r'(?=^#{1,2} )', text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        truncated = _truncate(section, max_chars=max_chars)
        chunks.append({
            "text": truncated,
            "source_file": source,
            "chunk_type": "markdown",
            "component_name": "",
            "content_type": detect_content_type(truncated, source),
        })
    return chunks
```

- [ ] **Step 4: Run all chunker tests**

Run: `PYTHONPATH=./TUI python -m pytest tests/rag/test_chunker.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/chunker.py tests/rag/test_chunker.py
git commit -m "feat(rag): increase chunk size for FPP spec files to 2000 chars"
```

---

## Chunk 3: Indexer Updates and Prompt Improvements

### Task 14: Update indexer to include C++ files

**Files:**
- Modify: `TUI/rag/indexer.py`

**Context:** The indexer currently only processes `.md`, `.fpp`, and `.py` files. Add `.hpp`, `.h`, `.cpp` files with routing: autocoded files (`*Ac.hpp`, `*Ac.cpp`) go to `chunk_autocoded_cpp()`, generated files (`*GTestBase.*`, `*TesterBase.*`) are skipped, everything else goes to `chunk_cpp()`. Also add `content_type` to the metadata stored in ChromaDB.

- [ ] **Step 1: Update imports in indexer.py**

At the top of `TUI/rag/indexer.py`, update the import from `rag.chunker`:

```python
from rag.chunker import (
    chunk_autocoded_cpp,
    chunk_cpp,
    chunk_fpp,
    chunk_markdown,
    chunk_python,
    deduplicate,
)
```

- [ ] **Step 2: Add C++ file routing to collect_chunks()**

In `TUI/rag/indexer.py`, add a helper function and update `collect_chunks()`:

```python
def _is_generated_skip(filename: str) -> bool:
    """Files to skip entirely (generated boilerplate with no RAG value)."""
    return any(pattern in filename for pattern in ("GTestBase", "TesterBase"))


def _is_autocoded(filename: str) -> bool:
    """Autocoded files get API extraction instead of full chunking."""
    return filename.endswith(("Ac.hpp", "Ac.cpp"))
```

In `collect_chunks()`, after the existing `.md/.fpp/.py` loop for the fprime repo, add:

```python
    # C++ files from fprime framework
    for ext in (".hpp", ".h", ".cpp"):
        for f in repo_path.rglob(f"*{ext}"):
            # Skip build artifacts
            rel = str(f.relative_to(repo_path))
            if rel.startswith("build") or "/build/" in rel:
                continue
            try:
                name = f.name
                if _is_generated_skip(name):
                    continue
                text = f.read_text(errors="ignore")
                if _is_autocoded(name):
                    all_chunks.extend(chunk_autocoded_cpp(text, source=rel))
                else:
                    all_chunks.extend(chunk_cpp(text, source=rel))
            except Exception:
                pass
```

- [ ] **Step 3: Update build_index() to store content_type in metadata**

In `TUI/rag/indexer.py`, update the metadata dict in `build_index()`:

```python
        metadatas.append({
            "source_file": str(chunk["source_file"]),
            "chunk_type": str(chunk["chunk_type"]),
            "component_name": str(chunk.get("component_name", "")),
            "content_type": str(chunk.get("content_type", "")),
        })
```

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH=./TUI python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/indexer.py
git commit -m "feat(rag): index C++ headers, sources, and autocoded API signatures"
```

---

### Task 15: Strengthen system prompt and update RAG integration

**Files:**
- Modify: `TUI/fprime_ai_client.py`
- Modify: `TUI/app.py`

**Context:** Strengthen the context-use instruction in the system prompt. No `app.py` changes are needed — `query()` now handles `format_context(top_chunks, query_type)` internally (Task 8), and `app.py` only accesses `rag_result["answer_context"]` and `rag_result["sources"]`, both of which are unchanged.

- [ ] **Step 1: Update system prompt in fprime_ai_client.py**

In `TUI/fprime_ai_client.py`, find the line (around line 21):
```python
"You are an absolute expert in F'. If provided with a '### RELEVANT F' KNOWLEDGE BASE ###' section, treat it as the authoritative source for F' architecture, standards, and code structure.\n\n"
```

Replace with:
```python
"You are an absolute expert in F'. If provided with a '### RELEVANT F' KNOWLEDGE BASE ###' section, you MUST base your answer on the content provided in that section. Do not rely on your general knowledge for F'-specific syntax, API names, or code patterns — use only what appears in the sources. If the sources do not contain enough information, say so.\n\n"
```

- [ ] **Step 2: Run full test suite**

Run: `PYTHONPATH=./TUI python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add TUI/fprime_ai_client.py
git commit -m "feat(rag): strengthen context-use instruction in system prompt"
```

---

### Task 16: Final integration test — run full test suite and lint

**Files:** None (verification only)

- [ ] **Step 1: Run lint**

Run: `make lint`
Expected: no ruff or mypy errors

- [ ] **Step 2: Run full test suite**

Run: `make test`
Expected: all PASS

- [ ] **Step 3: Fix any lint or test failures**

Address any issues found in steps 1-2.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix(rag): address lint and test issues from v0.03 integration"
```

---

## Post-Implementation

After all tasks are complete:

1. **Rebuild the RAG index** to include C++ files and content_type metadata:
   ```bash
   rm -rf TUI/rag/db TUI/rag/raw
   PYTHONPATH=./TUI python -m rag.indexer
   ```

2. **Re-run the 262-question evaluation** to measure before/after accuracy. Compare against the baseline: 75 PASS / 80 PARTIAL / 113 FAIL.

3. **Tune boost weights** if needed — the source-category and content-type boosts in `retriever.py` are starting values. Adjust based on evaluation results.
