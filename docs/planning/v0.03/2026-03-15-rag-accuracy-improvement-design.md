# RAG Accuracy Improvement Design — v0.03

**Date:** 2026-03-15
**Branch:** `rag_implementation`
**Status:** Design approved, pending implementation

---

## Background

The first RAG evaluation (2026-03-14) tested 262 F' training questions against the TUI in MISSION_CONTROL mode. Results: **75 PASS / 80 PARTIAL / 113 FAIL** (29% pass rate).

Root cause analysis identified five systemic issues:

1. **Off-target source retrieval** — "sticky junk" files (e.g., `Svc/FileManager/docs/sdd.md`) win BM25 for generic F' vocabulary, consuming FINAL_K slots with irrelevant content.
2. **Missing source coverage** — C++ headers (`Fw/`, `Os/`), FPP grammar spec, and OSAL files are not indexed or poorly chunked.
3. **Retrieved-but-ignored** — The 8B model falls back to parametric knowledge even when correct sources are in context.
4. **FINAL_K=3 too low** — One bad retrieval eats 33% of the context budget.
5. **No query-type awareness** — Code-seeking queries get concept chunks and vice versa.

**Priority order:** Retrieval quality > Index coverage > Prompt/model behavior.

**Constraints:**
- No LLM calls in the retrieval pipeline (no query rewriting, no LLM-based reranking)
- Must work well at the 8B model floor (qwen3:8b + nomic-embed-text)
- Index rebuild time under ~5 minutes
- Eventually shipped to resource-constrained environments (college student laptops)

---

## Section 1: Retrieval Improvements

Changes to `TUI/rag/retriever.py`.

### 1a. Source-Category Boosting

Each chunk's `source_file` path maps to a category with a boost multiplier applied to the RRF score after fusion, before the keyword re-rank pass.

| Category | Path patterns | Boost | Rationale |
|---|---|---|---|
| `framework_core` | `Fw/`, `Os/`, `Svc/Cmd*`, `Svc/Health*` | 1.3 | Authoritative framework internals |
| `docs_tutorial` | `docs/getting-started/`, `docs/how-to/` | 1.2 | Official tutorials, high signal |
| `docs_reference` | `docs/reference/`, `docs/user-manual/` | 1.15 | Reference docs, good but verbose |
| `fpp_spec` | `*.fpp`, FPP grammar/spec files | 1.25 | DSL source of truth |
| `service_docs` | `Svc/*/docs/sdd.md` | 1.0 | Neutral — relevant when on-topic, noise when off |
| `test_projects` | `FppTestProject/`, `*test*` | 0.85 | Useful examples but narrow scope |
| `tools` | `fprime-tools/` | 0.9 | Build tooling, rarely the answer |

The boost multiplies into the RRF score *after* fusion, *before* the keyword re-rank pass. This influences final ordering without overriding strong semantic matches.

**Implementation note:** `source_category` is computed at retrieval time by pattern-matching the chunk's `source_file` path — it is NOT stored as index metadata. This avoids re-indexing when category weights are tuned. A `get_source_category(source_file: str) -> str` function maps paths to categories.

### 1b. Adaptive Diversity Filter

A query-type classifier (`classify_query(text)`) categorizes each query using keyword/regex heuristics (no LLM). The diversity filter and FINAL_K adjust based on classification.

**Query classification:**

| Query type | Detection signal | Max chunks per source | FINAL_K adjustment |
|---|---|---|---|
| **File-specific** | Path or extension in query (`FileManager`, `sdd.md`, `.fpp`) | Up to FINAL_K from matched file | Tier default |
| **Component-specific** | Single CamelCase F' identifier (`BufferManager`, `CmdDispatcher`) | Up to FINAL_K from matched component's source files | Tier default |
| **Comparison** | "difference", "vs", "compare", "between X and Y" | Max 1 per source (need breadth) | Tier default + 2 |
| **Code-seeking** | "how to implement", "write", "example", "syntax" | Max 2 per source | Tier default |
| **Concept-seeking** | "what is", "explain" | Max 2 per source | Tier default |
| **General** | No specific signals detected | Max 2 per source | Tier default |

