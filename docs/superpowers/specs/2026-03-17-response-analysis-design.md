# Response Analysis Pipeline — Design Spec
**Date:** 2026-03-17
**Branch:** rag_implementation
**Status:** Approved

---

## Overview

A two-phase pipeline for post-processing all 685 TUI responses collected by
`scripts/collect_responses.py`. Phase 1 runs autonomously (pure Python). Phase 2
runs in a Claude Code session using the `fprime-tui-analyze-responses` skill to
orchestrate subagents. Outputs an enriched JSONL and a human-readable markdown
report for RAG improvement decisions.

---

## Input Schema — `docs/training/responses.jsonl`

One JSON object per line, written by `scripts/collect_responses.py`:

```json
{
  "id": "112",
  "category": "Implementation",
  "question": "What is the FW_OPTIONAL_NAME macro?",
  "expected": "One-sentence ground-truth answer from training file.",
  "response": "Full TUI response text...",
  "status": "ok",
  "timestamp": "2026-03-17T02:41:30.653817"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | string (numeric) | Question ID, 1–685 |
| `category` | string | e.g. "Implementation", "Modeling" |
| `question` | string | Question text sent to TUI |
| `expected` | string | Ground-truth answer from training file (always present) |
| `response` | string | Full TUI response; empty string on timeout |
| `status` | `"ok"` \| `"timeout"` | Written by collector |
| `timestamp` | ISO-8601 string | Time response was captured |

---

## Phase 1 — Python Preprocessor

**Script:** `scripts/preprocess_responses.py`

Reads `docs/training/responses.jsonl` and extracts deterministic signals for
each response without any LLM. Safe to re-run — overwrites batch files.

### Signals Extracted

| Signal | Type | Method |
|--------|------|--------|
| `has_gap` | bool | Keyword match on `response`: "knowledge base", "do not have", "don't have", "no information", "not aware", "cannot find", "not enough info" |
| `has_fpp` | bool | Regex: ` ```fpp ` block present in `response` |
| `fpp_blocks` | list[str] | Extracted raw FPP code block content |
| `has_tool_call` | bool | Regex: ` ```json ` block with `tool`, `command`, or `read_file` key |
| `tool_calls` | list[dict] | Parsed JSON tool call objects |
| `source_count` | int | Count of filenames in `*Sources: ...*` footer |
| `sources_cited` | list[str] | Filenames parsed from `*Sources: ...*` footer via regex |
| `timeout` | bool | Derived from `status == "timeout"` or `len(response) < 50` |

**Note on `sources_cited`:** Extracted from free-text footer via regex
`\*Sources: ([^*]+)\*` then split on ` · `. Reliable for responses that follow
the standard TUI format; absent sources are treated as empty list.

### Batch File Partitioning

Writes batch files to `docs/training/analysis/batches/`. Each batch is a JSON
array of 25 items (final batch may be smaller). Items are only included in a
batch concern if they match that concern's filter:

```
docs/training/analysis/
  batches/
    accuracy_001.json ... accuracy_028.json   (all 685, ~28 batches)
    gap_001.json ... gap_NNN.json             (has_gap == true only)
    fpp_001.json ... fpp_NNN.json             (has_fpp == true only)
    sources_001.json ... sources_NNN.json     (source_count > 0 only)
    commands_001.json ... commands_NNN.json   (has_tool_call == true only)
