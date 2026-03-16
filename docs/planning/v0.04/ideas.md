# v0.04 Ideas Backlog

Consolidated from v0.01 Phase 4, v0.02 deferred, v0.03 deferred/design notes, and new ideas from the v0.03 training pipeline work.

---

## RAG Retrieval Improvements

| Idea | Origin | Impact | Notes |
|------|--------|--------|-------|
| Query rewriting | v0.02 deferred | High accuracy gain | LLM expands user queries into F' vocabulary before retrieval. Adds latency + hallucination risk — consider rule-based synonym expansion instead |
| Per-component metadata filtering | v0.02 deferred | High | Filter chunks by `component_name` before vector search for component-specific queries. Biggest single retrieval accuracy win remaining |
| Chunk quality scoring | v0.03 deferred | Medium | Static information-density score per chunk at index time. Deprioritize boilerplate, license headers |
| Answer grounding check | v0.03 deferred | Medium | Post-generation verification that response actually used retrieved sources. Hard at 8B level but training pipeline now provides measurement data |

## RAG Index Improvements

| Idea | Origin | Impact | Notes |
|------|--------|--------|-------|
| Index versioning | v0.02 deferred | Medium | Track F' version in index metadata, warn when repo has updated. Prevents stale index |
| Sitemap-driven docs crawl | v0.02 deferred | Medium | Replace single-page fetch with full docs site crawl for better coverage |
| Academy mode RAG | v0.02 deferred | Medium | Lightweight "concept explanation" index separate from code-heavy Mission Control index. Academy mode currently has no RAG |
| Nested C++ namespace splitting | v0.03 known limitation | Low | Brace-depth tracking to keep inner enums grouped with parent class. Marginal chunk quality improvement |

## Training Pipeline Improvements

| Idea | Origin | Impact | Notes |
|------|--------|--------|-------|
| Curated store audit pass | v0.03 design | Medium | Re-verify curated entries when source files change (compare `source_files` timestamps) |
| Split curated_qa.md by topic | v0.03 design | Medium | When exceeding ~200 entries, split into `curated_qa_commands.md`, `curated_qa_components.md`, etc. |
| Diagnosis pattern clustering | New | Medium | Auto-group failures by pattern (wrong framework, invented syntax, off-target retrieval) instead of manual grouping |
| Confidence scoring | New | Medium | Verifiers output 1-5 confidence alongside CORRECT/PARTIAL/INCORRECT, weight consensus by confidence for better signal on disputed cases |
| Incremental re-eval | New | High | Only re-test questions that previously failed, not the full 685 set. 10x faster overnight runs after initial pass |

## TUI Feature Ideas

| Idea | Origin | Impact | Notes |
|------|--------|--------|-------|
| Topology visualization | v0.01 Phase 4 | High | Parse topology FPP to generate Markdown graphs of component connections |
| Automated unit testing | v0.01 Phase 4 | High | Run F' unit tests, auto-generate missing test cases from component definitions. Ambitious |
| Dictionary generation | v0.01 Phase 4 | Medium | Draft command/telemetry/event dictionaries from natural language descriptions |
| Model-level UI | v0.03 design note | Medium | Let users switch between model tiers (8B/14B/32B) from within the TUI. Tiered FINAL_K already designed |
| `/review` command | New | High | Show the review queue inline, letting users `/good` or `/bad` each entry without leaving the TUI |
| `/stats` command | New | Low | Show curated store size, pass/fail rates from last training run, index age. Quick health check |
| Deprecate `rag/prompt.py` | v0.03 design | Low | Standalone utility diverges from TUI system prompt. Removes confusion about which prompt is authoritative |

---

## Recommended Priority Order

1. **Run the first real training pipeline** — exercise the skills, find friction, fix it
2. **Incremental re-eval** — after fixing failures, only re-test what failed
3. **Per-component metadata filtering** — biggest single retrieval accuracy win remaining
4. **`/review` command** — makes the human review loop 10x faster
5. **Academy mode RAG** — unlocks RAG for the teaching mode
6. **Index versioning** — prevents silent staleness