**Classification precedence** (first match wins): file-specific > component-specific > comparison > code-seeking > concept-seeking > general. This resolves overlap — e.g., "What is the difference between active and passive components?" matches both "comparison" ("difference between") and "concept-seeking" ("what is"), but "comparison" wins because it has higher precedence.

**False positive mitigation:** When a file-specific or component-specific entity is detected, validate that it actually exists in the index. The classifier receives a precomputed `known_entities: set[str]` built once at index load time inside `query()` after `_load_index()`, then cached at module level for subsequent calls. Entity extraction logic:
- From `source_file` paths: extract the last directory component before `/docs/` or the filename stem (e.g., `Svc/BufferManager/docs/sdd.md` → `BufferManager`, `Fw/Comp/ActiveComponent.hpp` → `ActiveComponent`)
- From `component_name` fields: include directly (already clean identifiers)
- All entity names lowercased for case-insensitive matching against query terms

If no match in `known_entities`, fall back to "general" classification.

### 1c. Tiered FINAL_K

Base FINAL_K tied to model capability tier:

| Level | FINAL_K (base) | Target model size | Notes |
|---|---|---|---|
| 1 | 5 | ≤8B (qwen3:8b) | Default. Up from 3. |
| 2 | 7 | 14B–32B | Mid-range |
| 3 | 10 | 70B+ | Large context models |

The tier is set once (not per-query) as a configuration constant. The query-type classifier can adjust upward from the base (e.g., comparison queries add +2).

**RERANK_K:** Currently derived as `FINAL_K * 5` at module load time. With dynamic FINAL_K, this becomes stale. Fix: set `RERANK_K = 50` as a fixed constant independent of FINAL_K. This provides a large enough candidate pool for all tiers (Tier 3 max effective FINAL_K = 10 + 2 = 12, well under 50).

### 1d. Content-Type Boosting

At re-rank time, boost chunks whose `content_type` metadata matches the query type:

| Query type | Boosted content types | Boost |
|---|---|---|
| Code-seeking | `code`, `reference` | 1.2 |
| Concept-seeking | `concept`, `tutorial` | 1.2 |
| File-specific | All (no preference) | 1.0 |
| Component-specific | All (no preference) | 1.0 |
| Comparison | `concept`, `reference` | 1.1 |
| General | All (no preference) | 1.0 |

---

## Section 2: Index Coverage Improvements

Changes to `TUI/rag/chunker.py` and `TUI/rag/indexer.py`.

### 2a. C++ Header and Source Parsing

Add `.hpp`, `.h`, `.cpp` files to the chunker.

**Chunking strategy for hand-written C++ files:**
- Split on class/struct declarations, enum definitions, and top-level function signatures
- Preserve the enclosing class name as context in each chunk (e.g., a chunk for `Os::Task::State` includes that it belongs to `Os::Task`)
- Skip include guards, license headers, and preprocessor noise (`#ifndef`, `#define`, `#include`)
- Handle F' namespace nesting (`namespace Os { namespace Task { ... } }` and `namespace Os::Task { ... }`)

**Target directories:** `Fw/`, `Os/`, `Svc/` (framework code, not user project code).

**Implementation approach:** Regex-based parsing (not a full C++ parser). Estimated ~80-120 lines in `chunker.py`. Key patterns:
- `class\s+(\w+)(?:\s*:\s*public\s+\w+)?` — class declarations with optional inheritance
- `enum\s+(?:class\s+)?(\w+)\s*\{` — enum and enum class definitions
- `namespace\s+([\w:]+)\s*\{` — namespace blocks (track for context prefix)
- `^\s*(?:virtual\s+)?[\w:]+\s+\w+\s*\(` — method signatures (in class scope)