```

**Note on overlapping responses:** A response may appear in multiple batch
concerns (e.g., one with both `has_gap` and `has_fpp`). This is intentional —
each agent writes its verdict independently, and the aggregation step merges
all verdict fields onto the same `id` in the enriched output.

**Ragged batches:** 685 / 25 = 27 full batches + 1 batch of 10. The
preprocessor handles this naturally with Python list slicing.

Also writes `docs/training/analysis/manifest.json`:
```json
{
  "total": 685,
  "batches": {
    "accuracy": 28,
    "gap": 5,
    "fpp": 8,
    "sources": 12,
    "commands": 2
  },
  "generated_at": "2026-03-17T..."
}
```

---

## Phase 2 — Claude Code Session Orchestration

Triggered by invoking the `fprime-tui-analyze-responses` skill in a Claude Code
session. No API key required — runs within the Pro subscription session.

### Parallelism Model

The Claude Code `Agent` tool dispatches subagents. Within a single message,
multiple `Agent` tool calls can be made in parallel (the system executes them
concurrently). The orchestration skill dispatches agents in **concern groups**:

1. Dispatch all `gap`, `fpp`, `sources`, and `commands` batches in parallel
   (small subsets — fast, low context). Wait for all to complete.
2. Dispatch `accuracy` batches in groups of 10 in parallel. Repeat until all
   28 batches are done. (Larger groups risk context pressure.)

This gives practical parallelism while keeping individual agent context small.

### Checkpoint / Resume

Before dispatching each batch, the skill checks
`docs/training/analysis/progress.json`:

```json
{
  "accuracy": ["accuracy_001", "accuracy_002"],
  "gap": ["gap_001"],
  "fpp": [],
  "sources": [],
  "commands": [],
  "last_updated": "2026-03-17T..."
}
```

Batch IDs are agent-namespaced (e.g. `"accuracy_001"`, `"gap_001"`) so there is
no ambiguity when two agents have the same batch number.

If `progress.json` exists, already-completed batches are skipped. After each
batch result is written, the skill updates `progress.json`. On re-run (if a
session is interrupted), only incomplete batches are dispatched.

### The Five Agents

#### 1. Accuracy Agent
- **Filter:** all responses
- **Input per batch:**
  ```json
  [{"id": "1", "category": "Architecture", "question": "...", "expected": "...", "response": "..."}]
  ```
- **Task:** Semantic comparison — does the response convey the key concepts,
  correct values, and correct terminology from the expected answer? Not
  word-for-word. Responses that hedge appropriately on unknown topics can still
  be PASS.
- **Output per item:** `{"id": "1", "verdict": "PASS|PARTIAL|FAIL", "reason": "<one sentence>"}`
- **PARTIAL definition:** Response addresses the topic and shows partial
  understanding but is missing one or more key concepts or contains minor
  inaccuracies. Downstream: goes to `review_queue.md`.
- **Batches:** ~28

#### 2. Gap Agent
- **Filter:** `has_gap == true`
- **Input per batch:**
  ```json
  [{"id": "112", "category": "Implementation", "question": "...", "response": "..."}]
  ```
- **Task:** Extract what specific topic is missing and classify the gap type.
- **Output per item:**
  ```json
  {"id": "112", "missing_topic": "FW_OPTIONAL_NAME macro", "gap_type": "explicit|hedged|deflection"}
  ```
  - `explicit` — TUI directly states topic is not in its knowledge base
  - `hedged` — TUI softens with "you may want to consult..." without admitting the gap
  - `deflection` — TUI changes subject or gives a generic answer without addressing the question
- **Batches:** ~4–6

#### 3. FPP Syntax Agent
- **Filter:** `has_fpp == true`
- **Input per batch:**
  ```json
  [{"id": "10", "category": "Modeling", "question": "...", "expected": "...", "fpp_blocks": ["..."]}]
  ```
  Only `fpp_blocks` are sent, not the full response, to keep context small.
- **Task:** Check FPP syntax against known-correct patterns. Flag wrong
  keywords, invalid block structure, made-up constructs or type names.
- **Output per item:**
  ```json
  {"id": "10", "has_issues": false, "issues": [], "severity": "ok|minor|major"}
  ```
  - `minor`: incorrect style or suboptimal but functionally plausible
  - `major`: wrong keyword, invalid syntax, made-up construct
- **Batches:** ~7–8

#### 4. Source Citation Agent
- **Filter:** `source_count > 0`
- **Input per batch:**
  ```json
  [{"id": "314", "category": "Architecture", "question": "...", "sources_cited": ["Fw/Types/docs/sdd.md", "..."], "response": "..."}]
  ```
  Full `response` included (truncated to 1000 chars if needed to fit context).
- **Task:** Are the cited sources actually relevant to the question? This
  separates three failure modes:
  - FAIL + no sources → knowledge gap (RAG found nothing)
  - FAIL + irrelevant sources → retrieval quality problem (wrong chunks surfaced)
  - FAIL + relevant sources → reasoning/prompt problem (right info, wrong answer)
- **Output per item:**
  ```json
  {"id": "314", "relevant": true, "reason": "<one sentence>"}
  ```
- **Batches:** ~10–12

#### 5. Command Validity Agent
- **Filter:** `has_tool_call == true`
- **Input per batch:**
  ```json
  [{"id": "50", "category": "Build System", "question": "...", "tool_calls": [{"tool": "run_command", "command": "fprime-util build"}]}]
  ```
- **Task:** Are tool calls logically sound?
  - Do `read_file` paths target files plausibly in the F' repo?
  - Are `run_command` calls using valid `fprime-util` subcommands?
  - Is the reasoning appropriate for the question?
- **Output per item:**
  ```json
  {"id": "50", "valid": true, "issues": []}
  ```
- **Batches:** ~1–2

---

## Aggregation

After all batches complete, a Python aggregation step merges results:

**Script:** `scripts/aggregate_analysis.py` (can also be invoked by the skill)

Result files use the naming convention `results/<concern>_NNN.json` where
`<concern>` is one of `accuracy`, `gap`, `fpp`, `sources`, `commands`. The
aggregator globs each concern separately:
- `results/accuracy_*.json` → merged into `accuracy` field
- `results/gap_*.json` → merged into `gap` field
- `results/fpp_*.json` → merged into `fpp` field
- `results/sources_*.json` → merged into `sources` field
- `results/commands_*.json` → merged into `commands` field

Logic:
1. Load all concern-specific result files by glob pattern
2. Build a lookup dict: `{id: {accuracy: ..., gap: ..., fpp: ..., sources: ..., commands: ...}}`
3. For each entry in `responses.jsonl`, merge the signals (from Phase 1) and
   all agent verdicts by `id`
4. Write `docs/training/analysis/responses_enriched.jsonl`
5. Compute category-level statistics and write `docs/training/analysis/YYYY-MM-DD-analysis-report.md`

Responses with no agent verdict for a concern (filtered out in Phase 1) get
`null` for that field. No data is dropped — all 685 entries appear in the
enriched output.

---

## Output Format

### `docs/training/analysis/responses_enriched.jsonl`

```json
{
  "id": "112",
  "category": "Implementation",
  "question": "What is the FW_OPTIONAL_NAME macro?",
  "expected": "...",
  "response": "...",
  "status": "ok",
  "timestamp": "...",
  "signals": {
    "has_gap": true,
    "has_fpp": false,
    "has_tool_call": false,
    "timeout": false,
    "source_count": 3
  },
  "accuracy": {"verdict": "FAIL", "reason": "Missing FW_OPTIONAL_NAME definition entirely"},
  "gap": {"missing_topic": "FW_OPTIONAL_NAME macro", "gap_type": "explicit"},
  "fpp": null,
  "sources": {"relevant": false, "reason": "Cited Fw/Types/docs/sdd.md but question is about config macros"},
  "commands": null
}
```

### `docs/training/analysis/YYYY-MM-DD-analysis-report.md`

**Section 1 — Accuracy Scorecard**
Table by category: columns = Category, Total, PASS (#/%),  PARTIAL (#/%), FAIL (#/%).
One row per category plus a totals row.

**Section 2 — Knowledge Gap Index**
Ranked list of `missing_topic` values by frequency. Grouped by category.
Format: `- [N×] <topic> (<category>)`. Top 20 shown.

**Section 3 — FPP Issue Summary**
Counts by severity (ok/minor/major). Followed by up to 5 example `major` issues
with question ID, bad FPP block, and agent's issue description.

**Section 4 — Source Citation Quality**
Table by category: columns = Category, Responses With Sources, Relevant (#/%),
Irrelevant (#/%). Highlights categories where retrieval accuracy is lowest.

**Section 5 — Command Validity Summary**
List of all attempted tool calls: `Q<id>: <tool>(<args>) → valid|invalid — <reason>`.

---

## Skills

Phase 2 uses **six skills** — one orchestrator and one per agent type. Each agent
skill defines strict rules: exact input contract, evaluation criteria, and required
output format. Subagents invoke their skill and follow it exactly.

### Orchestration Skill — `fprime-tui-analyze-responses`
`~/.claude/skills/fprime-tui-analyze-responses/skill.md`

Instructs the orchestrating agent to:
1. Read `manifest.json` to determine batch counts per concern
2. Read `progress.json` (if present) to identify already-completed batches
3. Dispatch concern group 1 (gap, fpp, sources, commands) as parallel subagents —
   one Agent tool call per batch file, all in a single message; each subagent
   is told which agent skill to invoke
4. Wait for group 1 to complete, update `progress.json`
5. Dispatch accuracy batches in groups of 10 parallel subagents; repeat until done,
   updating `progress.json` after each group
6. Run `python3 scripts/aggregate_analysis.py` to merge results and write final outputs
7. Print a completion summary: batch counts, any failures, output file paths

### Agent Skills (one per concern)

| Skill | Path |
|-------|------|
| `fprime-tui-agent-accuracy` | `~/.claude/skills/fprime-tui-agent-accuracy/skill.md` |
| `fprime-tui-agent-gap` | `~/.claude/skills/fprime-tui-agent-gap/skill.md` |
| `fprime-tui-agent-fpp` | `~/.claude/skills/fprime-tui-agent-fpp/skill.md` |
| `fprime-tui-agent-sources` | `~/.claude/skills/fprime-tui-agent-sources/skill.md` |
| `fprime-tui-agent-commands` | `~/.claude/skills/fprime-tui-agent-commands/skill.md` |

Each agent skill specifies:
- **Role** — one sentence on what this agent does
- **Input contract** — exact JSON field names and types expected in the batch file
- **Evaluation rules** — explicit criteria for each verdict/output value (no ambiguity)
- **Output contract** — exact required JSON structure per item, with field names and types
- **Hard rules** — what the agent must never do (e.g., infer missing fields, skip items,
  produce output outside the defined schema)

---

## File Layout

```
scripts/
  preprocess_responses.py         # Phase 1 — run from terminal
  aggregate_analysis.py           # Aggregation — run by skill or manually

