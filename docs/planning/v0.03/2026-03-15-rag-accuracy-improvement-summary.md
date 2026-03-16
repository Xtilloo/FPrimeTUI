# RAG Accuracy Improvement — v0.03 Summary

**Date:** 2026-03-15
**Branch:** `rag_implementation`
**Status:** Implemented, index rebuilt, evaluation pending

---

## What This Iteration Aimed to Achieve

The first RAG evaluation (2026-03-14) tested 262 F' training questions and returned a **29% pass rate** (75 PASS / 80 PARTIAL / 113 FAIL). Root cause analysis identified five problems:

1. **Off-target retrieval** — generic F' vocabulary caused unrelated files (e.g. `Svc/FileManager/docs/sdd.md`) to win BM25 matches and consume context slots.
2. **Missing C++ coverage** — framework headers (`Fw/`, `Os/`) and autocoded API files were not indexed at all.
3. **Model ignores context** — the 8B model fell back to parametric knowledge even when correct sources were in context.
4. **FINAL_K=3 too low** — one bad retrieval consumed 33% of the context budget.
5. **No query-type awareness** — code-seeking queries received concept chunks and vice versa.

v0.03 addresses all five with deterministic (no-LLM) changes to the retrieval pipeline, chunker, indexer, and system prompt.

---

## What Was Built

### Retrieval pipeline (`retriever.py`, `config.py`)
- **Tiered FINAL_K** — context window now scales with model: 5 chunks (≤8B), 7 (14–32B), 10 (70B+). Up from hardcoded 3.
- **Source-category boosting** — framework core files get 1.3× score multiplier; FPP spec 1.25×; test projects penalized at 0.85×. Computed at query time from `source_file` path — no re-indexing needed to tune weights.
- **Query-type classifier** — regex/keyword heuristics classify each query as `file_specific`, `component_specific`, `comparison`, `code_seeking`, `concept_seeking`, or `general`. No LLM call.
- **Content-type boosting** — code chunks boosted for code-seeking queries; concept/tutorial chunks boosted for concept-seeking.
- **Composite scoring** — all signals (RRF base × source boost × content boost × keyword match) combined multiplicatively in a single pass. Keyword contribution is a tiebreaker (30% max lift), not a dominant signal.
- **Adaptive diversity filter** — comparison queries cap at 1 chunk per source (forces breadth); others cap at 2. File/component-specific queries get unlimited chunks from the target source.
- **Improved context format** — source labels now include `content: code/concept/reference/tutorial`. Query-type instructions prepended to context block.

### Chunker (`chunker.py`)
- **`detect_content_type()`** — tags every chunk as `code`, `concept`, `reference`, or `tutorial` via file extension, path heuristics, fenced block ratio, table detection, and numbered step detection.
- **`chunk_cpp()`** — splits `.hpp`/`.cpp` files on class/struct/enum boundaries; strips preprocessor noise; preserves namespace context prefix.
- **`chunk_autocoded_cpp()`** — extracts only public/protected method signatures from `*Ac.hpp`/`*Ac.cpp`; skips dispatch/serialization boilerplate. These generated method names (`log_WARNING_HI_*`, `tlmWrite_*`, `cmdResponse_out`) are exactly what developers call — they must be in the index.
- **FPP spec larger chunks** — `docs/reference/fpp-*` and `docs/user-manual/fpp-*` re-chunked at 2000 chars (was 1200) — dense DSL docs lose context when split too small.
- All existing chunkers (`chunk_markdown`, `chunk_fpp`, `chunk_python`) updated to include `content_type`.

### Indexer (`indexer.py`)
- `.hpp`, `.h`, `.cpp` files now indexed from the fprime repo.
- Routing: autocoded files (`*Ac.*`) → API extraction; `GTestBase`/`TesterBase` skipped; build artifacts skipped.
- `content_type` stored in ChromaDB metadata alongside existing fields.

### System prompt (`fprime_ai_client.py`)
- Strengthened context-use instruction: model is now told to base answers exclusively on retrieved sources, not parametric knowledge, and to say so if sources are insufficient.

---

## What Was Not Changed

- Dense retrieval (DENSE_K=10) and sparse retrieval (SPARSE_K=20) parameters — unchanged.
- BM25 tokenization and CamelCase expansion — unchanged.
- No LLM calls anywhere in the retrieval pipeline.
- `rag/prompt.py` standalone utility — not updated (diverges from TUI system prompt by design).

---

## Metrics

- **Baseline:** 75 PASS / 80 PARTIAL / 113 FAIL (29% pass rate) — 2026-03-14 evaluation
- **Target:** Significantly higher pass rate, particularly on framework API and code-seeking questions
- **Post-implementation evaluation:** Pending — requires re-running the 262-question evaluation suite against the rebuilt index

---

## Known Limitations

- C++ namespace context captures only the outermost namespace (nested `namespace Os { namespace Task { } }` loses inner level). Acceptable for v0.03 — chunks are still indexed and searchable.
- `classify_query` bare file extension (`.fpp` without a filename) does not trigger `file_specific`. Defensible behavior.
- `priority: high` metadata for FPP spec files (mentioned in design spec) deferred — the source-category boost handles the ranking effect at query time without stored metadata.