For header-only implementations (common in F'), the entire function body is included in the chunk — splitting at the next top-level declaration boundary, same as the Python chunker strategy. The `_truncate()` function caps oversized chunks.

### 2b. Autocoded File API Extraction

For autocoded files (`*Ac.hpp`, `*Ac.cpp`), use a specialized chunking strategy:
- **Extract only public/protected method signatures** — the API surface that developers call
- Group extracted signatures by component (e.g., "Component `Health` provides: `pingIn_handler()`, `log_WARNING_HI_PingLate(entry)`, `tlmWrite_PingLateWarnings(count)`")
- Skip serialization boilerplate, dispatch switch statements, constructor/destructor implementations

**Rationale:** F' is a modeling language. The `.fpp` file defines the model, the autocoder generates the implementation API (`log_WARNING_HI_*`, `cmdResponse_out()`, `tlmWrite_*`). These generated function names are what developers actually call, so they must be in the index. But the full autocoded files are thousands of lines of dispatch/serialization noise that would become "sticky junk" in BM25.

**Implementation:** A new `chunk_autocoded_cpp()` function in `chunker.py` that parses for C++ method declarations in public/protected sections (~40-60 lines of regex parsing).

### 2c. Content-Type Tagging

At chunk time, tag each chunk with a `content_type` metadata field:

| Content type | Detection heuristic |
|---|---|
| `code` | >50% of lines are code-fenced or indented code blocks, or source file is `.fpp`/`.hpp`/`.cpp`/`.py` |
| `concept` | Prose-heavy markdown with headers, no significant code blocks |
| `reference` | Tables, parameter lists, enum listings, API signatures |
| `tutorial` | Ordered steps (numbered lists), "first... then..." patterns, files under `docs/how-to/` or `docs/getting-started/` |

Stored in both ChromaDB metadata AND the BM25 pickle's chunk dicts. The retriever accesses chunks from `bm25_data["chunks"]` (not ChromaDB metadata) during re-ranking, so `content_type` must be present in the pickle. The `indexer.py` chunk dict structure becomes: `{"text", "source_file", "chunk_type", "component_name", "content_type"}`.

### 2d. FPP Spec Priority

- **Chunker:** Increase target chunk size for FPP spec files to ~500 tokens (dense content; splitting too small loses context like "this keyword must appear inside a component block"). The `_truncate()` function already accepts an optional `max_chars` parameter (default: `TARGET_TOKENS * CHARS_PER_TOKEN = 1200`). FPP spec chunk callers pass `max_chars=2000`.
- **Indexer:** FPP spec files from the fprime repo (`docs/reference/fpp-*`, `docs/user-manual/fpp-*`) get flagged with metadata `priority: high`
- **Retriever:** Source-category boost from Section 1a handles the ranking side (`fpp_spec` category gets 1.25x)

### 2e. Autocoded File Exclusion Filter

Files excluded from full chunking (handled separately by API extraction in 2b):

| Pattern | Reason |
|---|---|
| `*Ac.hpp` / `*Ac.cpp` | Autocoded — API extracted separately |
| `*GTestBase.*` | Generated test base classes |
| `*TesterBase.*` | Generated tester scaffolding |
| `build*/` | Build artifacts |

---

## Section 3: Prompt & Context Improvements

Changes to `TUI/fprime_ai_client.py` and context formatting. No LLM rewrites.

### 3a. Query-Type Signal in System Prompt

When the query-type classifier detects the query type, prepend a one-line static instruction to the context block:

| Query type | Prepended instruction |
|---|---|
| Code-seeking | `"Prioritize code examples and exact syntax from the sources below."` |
| Concept-seeking | `"Explain the concept using the sources below. Cite specific F' terminology."` |
| File-specific | `"Answer using the content from the requested file below."` |
| Comparison | `"Compare using specific details from the sources below."` |

These are static strings selected by the classifier, not LLM-generated.

### 3b. Source Label Enhancement

Current format:
```
[SOURCE: Fw/Comp/docs/sdd.md | type: markdown]
```

Enhanced format:
```
[SOURCE: Fw/Comp/docs/sdd.md | type: markdown | content: concept]
```

Adds the `content_type` tag so the model can see what kind of information each chunk contains.

### 3c. Strengthened Context-Use Instruction

Current system prompt instruction:
> "If provided with a '### RELEVANT F' KNOWLEDGE BASE ###' section, treat it as the authoritative source for F' architecture, standards, and code structure."

Revised:
> "If provided with a '### RELEVANT F' KNOWLEDGE BASE ###' section, you MUST base your answer on the content provided in that section. Do not rely on your general knowledge for F'-specific syntax, API names, or code patterns — use only what appears in the sources. If the sources do not contain enough information, say so."

---

## Section 4: Architecture & Configuration

### 4a. Model Tier Configuration

```python
# TUI/rag/config.py (or constants in retriever.py)
TIERS = {
    1: {"final_k": 5, "label": "lightweight", "target_models": "≤8B"},
    2: {"final_k": 7, "label": "standard",    "target_models": "14B–32B"},
    3: {"final_k": 10, "label": "full",        "target_models": "70B+"},
}
DEFAULT_TIER = 1
```

Set once, not per-query. When model-level UI is implemented later, it sets this value.

### 4b. Revised Retrieval Pipeline

**Critical refactoring:** The current `reciprocal_rank_fusion()` returns only a sorted `list[str]` of IDs — the RRF scores are discarded. To support multiplicative boosting (Sections 1a, 1d) and unified scoring (below), this function must be refactored to return `dict[str, float]` (ID → score). Existing tests in `tests/rag/test_retriever.py` (`test_rrf_merges_two_lists`, etc.) will need updating for the new return type.

**Unified scoring function:** Rather than applying boosts, keyword scores, and content-type scores as sequential re-sorts (which would cause later sorts to erase earlier ones), all signals are combined into a single composite score per candidate:

```python
def composite_score(
    rrf_score: float,
    chunk: dict,
    keywords: list[str],
    query_type: str,
) -> float:
    score = rrf_score
    score *= get_source_category_boost(chunk["source_file"])   # Section 1a
    score *= get_content_type_boost(chunk["content_type"], query_type)  # Section 1d
    score *= (1 + keyword_score(chunk["text"], keywords) * KEYWORD_WEIGHT)  # Section 1 (existing)
    return score
```

The keyword contribution is **multiplicative** (`*= (1 + kw * weight)`), not additive. This is critical because RRF scores are small (~0.01-0.03 for `1/(60+rank)`), so an additive keyword term would dominate the score. With the multiplicative form, keywords act as a tiebreaker: a perfect keyword match with `KEYWORD_WEIGHT=0.3` boosts the score by 30%, enough to break ties but not enough to override a strong RRF signal. Starting value: `KEYWORD_WEIGHT = 0.3`.

**Revised pipeline:**

```
User query
    │
    ├─ 1. classify_query(text, known_entities) → query_type + target_entity
    │
    ├─ 2. Dense retrieval (DENSE_K=10, unchanged)
    │
    ├─ 3. Sparse retrieval (SPARSE_K=20, unchanged)
    │
    ├─ 4. RRF merge → dict[str, float] (RERANK_K=50 candidates with scores)
    │
    ├─ 5. Composite scoring (source-category boost × content-type boost + keyword score)
    │     All signals combined in a single pass — no sequential re-sorts
    │
    ├─ 6. Sort by composite score, descending
    │
    ├─ 7. Adaptive diversity filter (max per source based on query_type)
    │
    ├─ 8. Take top FINAL_K (tier base + query_type adjustment)
    │
    └─ 9. Format with query-type instruction prepended
```

Steps 1, 4 (return type), 5, 6, 7, 8, 9 are new or modified. Steps 2 and 3 are unchanged.

### 4c. Revised Indexer Pipeline

```
Source acquisition (unchanged: git clone + web scrape)
    │
    ├─ Markdown files → existing markdown chunker
    │     └─ FPP spec files: larger chunks (~500 tokens)
    │
    ├─ .fpp files → existing FPP chunker (unchanged)
    │
    ├─ .py files → existing Python chunker (unchanged)
    │
    ├─ .hpp/.h files (non-Ac) → NEW: C++ header chunker
    │
    ├─ .cpp files (non-Ac) → NEW: C++ source chunker
    │
    ├─ *Ac.hpp / *Ac.cpp → NEW: API extraction chunker
    │     └─ Public/protected method signatures only
    │
    ├─ All chunks tagged with:
    │     source_file, chunk_type, component_name,
    │     content_type (code/concept/reference/tutorial)
    │
    ├─ Deduplication (existing SHA-256, unchanged)
    │
    └─ Embed + store in ChromaDB + BM25 (unchanged)
```

### 4d. Non-RAG Issues Register

Issues observed during evaluation that affect answer quality but are outside RAG scope:

| Issue | Layer | Notes |
|---|---|---|
| Path blindness — agent wanders to `/`, `~/` when searching | Tool sandboxing | Constrain file tools to `FPRIME_PROJECT_ROOT` |
| Tool recursion depth limit (5) too shallow for deep paths | ReAct loop | Deep `fprime/Svc/` paths need more hops |
| Duplicate training questions (Q216, Q239, Q249, Q259) | Eval dataset | Inflates fail counts, not a system issue |

---

## Test Plan

Existing tests in `tests/rag/` cover `chunker`, `retriever`, and `prompt`. The following new tests are needed:

### Retriever tests (`tests/rag/test_retriever.py`)
- **Update** `test_rrf_merges_two_lists` — assert return type is `dict[str, float]` (scores preserved)
- `test_classify_query_file_specific` — query with filename → `file_specific` type
- `test_classify_query_component` — query with CamelCase identifier → `component_specific`
- `test_classify_query_comparison` — query with "difference between" → `comparison` (not `concept_seeking`)
- `test_classify_query_precedence` — verify file-specific > comparison > concept-seeking
- `test_classify_query_unknown_entity_fallback` — unrecognized component name → `general`
- `test_source_category_boost` — framework_core chunks ranked higher than service_docs for equal RRF
- `test_content_type_boost` — code chunks boosted for code-seeking queries
- `test_diversity_filter_general` — max 2 chunks per source file
- `test_diversity_filter_file_specific` — relaxed limit for target file
- `test_composite_score` — verify all signals combine correctly (multiplicative keyword, not additive)
- **Update** `test_format_context_produces_labeled_blocks` — assert new format includes `content` field in source label

### Chunker tests (`tests/rag/test_chunker.py`)
- `test_chunk_cpp_header` — class/enum/namespace extraction from `.hpp`
- `test_chunk_cpp_source` — function boundary splitting from `.cpp`
- `test_chunk_autocoded_api` — public method signature extraction from `*Ac.hpp`
- `test_chunk_autocoded_skips_boilerplate` — dispatch/serialization code excluded
- `test_content_type_tagging` — verify `content_type` field set correctly per heuristic
- `test_fpp_spec_larger_chunks` — FPP spec files use 2000-char truncation limit

### Integration
- Re-run the 262-question evaluation after implementation to measure before/after accuracy

---

## Deferred to Iteration 3

| Feature | Description | Why deferred |
|---|---|---|
| Chunk quality scoring | Static information-density score per chunk at index time | Source-category boosting and diversity filter solve most of the same problems more directly |
| Query expansion | LLM rewrites query with technical terms before retrieval | Adds latency, hallucination risk, violates no-LLM-in-pipeline constraint |
| Answer grounding check | Post-generation verification that cited sources match retrieved sources | Limited benefit at 8B model level |

---

## Files Modified

| File | Changes |
|---|---|
| `TUI/rag/retriever.py` | Source-category boosting, adaptive diversity filter, tiered FINAL_K, content-type boosting, query classifier, query-type instructions |
| `TUI/rag/chunker.py` | C++ header/source chunking, autocoded API extraction, content-type tagging, FPP spec larger chunk size |
| `TUI/rag/indexer.py` | Include `.hpp`/`.cpp` files, autocoded file filter, source-category and content-type metadata |
| `TUI/fprime_ai_client.py` | Strengthened context-use instruction, enhanced source labels |
| `TUI/rag/config.py` (new) | Tier configuration constants. Imported by `retriever.py` as `from rag.config import TIERS, DEFAULT_TIER` |
| `TUI/rag/prompt.py` | No changes. This standalone utility diverges from the TUI system prompt — acceptable since it's used for CLI/batch scripts only, not the TUI. May be deprecated in a future iteration |