docs/training/analysis/
  manifest.json                   # Batch counts, written by Phase 1
  progress.json                   # Checkpoint, written by Phase 2 skill
  batches/                        # Written by Phase 1
    accuracy_NNN.json
    gap_NNN.json
    fpp_NNN.json
    sources_NNN.json
    commands_NNN.json
  results/                        # Written by Phase 2 subagents
    accuracy_NNN.json
    gap_NNN.json
    fpp_NNN.json
    sources_NNN.json
    commands_NNN.json
  responses_enriched.jsonl        # Final merged output
  YYYY-MM-DD-analysis-report.md   # Human-readable summary

~/.claude/skills/
  fprime-tui-analyze-responses/
    skill.md                      # Phase 2 orchestration instructions
  fprime-tui-agent-accuracy/
    skill.md                      # Accuracy agent — strict evaluation rules
  fprime-tui-agent-gap/
    skill.md                      # Gap agent — missing topic extraction rules
  fprime-tui-agent-fpp/
    skill.md                      # FPP syntax agent — syntax check rules
  fprime-tui-agent-sources/
    skill.md                      # Source citation agent — relevance check rules
  fprime-tui-agent-commands/
    skill.md                      # Command validity agent — tool call check rules
```

---

## Workflow

```
1. collect_responses.py finishes  →  responses.jsonl has all 685 entries

2. python3 scripts/preprocess_responses.py
   (autonomous, no LLM, writes batches + manifest.json)

3. Start Claude Code session
   → "run the response analysis"
   → fprime-tui-analyze-responses skill loads
   → subagents dispatch by concern group (parallel within group)
   → progress.json updated after each batch
   → aggregate_analysis.py runs on completion
   → responses_enriched.jsonl + analysis_report.md written

4. Review analysis_report.md
   → use fprime-tui-analyze-results skill for RAG improvement decisions
```

If interrupted at step 3, re-run step 3 — progress.json enables resume.

---

## Constraints

- `responses.jsonl` is never modified — `responses_enriched.jsonl` is the output
- Phase 1 is pure Python — no LLM, no network, safe to re-run
- Phase 2 requires an active Claude Code session (Pro subscription, no API key)
- Batch size of 25 keeps each subagent context small and focused
- Subagents write to separate result files to avoid write conflicts
- `TUI/rag/db/` and `TUI/rag/raw/` are gitignored — never commit index data
