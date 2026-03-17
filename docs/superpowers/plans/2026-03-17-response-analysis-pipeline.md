# Response Analysis Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-phase pipeline that preprocesses 685 TUI Q&A responses with Python signal extraction, then orchestrates five specialized Claude subagents to evaluate accuracy, knowledge gaps, FPP syntax, source citation quality, and command validity.

**Architecture:** Phase 1 is a pure Python script (`preprocess_responses.py`) that extracts deterministic signals and writes partitioned batch files. Phase 2 is driven by the `fprime-tui-analyze-responses` skill in a Claude Code session, which dispatches five agent-skill subagents in parallel concern groups and aggregates their results via `aggregate_analysis.py`.

**Tech Stack:** Python 3.9+, pytest, pathlib, json, re — no external dependencies. Six Claude Code skills (markdown). All outputs write to `docs/training/analysis/`.

**Spec:** `docs/superpowers/specs/2026-03-17-response-analysis-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/preprocess_responses.py` | Create | Signal extraction + batch file writing + signals.json + manifest.json |
| `scripts/aggregate_analysis.py` | Create | Load results by glob, merge by id, write enriched JSONL + report |
| `tests/analysis/__init__.py` | Create | Makes test directory a package |
| `tests/analysis/conftest.py` | Create | Adds `scripts/` to `sys.path` for imports |
| `tests/analysis/test_preprocess.py` | Create | Unit tests for signal extraction and batch partitioning |
| `tests/analysis/test_aggregate.py` | Create | Unit tests for result loading, merging, and report generation |
| `~/.claude/skills/fprime-tui-agent-accuracy/skill.md` | Create | Strict accuracy evaluation rules for subagents |
| `~/.claude/skills/fprime-tui-agent-gap/skill.md` | Create | Strict gap extraction rules for subagents |
| `~/.claude/skills/fprime-tui-agent-fpp/skill.md` | Create | Strict FPP syntax check rules for subagents |
| `~/.claude/skills/fprime-tui-agent-sources/skill.md` | Create | Strict source relevance check rules for subagents |
| `~/.claude/skills/fprime-tui-agent-commands/skill.md` | Create | Strict command validity check rules for subagents |
| `~/.claude/skills/fprime-tui-analyze-responses/skill.md` | Create | Orchestration skill — dispatches subagents, manages progress, triggers aggregation |

---

## Chunk 1: Phase 1 — Preprocessor

### Task 1: Test infrastructure

**Files:**
- Create: `tests/analysis/__init__.py`
- Create: `tests/analysis/conftest.py`

- [ ] **Step 1.1: Create `tests/analysis/__init__.py`** (empty file)

- [ ] **Step 1.2: Create `tests/analysis/conftest.py`**

```python
# tests/analysis/conftest.py
import sys
from pathlib import Path

# Allow tests to import directly from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
```

- [ ] **Step 1.3: Verify import path works**

Run: `PYTHONPATH=./TUI ./venv/bin/python -c "import sys; sys.path.insert(0, 'scripts'); print('ok')"`
Expected: `ok`

- [ ] **Step 1.4: Commit**

```bash
git add tests/analysis/__init__.py tests/analysis/conftest.py
git commit -m "test: add analysis test infrastructure with scripts/ path fixture"
```

---

### Task 2: Signal extraction (TDD)

**Files:**
- Create: `tests/analysis/test_preprocess.py` (failing tests first)
- Create: `scripts/preprocess_responses.py` (implementation)

- [ ] **Step 2.1: Write failing tests for `extract_signals()`**

Create `tests/analysis/test_preprocess.py`:

```python
# tests/analysis/test_preprocess.py
import json
import pytest
from preprocess_responses import extract_signals, make_batches


# --- extract_signals ---

def test_gap_explicit():
    entry = {"response": "This is not in my knowledge base.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_gap"] is True


def test_gap_dont_have():
    entry = {"response": "I don't have enough info to answer that.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_gap"] is True


def test_no_gap():
    entry = {"response": "The answer is that components use port arrays.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_gap"] is False


def test_fpp_block_extracted():
    entry = {"response": "Example:\n```fpp\ncomponent Foo {}\n```\nDone.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_fpp"] is True
    assert s["fpp_blocks"] == ["component Foo {}"]


def test_multiple_fpp_blocks():
    entry = {"response": "```fpp\nmodule A {}\n```\n```fpp\nmodule B {}\n```", "status": "ok"}
    s = extract_signals(entry)
    assert len(s["fpp_blocks"]) == 2


def test_no_fpp():
    entry = {"response": "No code blocks here.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_fpp"] is False
    assert s["fpp_blocks"] == []


def test_tool_call_detected():
    entry = {
        "response": '```json\n{"tool": "read_file", "path": "Fw/Types/Types.hpp"}\n```',
        "status": "ok",
    }
    s = extract_signals(entry)
    assert s["has_tool_call"] is True
    assert len(s["tool_calls"]) == 1
    assert s["tool_calls"][0]["tool"] == "read_file"


def test_json_block_without_tool_key_ignored():
    entry = {"response": '```json\n{"key": "value"}\n```', "status": "ok"}
    s = extract_signals(entry)
    assert s["has_tool_call"] is False
    assert s["tool_calls"] == []


def test_sources_extracted():
    entry = {
        "response": "Answer.\n\n*Sources: Fw/Types/docs/sdd.md · docs/reference/dictionary.md*",
        "status": "ok",
    }
    s = extract_signals(entry)
    assert s["source_count"] == 2
    assert "Fw/Types/docs/sdd.md" in s["sources_cited"]
    assert "docs/reference/dictionary.md" in s["sources_cited"]


def test_no_sources():
    entry = {"response": "Answer with no sources.", "status": "ok"}
    s = extract_signals(entry)
    assert s["source_count"] == 0
    assert s["sources_cited"] == []


def test_timeout_from_status():
    entry = {"response": "", "status": "timeout"}
    s = extract_signals(entry)
    assert s["timeout"] is True


def test_timeout_from_short_response():
    entry = {"response": "Short.", "status": "ok"}
    s = extract_signals(entry)
    assert s["timeout"] is True  # len("Short.") < 50


def test_no_timeout_normal_response():
    entry = {"response": "A" * 100, "status": "ok"}
    s = extract_signals(entry)
    assert s["timeout"] is False


# --- make_batches ---

def test_make_batches_even():
    items = list(range(50))
    batches = make_batches(items, 25)
    assert len(batches) == 2
    assert len(batches[0]) == 25
    assert len(batches[1]) == 25


def test_make_batches_ragged():
    items = list(range(685))
    batches = make_batches(items, 25)
    assert len(batches) == 28  # 27 full + 1 with 10
    assert len(batches[-1]) == 10


def test_make_batches_empty():
    assert make_batches([], 25) == []


def test_make_batches_smaller_than_size():
    items = list(range(10))
    batches = make_batches(items, 25)
    assert len(batches) == 1
    assert len(batches[0]) == 10
```

- [ ] **Step 2.2: Run tests to confirm they fail**

Run: `PYTHONPATH=./TUI ./venv/bin/python -m pytest tests/analysis/test_preprocess.py -v 2>&1 | head -20`
Expected: `ModuleNotFoundError: No module named 'preprocess_responses'`

- [ ] **Step 2.3: Implement `extract_signals()` and `make_batches()` in `scripts/preprocess_responses.py`**

```python
#!/usr/bin/env python3
"""
preprocess_responses.py — Phase 1 of the response analysis pipeline.

Reads docs/training/responses.jsonl, extracts deterministic signals for each
response, and writes partitioned batch files for the five analysis agents.

Output layout under docs/training/analysis/:
  manifest.json           — batch counts per concern
  signals.json            — {id: signals} for all responses
  batches/
    accuracy_NNN.json     — all 685 responses (25 per batch)
    gap_NNN.json          — has_gap == True responses only
    fpp_NNN.json          — has_fpp == True responses only
    sources_NNN.json      — source_count > 0 responses only
    commands_NNN.json     — has_tool_call == True responses only

Usage:
    python3 scripts/preprocess_responses.py
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).parent.parent
INPUT_FILE = PROJECT / "docs/training/responses.jsonl"
ANALYSIS_DIR = PROJECT / "docs/training/analysis"
BATCHES_DIR = ANALYSIS_DIR / "batches"
BATCH_SIZE = 25

GAP_KEYWORDS = [
    "knowledge base",
    "do not have",
    "don't have",
    "no information",
    "not aware",
    "cannot find",
    "not enough info",
]


def extract_signals(entry: dict) -> dict:
    """Extract all deterministic signals from a single response entry."""
    response = entry.get("response", "")
    response_lower = response.lower()

    # Knowledge gap detection
    has_gap = any(kw in response_lower for kw in GAP_KEYWORDS)

    # FPP code blocks
    fpp_blocks = re.findall(r"```fpp\n(.*?)```", response, re.DOTALL)
    fpp_blocks = [b.strip() for b in fpp_blocks]
    has_fpp = len(fpp_blocks) > 0

    # Tool call JSON blocks
    json_blocks = re.findall(r"```json\n(.*?)```", response, re.DOTALL)
    tool_calls = []
    for block in json_blocks:
        try:
            obj = json.loads(block.strip())
            if isinstance(obj, dict) and any(k in obj for k in ("tool", "command", "read_file")):
                tool_calls.append(obj)
        except json.JSONDecodeError:
            pass
    has_tool_call = len(tool_calls) > 0

    # Source citations from *Sources: ...* footer
    sources_match = re.search(r"\*Sources: ([^*]+)\*", response)
    sources_cited: list[str] = []
    if sources_match:
        sources_cited = [s.strip() for s in sources_match.group(1).split("·") if s.strip()]
    source_count = len(sources_cited)

    # Timeout: explicit status or suspiciously short response
    timeout = entry.get("status") == "timeout" or len(response) < 50

    return {
        "has_gap": has_gap,
        "has_fpp": has_fpp,
        "fpp_blocks": fpp_blocks,
        "has_tool_call": has_tool_call,
        "tool_calls": tool_calls,
        "source_count": source_count,
        "sources_cited": sources_cited,
        "timeout": timeout,
    }


def make_batches(items: list, size: int) -> list:
    """Partition a list into chunks of at most `size`."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def write_batches(concern: str, items: list) -> int:
    """Write batches for a concern to BATCHES_DIR. Returns batch count."""
    batches = make_batches(items, BATCH_SIZE)
    for i, batch in enumerate(batches, 1):
        path = BATCHES_DIR / f"{concern}_{i:03d}.json"
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=2))
    return len(batches)


def main() -> None:
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    entries = [
        json.loads(line)
        for line in INPUT_FILE.read_text(errors="replace").splitlines()
        if line.strip()
    ]

    BATCHES_DIR.mkdir(parents=True, exist_ok=True)

    # Extract signals for all entries
    signals_map: dict[str, dict] = {}
    for entry in entries:
        signals_map[str(entry["id"])] = extract_signals(entry)

    # Write signals.json for aggregator
    (ANALYSIS_DIR / "signals.json").write_text(
        json.dumps(signals_map, ensure_ascii=False, indent=2)
    )

    # Build per-concern item lists (only the fields each agent needs)
    accuracy_items = [
        {"id": e["id"], "category": e["category"], "question": e["question"],
         "expected": e["expected"], "response": e["response"]}
        for e in entries
    ]
    gap_items = [
        {"id": e["id"], "category": e["category"], "question": e["question"],
         "response": e["response"]}
        for e in entries if signals_map[str(e["id"])]["has_gap"]
    ]
    fpp_items = [
        {"id": e["id"], "category": e["category"], "question": e["question"],
         "expected": e["expected"], "fpp_blocks": signals_map[str(e["id"])]["fpp_blocks"]}
        for e in entries if signals_map[str(e["id"])]["has_fpp"]
    ]
    sources_items = [
        {"id": e["id"], "category": e["category"], "question": e["question"],
         "sources_cited": signals_map[str(e["id"])]["sources_cited"],
         "response": e["response"][:1000]}
        for e in entries if signals_map[str(e["id"])]["source_count"] > 0
    ]
    commands_items = [
        {"id": e["id"], "category": e["category"], "question": e["question"],
         "tool_calls": signals_map[str(e["id"])]["tool_calls"]}
        for e in entries if signals_map[str(e["id"])]["has_tool_call"]
    ]

    batch_counts = {
        "accuracy": write_batches("accuracy", accuracy_items),
        "gap": write_batches("gap", gap_items),
        "fpp": write_batches("fpp", fpp_items),
        "sources": write_batches("sources", sources_items),
        "commands": write_batches("commands", commands_items),
    }

    manifest = {
        "total": len(entries),
        "batches": batch_counts,
        "generated_at": datetime.now().isoformat(),
    }
    (ANALYSIS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"Preprocessed {len(entries)} responses")
    for concern, count in batch_counts.items():
        item_count = len(locals()[f"{concern}_items"])
        print(f"  {concern}: {item_count} items → {count} batches")
    print(f"Written: {ANALYSIS_DIR}/manifest.json")
    print(f"Written: {ANALYSIS_DIR}/signals.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2.4: Run tests — all must pass**

Run: `PYTHONPATH=./TUI ./venv/bin/python -m pytest tests/analysis/test_preprocess.py -v`
Expected: all green

- [ ] **Step 2.5: Run full lint**

Run: `make lint`
Expected: no errors

- [ ] **Step 2.6: Commit**

```bash
git add scripts/preprocess_responses.py tests/analysis/test_preprocess.py
git commit -m "feat: add preprocess_responses.py with signal extraction and batch partitioning"
```

---

### Task 3: Integration smoke test for preprocessor

- [ ] **Step 3.1: Write integration test for `write_batches()` and `main()` output**

Add to `tests/analysis/test_preprocess.py`:

```python
def test_write_batches_creates_files(tmp_path):
    from preprocess_responses import write_batches, BATCH_SIZE
    import preprocess_responses as pp
    original = pp.BATCHES_DIR
    pp.BATCHES_DIR = tmp_path

    items = [{"id": str(i)} for i in range(30)]
    count = write_batches("accuracy", items)

    pp.BATCHES_DIR = original

    assert count == 2
    assert (tmp_path / "accuracy_001.json").exists()
    assert (tmp_path / "accuracy_002.json").exists()
    batch1 = json.loads((tmp_path / "accuracy_001.json").read_text())
    assert len(batch1) == BATCH_SIZE
    batch2 = json.loads((tmp_path / "accuracy_002.json").read_text())
    assert len(batch2) == 5  # 30 - 25


def test_preprocess_manifest_and_signals(tmp_path):
    """End-to-end: write a small JSONL, run main(), check outputs."""
    import preprocess_responses as pp
    # Patch paths
    original_input = pp.INPUT_FILE
    original_analysis = pp.ANALYSIS_DIR
    original_batches = pp.BATCHES_DIR

    input_file = tmp_path / "responses.jsonl"
    entries = [
        {"id": str(i), "category": "Architecture", "question": f"Q{i}?",
         "expected": "answer", "response": "A" * 100, "status": "ok",
         "timestamp": "2026-03-17T00:00:00"}
        for i in range(1, 6)
    ]
    input_file.write_text("\n".join(json.dumps(e) for e in entries))

    pp.INPUT_FILE = input_file
    pp.ANALYSIS_DIR = tmp_path / "analysis"
    pp.BATCHES_DIR = tmp_path / "analysis" / "batches"

    pp.main()

    manifest = json.loads((tmp_path / "analysis" / "manifest.json").read_text())
    assert manifest["total"] == 5
    assert manifest["batches"]["accuracy"] == 1  # 5 items fits in 1 batch

    signals = json.loads((tmp_path / "analysis" / "signals.json").read_text())
    assert "1" in signals
    assert "has_gap" in signals["1"]

    # Restore
    pp.INPUT_FILE = original_input
    pp.ANALYSIS_DIR = original_analysis
    pp.BATCHES_DIR = original_batches
```

- [ ] **Step 3.2: Run new tests**

Run: `PYTHONPATH=./TUI ./venv/bin/python -m pytest tests/analysis/test_preprocess.py -v`
Expected: all green

- [ ] **Step 3.3: Commit**

```bash
git add tests/analysis/test_preprocess.py
git commit -m "test: add integration tests for preprocess_responses batch writing and main()"
```

---

## Chunk 2: Phase 2 — Aggregation

### Task 4: Aggregation core (TDD)

**Files:**
- Create: `tests/analysis/test_aggregate.py`
- Create: `scripts/aggregate_analysis.py`

- [ ] **Step 4.1: Write failing tests for aggregation**

Create `tests/analysis/test_aggregate.py`:

```python
# tests/analysis/test_aggregate.py
import json
import pytest
from pathlib import Path
from aggregate_analysis import load_results, enrich_entries


def test_load_results_merges_two_batches(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    batch1 = [{"id": "1", "verdict": "PASS", "reason": "correct"}]
    batch2 = [{"id": "2", "verdict": "FAIL", "reason": "wrong"}]
    (results_dir / "accuracy_001.json").write_text(json.dumps(batch1))
    (results_dir / "accuracy_002.json").write_text(json.dumps(batch2))

    results = load_results("accuracy", results_dir)

    assert results["1"] == {"verdict": "PASS", "reason": "correct"}
    assert results["2"] == {"verdict": "FAIL", "reason": "wrong"}


def test_load_results_returns_empty_when_no_files(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    assert load_results("accuracy", results_dir) == {}


def test_load_results_ignores_other_concerns(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "gap_001.json").write_text(
        json.dumps([{"id": "5", "missing_topic": "Foo", "gap_type": "explicit"}])
    )
    # Loading accuracy should not find gap files
    results = load_results("accuracy", results_dir)
    assert results == {}

    # Loading gap should find gap files
    gap_results = load_results("gap", results_dir)
    assert "5" in gap_results


def test_enrich_entries_merges_all_agents():
    entries = [
        {"id": "1", "category": "Architecture", "question": "Q?", "expected": "E",
         "response": "R", "status": "ok", "timestamp": "2026-03-17T00:00:00"}
    ]
    signals_map = {"1": {"has_gap": False, "has_fpp": False, "has_tool_call": False,
                          "timeout": False, "source_count": 0}}
    accuracy = {"1": {"verdict": "PASS", "reason": "correct"}}
    gap = {}
    fpp = {}
    sources = {}
    commands = {}

    enriched = enrich_entries(entries, signals_map, accuracy, gap, fpp, sources, commands)

    assert len(enriched) == 1
    assert enriched[0]["accuracy"] == {"verdict": "PASS", "reason": "correct"}
    assert enriched[0]["gap"] is None
    assert enriched[0]["fpp"] is None
    assert enriched[0]["sources"] is None
    assert enriched[0]["commands"] is None
    assert enriched[0]["signals"]["has_gap"] is False


def test_enrich_entries_all_685_present_even_if_no_verdict():
    """All entries appear in output, even those not processed by an agent."""
    entries = [
        {"id": str(i), "category": "Modeling", "question": "Q?", "expected": "E",
         "response": "R" * 100, "status": "ok", "timestamp": "2026-03-17T00:00:00"}
        for i in range(1, 4)
    ]
    signals_map = {str(i): {"has_gap": False, "has_fpp": False, "has_tool_call": False,
                             "timeout": False, "source_count": 0} for i in range(1, 4)}
    # Only id "2" has an accuracy verdict
    accuracy = {"2": {"verdict": "PARTIAL", "reason": "incomplete"}}

    enriched = enrich_entries(entries, signals_map, accuracy, {}, {}, {}, {})

    assert len(enriched) == 3
    assert enriched[0]["accuracy"] is None   # id "1" — no verdict
    assert enriched[1]["accuracy"] == {"verdict": "PARTIAL", "reason": "incomplete"}
    assert enriched[2]["accuracy"] is None   # id "3" — no verdict
```

- [ ] **Step 4.2: Run tests to confirm they fail**

Run: `PYTHONPATH=./TUI ./venv/bin/python -m pytest tests/analysis/test_aggregate.py -v 2>&1 | head -10`
Expected: `ModuleNotFoundError: No module named 'aggregate_analysis'`

- [ ] **Step 4.3: Implement `load_results()` and `enrich_entries()` in `scripts/aggregate_analysis.py`**

```python
#!/usr/bin/env python3
"""
aggregate_analysis.py — Phase 2 aggregation for the response analysis pipeline.

Reads:
  docs/training/analysis/signals.json          — per-response signals from Phase 1
  docs/training/analysis/results/<c>_NNN.json  — agent verdict files
  docs/training/responses.jsonl                — original responses

Writes:
  docs/training/analysis/responses_enriched.jsonl
  docs/training/analysis/YYYY-MM-DD-analysis-report.md

Usage:
    python3 scripts/aggregate_analysis.py
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).parent.parent
INPUT_FILE = PROJECT / "docs/training/responses.jsonl"
ANALYSIS_DIR = PROJECT / "docs/training/analysis"
RESULTS_DIR = ANALYSIS_DIR / "results"
SIGNALS_FILE = ANALYSIS_DIR / "signals.json"


def load_results(concern: str, results_dir: Path) -> dict:
    """Load all result files for a concern. Returns {id: verdict_dict}."""
    results: dict[str, dict] = {}
    for f in sorted(results_dir.glob(f"{concern}_*.json")):
        items = json.loads(f.read_text())
        for item in items:
            item_id = str(item["id"])
            results[item_id] = {k: v for k, v in item.items() if k != "id"}
    return results


def enrich_entries(
    entries: list,
    signals_map: dict,
    accuracy: dict,
    gap: dict,
    fpp: dict,
    sources: dict,
    commands: dict,
) -> list:
    """Merge all agent verdicts and signals onto each response entry."""
    enriched = []
    for entry in entries:
        eid = str(entry["id"])
        enriched.append({
            **entry,
            "signals": signals_map.get(eid, {}),
            "accuracy": accuracy.get(eid),
            "gap": gap.get(eid),
            "fpp": fpp.get(eid),
            "sources": sources.get(eid),
            "commands": commands.get(eid),
        })
    return enriched


def generate_report(enriched: list, date_str: str) -> str:
    """Generate the 5-section markdown analysis report."""
    lines = [f"# F' TUI Response Analysis Report — {date_str}", ""]

    # Section 1: Accuracy Scorecard
    lines += ["## 1. Accuracy Scorecard", ""]
    by_category: dict[str, list] = defaultdict(list)
    for entry in enriched:
        if entry.get("accuracy"):
            by_category[entry["category"]].append(entry["accuracy"]["verdict"])

    header = "| Category | Total | PASS | PARTIAL | FAIL |"
    sep    = "|----------|-------|------|---------|------|"
    lines += [header, sep]

    totals = Counter()
    for cat, verdicts in sorted(by_category.items()):
        c = Counter(verdicts)
        total = len(verdicts)
        totals.update(c)
        totals["total"] += total
        lines.append(
            f"| {cat} | {total} "
            f"| {c['PASS']} ({100*c['PASS']//total}%) "
            f"| {c['PARTIAL']} ({100*c['PARTIAL']//total}%) "
            f"| {c['FAIL']} ({100*c['FAIL']//total}%) |"
        )
    t = totals["total"]
    if t:
        lines.append(
            f"| **Total** | {t} "
            f"| {totals['PASS']} ({100*totals['PASS']//t}%) "
            f"| {totals['PARTIAL']} ({100*totals['PARTIAL']//t}%) "
            f"| {totals['FAIL']} ({100*totals['FAIL']//t}%) |"
        )
    lines.append("")

    # Section 2: Knowledge Gap Index
    lines += ["## 2. Knowledge Gap Index", ""]
    topic_counts: Counter = Counter()
    topic_cat: dict[str, str] = {}
    for entry in enriched:
        if entry.get("gap") and entry["gap"].get("missing_topic"):
            topic = entry["gap"]["missing_topic"]
            topic_counts[topic] += 1
            topic_cat[topic] = entry["category"]
    lines.append("Top missing topics (by frequency):")
    lines.append("")
    for topic, count in topic_counts.most_common(20):
        lines.append(f"- [{count}×] {topic} ({topic_cat[topic]})")
    lines.append("")

    # Section 3: FPP Issue Summary
    lines += ["## 3. FPP Issue Summary", ""]
    fpp_severities: Counter = Counter()
    major_examples = []
    for entry in enriched:
        if entry.get("fpp"):
            fpp_severities[entry["fpp"].get("severity", "ok")] += 1
            if entry["fpp"].get("severity") == "major" and len(major_examples) < 5:
                major_examples.append(entry)
    lines.append(f"- ok: {fpp_severities['ok']}")
    lines.append(f"- minor: {fpp_severities['minor']}")
    lines.append(f"- major: {fpp_severities['major']}")
    lines.append("")
    if major_examples:
        lines.append("**Major issue examples:**")
        lines.append("")
        for ex in major_examples:
            lines.append(f"**Q{ex['id']}** — {ex['question'][:80]}")
            for issue in ex["fpp"].get("issues", []):
                lines.append(f"  - {issue}")
            lines.append("")

    # Section 4: Source Citation Quality
    lines += ["## 4. Source Citation Quality", ""]
    src_by_cat: dict[str, list] = defaultdict(list)
    for entry in enriched:
        if entry.get("sources"):
            src_by_cat[entry["category"]].append(entry["sources"].get("relevant", False))
    header = "| Category | With Sources | Relevant | Irrelevant |"
    sep    = "|----------|-------------|----------|------------|"
    lines += [header, sep]
    for cat, relevance_list in sorted(src_by_cat.items()):
        total = len(relevance_list)
        relevant = sum(1 for r in relevance_list if r)
        irrelevant = total - relevant
        lines.append(
            f"| {cat} | {total} "
            f"| {relevant} ({100*relevant//total}%) "
            f"| {irrelevant} ({100*irrelevant//total}%) |"
        )
    lines.append("")

    # Section 5: Command Validity Summary
    lines += ["## 5. Command Validity Summary", ""]
    for entry in enriched:
        if entry.get("commands"):
            verdict = "valid" if entry["commands"].get("valid") else "invalid"
            issues = "; ".join(entry["commands"].get("issues", []))
            tool_calls = entry["commands"].get("tool_calls_summary", "")
            lines.append(f"Q{entry['id']}: {tool_calls} → {verdict}" + (f" — {issues}" if issues else ""))
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    if not INPUT_FILE.exists():
        print(f"[ERROR] {INPUT_FILE} not found", file=sys.stderr)
        sys.exit(1)
    if not SIGNALS_FILE.exists():
        print(f"[ERROR] {SIGNALS_FILE} not found — run preprocess_responses.py first", file=sys.stderr)
        sys.exit(1)
    if not RESULTS_DIR.exists():
        print(f"[ERROR] {RESULTS_DIR} not found — run analysis session first", file=sys.stderr)
        sys.exit(1)

    entries = [
        json.loads(line)
        for line in INPUT_FILE.read_text(errors="replace").splitlines()
        if line.strip()
    ]
    signals_map = json.loads(SIGNALS_FILE.read_text())

    accuracy = load_results("accuracy", RESULTS_DIR)
    gap = load_results("gap", RESULTS_DIR)
    fpp = load_results("fpp", RESULTS_DIR)
    sources = load_results("sources", RESULTS_DIR)
    commands = load_results("commands", RESULTS_DIR)

    enriched = enrich_entries(entries, signals_map, accuracy, gap, fpp, sources, commands)

    out_file = ANALYSIS_DIR / "responses_enriched.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for entry in enriched:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    date_str = datetime.now().strftime("%Y-%m-%d")
    report = generate_report(enriched, date_str)
    report_file = ANALYSIS_DIR / f"{date_str}-analysis-report.md"
    report_file.write_text(report)

    print(f"Written: {out_file} ({len(enriched)} entries)")
    print(f"Written: {report_file}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4.4: Run tests — all must pass**

Run: `PYTHONPATH=./TUI ./venv/bin/python -m pytest tests/analysis/test_aggregate.py -v`
Expected: all green

- [ ] **Step 4.5: Run full test suite**

Run: `make test`
Expected: all green, lint passes

- [ ] **Step 4.6: Commit**

```bash
git add scripts/aggregate_analysis.py tests/analysis/test_aggregate.py
git commit -m "feat: add aggregate_analysis.py with result loading, merging, and report generation"
```

---

## Chunk 3: Skills

### Task 5: Five agent skills

Each skill is a markdown file. No tests — correctness is validated by the orchestration skill invoking them and reviewing sample output.

**Files:**
- Create: `~/.claude/skills/fprime-tui-agent-accuracy/skill.md`
- Create: `~/.claude/skills/fprime-tui-agent-gap/skill.md`
- Create: `~/.claude/skills/fprime-tui-agent-fpp/skill.md`
- Create: `~/.claude/skills/fprime-tui-agent-sources/skill.md`
- Create: `~/.claude/skills/fprime-tui-agent-commands/skill.md`

- [ ] **Step 5.1: Create `~/.claude/skills/fprime-tui-agent-accuracy/skill.md`**

```markdown
---
name: fprime-tui-agent-accuracy
description: Evaluates TUI responses against ground-truth expected answers for F' training data. Use when processing an accuracy batch file.
---

# Accuracy Agent

You are a strict F' TUI response evaluator. Your only job is to evaluate each
item in a batch file and write a JSON result file.

## Input

You will be given two paths:
- **Batch file** (read this): a JSON array of objects with fields:
  `id`, `category`, `question`, `expected`, `response`
- **Result file** (write this): path where you must write your output

Read the batch file. Evaluate every item. Write the result file. Do nothing else.

## Evaluation Rules

For each item, compare `response` to `expected` semantically:

**PASS** — Response clearly conveys the key concepts, correct values, and correct
terminology from `expected`. Minor phrasing differences are fine. A response that
correctly says "I don't have information on this specific topic" when the expected
answer is also narrow/obscure MAY be PASS if the hedge is accurate.

**PARTIAL** — Response addresses the topic and shows partial understanding but
is missing one or more key concepts from `expected`, OR contains minor factual
inaccuracies that don't completely invalidate the answer.

**FAIL** — Response is factually wrong, evasive without justification, completely
misses what `expected` describes, or deflects to a different topic entirely.

## Output Contract

Write a JSON array to the result file. One object per input item, in the same
order. Every item from the batch MUST appear in the output — no skipping.

```json
[
  {"id": "1", "verdict": "PASS", "reason": "Correctly identifies port arrays and base ID namespace."},
  {"id": "2", "verdict": "FAIL", "reason": "Describes task scheduling, not the startTasks lifecycle phase."}
]
```

**Hard rules:**
- `verdict` MUST be exactly `"PASS"`, `"PARTIAL"`, or `"FAIL"` — no other values
- `reason` MUST be one sentence, specific to this response (not generic)
- Every item in the batch MUST have an output entry
- Do NOT add fields beyond `id`, `verdict`, `reason`
- Do NOT modify the batch file
- Do NOT summarize or explain your process — only write the result file
```

- [ ] **Step 5.2: Create `~/.claude/skills/fprime-tui-agent-gap/skill.md`**

```markdown
---
name: fprime-tui-agent-gap
description: Extracts missing knowledge topics from F' TUI responses that show knowledge gaps. Use when processing a gap batch file.
---

# Gap Agent

You are a knowledge gap extractor for the F' TUI training pipeline. Your only
job is to identify what specific topic is missing from the knowledge base and
classify the gap type.

## Input

You will be given two paths:
- **Batch file** (read this): a JSON array of objects with fields:
  `id`, `category`, `question`, `response`
- **Result file** (write this): path where you must write your output

All items in this batch have already been flagged as containing gap language.
Read the batch file. Classify every item. Write the result file.

## Classification Rules

**`missing_topic`** — A specific, concise name for what the TUI doesn't know.
Be precise: not "F' internals" but "Fw::ExternalString buffer constructor".
Not "build system" but "fprime-util generate --ut flag".

**`gap_type`:**
- `explicit` — TUI directly states the topic is not in its knowledge base
  (e.g., "not mentioned in the provided F' knowledge base sources")
- `hedged` — TUI softens without directly admitting the gap
  (e.g., "you may want to consult additional documentation")
- `deflection` — TUI changes subject, gives a completely generic answer,
  or answers a different question than was asked

## Output Contract

Write a JSON array to the result file. One object per input item, in same order.
Every item MUST appear in output.

```json
[
  {"id": "112", "missing_topic": "FW_OPTIONAL_NAME macro", "gap_type": "explicit"},
  {"id": "87", "missing_topic": "fprime-util purge --all behavior", "gap_type": "hedged"}
]
```

**Hard rules:**
- `gap_type` MUST be exactly `"explicit"`, `"hedged"`, or `"deflection"`
- `missing_topic` MUST be specific — generic topic names are not acceptable
- Every item in the batch MUST have an output entry
- Do NOT add fields beyond `id`, `missing_topic`, `gap_type`
- Do NOT modify the batch file
```

- [ ] **Step 5.3: Create `~/.claude/skills/fprime-tui-agent-fpp/skill.md`**

```markdown
---
name: fprime-tui-agent-fpp
description: Validates FPP syntax in F' TUI responses against known-correct FPP patterns. Use when processing an FPP batch file.
---

# FPP Syntax Agent

You are an FPP (F Prime Prime) syntax validator. Your only job is to check
extracted FPP code blocks for correctness and write a result file.

## Input

You will be given two paths:
- **Batch file** (read this): a JSON array of objects with fields:
  `id`, `category`, `question`, `expected`, `fpp_blocks` (list of code strings)
- **Result file** (write this): path where you must write your output

## FPP Syntax Reference

Valid FPP constructs include:
- `module <Name> { ... }` — namespace
- `component <Name> { ... }` — component definition
- `active component`, `passive component`, `queued component`
- `port <name>: <Type>` — port declaration
- `command <name>` — command declaration
- `event <name>` — event declaration
- `telemetry <name>: <Type>` — telemetry channel
- `param <name>: <Type>` — parameter
- `instance <name>: <Type> base id <N>` — topology instance
- `topology <Name> { ... }` — topology definition
- `connect <a>.<p> to <b>.<q>` — port connection

**Common errors to flag:**
- C++/Java syntax inside FPP blocks (`class`, `void`, `int main()`, `#include`)
- Wrong keyword (`component type` instead of `active component`)
- Made-up port types or module names not in standard F' framework
- Missing `base id` in topology instance declarations

## Evaluation Rules

**`ok`** — FPP blocks are syntactically plausible and use correct keywords.
**`minor`** — Suboptimal style or non-standard approach but functionally plausible.
**`major`** — Wrong keyword, invalid syntax structure, or made-up FPP construct.

## Output Contract

Write a JSON array to the result file. One object per input item, in same order.

```json
[
  {"id": "10", "has_issues": false, "issues": [], "severity": "ok"},
  {"id": "55", "has_issues": true, "issues": ["Uses 'class' keyword — not valid FPP syntax"], "severity": "major"}
]
```

**Hard rules:**
- `severity` MUST be exactly `"ok"`, `"minor"`, or `"major"`
- `has_issues` MUST be `false` when `severity` is `"ok"`
- `issues` MUST be an array (empty array if no issues)
- Every item in the batch MUST have an output entry
- Do NOT add fields beyond `id`, `has_issues`, `issues`, `severity`
- Do NOT modify the batch file
```

- [ ] **Step 5.4: Create `~/.claude/skills/fprime-tui-agent-sources/skill.md`**

```markdown
---
name: fprime-tui-agent-sources
description: Evaluates whether RAG source citations in F' TUI responses are relevant to the question asked. Use when processing a sources batch file.
---

# Source Citation Agent

You are a RAG retrieval quality evaluator. Your only job is to determine whether
the sources cited in a TUI response are actually relevant to the question asked.

## Input

You will be given two paths:
- **Batch file** (read this): a JSON array of objects with fields:
  `id`, `category`, `question`, `sources_cited` (list of filenames), `response`
- **Result file** (write this): path where you must write your output

## Relevance Rules

**`relevant: true`** — At least one cited source plausibly contains information
needed to answer this question. A source about `Fw/Types/docs/sdd.md` is relevant
to a question about F' type system. A source about `Drv/Ip/docs/sdd.md` is
relevant to a question about IP drivers.

**`relevant: false`** — The cited sources are clearly unrelated to the question.
A question about FPP modeling that cites only `docs/getting-started/installing-fprime.md`
is irrelevant. A question about UART drivers that cites only documentation about
the GDS is irrelevant.

This signal separates three RAG failure modes:
- FAIL + no sources → knowledge gap (nothing retrieved)
- FAIL + irrelevant sources → retrieval quality problem (wrong chunks)
- FAIL + relevant sources → reasoning problem (right info, wrong answer)

## Output Contract

Write a JSON array to the result file. One object per input item, in same order.

```json
[
  {"id": "314", "relevant": true, "reason": "Fw/Types/docs/sdd.md directly covers the type system question."},
  {"id": "22", "relevant": false, "reason": "Installing-fprime.md does not cover FPP topology syntax."}
]
```

**Hard rules:**
- `relevant` MUST be a boolean (`true` or `false`)
- `reason` MUST be one sentence explaining the relevance judgement
- Every item in the batch MUST have an output entry
- Do NOT add fields beyond `id`, `relevant`, `reason`
- Do NOT modify the batch file
```

- [ ] **Step 5.5: Create `~/.claude/skills/fprime-tui-agent-commands/skill.md`**

```markdown
---
name: fprime-tui-agent-commands
description: Validates tool call attempts in F' TUI MISSION_CONTROL responses. Use when processing a commands batch file.
---

# Command Validity Agent

You are a tool call validator for the F' TUI. Your only job is to check whether
tool call attempts in TUI responses are logically sound.

## Input

You will be given two paths:
- **Batch file** (read this): a JSON array of objects with fields:
  `id`, `category`, `question`, `tool_calls` (list of parsed tool call objects)
- **Result file** (write this): path where you must write your output

## Validation Rules

For each tool call, check:

**`read_file` calls:**
- Does the path target a file that plausibly exists in the F' framework?
  (e.g., `Fw/Types/Types.hpp`, `docs/user-manual/framework/state-machines.md`)
- Paths like `fprime/Src/Components/Foo.cpp` or made-up module paths are invalid.

**`run_command` calls:**
- Valid `fprime-util` subcommands: `generate`, `build`, `check`, `install`, `purge`,
  `hash-to-file`, `new`, `format`
- Any other command name is invalid.

**Reasoning check:**
- Is the tool call logically appropriate for the question asked?
  A `read_file` on a type header for a question about UDP sockets is invalid reasoning.

**`valid: true`** — All tool calls are logically sound and target plausible resources.
**`valid: false`** — At least one tool call has an invalid path, wrong command, or
illogical reasoning for the question.

## Output Contract

Write a JSON array to the result file. One object per input item, in same order.

```json
[
  {"id": "50", "valid": true, "issues": []},
  {"id": "73", "valid": false, "issues": ["run_command uses 'fprime-util compile' — not a valid subcommand"]}
]
```

**Hard rules:**
- `valid` MUST be a boolean
- `issues` MUST be an array (empty if valid)
- Every item in the batch MUST have an output entry
- Do NOT add fields beyond `id`, `valid`, `issues`
- Do NOT modify the batch file
```

- [ ] **Step 5.6: Commit all five agent skills**

```bash
git add \
  ~/.claude/skills/fprime-tui-agent-accuracy/skill.md \
  ~/.claude/skills/fprime-tui-agent-gap/skill.md \
  ~/.claude/skills/fprime-tui-agent-fpp/skill.md \
  ~/.claude/skills/fprime-tui-agent-sources/skill.md \
  ~/.claude/skills/fprime-tui-agent-commands/skill.md
git commit -m "feat: add five analysis agent skills with strict input/output contracts"
```

---

### Task 6: Orchestration skill

**Files:**
- Create: `~/.claude/skills/fprime-tui-analyze-responses/skill.md`

- [ ] **Step 6.1: Create `~/.claude/skills/fprime-tui-analyze-responses/skill.md`**

```markdown
---
name: fprime-tui-analyze-responses
description: Orchestrates the five F' TUI response analysis agents. Use when the user says "run the response analysis" or similar.
---

# F' TUI Response Analysis Orchestrator

You are orchestrating the Phase 2 analysis pipeline. Work through these steps
exactly. Do not deviate.

## Prerequisites

Verify these files exist before starting:
- `docs/training/analysis/manifest.json` — if missing, tell user to run `python3 scripts/preprocess_responses.py` first
- `docs/training/analysis/signals.json` — same
- `docs/training/analysis/batches/` directory — same

Read `manifest.json` to get batch counts per concern:
```json
{"total": 685, "batches": {"accuracy": 28, "gap": 5, "fpp": 8, "sources": 12, "commands": 2}}
```

## Checkpoint

Check if `docs/training/analysis/progress.json` exists. If it does, read it to
identify already-completed batches and skip them:
```json
{"accuracy": ["accuracy_001", "accuracy_002"], "gap": [], "fpp": [], "sources": [], "commands": [], "last_updated": "..."}
```

If progress.json does not exist, initialize it with all concerns as empty arrays.

## Concern Group 1 — Small agents (dispatch in parallel)

Dispatch ALL remaining batches for gap, fpp, sources, and commands in a single
message using parallel Agent tool calls. Each subagent call must:
1. Invoke the appropriate agent skill (`fprime-tui-agent-gap`, etc.)
2. Tell the subagent: the batch file path to read and result file path to write
3. The result file path follows the convention: `docs/training/analysis/results/<batchfile_name>.json`
   (same filename as batch, but in results/ instead of batches/)

Example prompt for a gap subagent:
> "Use the fprime-tui-agent-gap skill. Batch file: docs/training/analysis/batches/gap_001.json. Write results to: docs/training/analysis/results/gap_001.json"

Create `docs/training/analysis/results/` directory before dispatching if it does not exist.

After all Group 1 subagents complete, update `progress.json` with completed batch IDs.

## Concern Group 2 — Accuracy (dispatch in groups of 10)

Dispatch accuracy batches in groups of 10 parallel subagents at a time. For each group:
1. Dispatch up to 10 remaining accuracy batches in a single message (parallel Agent calls)
2. Each subagent invokes `fprime-tui-agent-accuracy`
3. Wait for all 10 to complete
4. Update `progress.json` with completed batch IDs
5. Repeat until all accuracy batches are done

Example prompt for an accuracy subagent:
> "Use the fprime-tui-agent-accuracy skill. Batch file: docs/training/analysis/batches/accuracy_001.json. Write results to: docs/training/analysis/results/accuracy_001.json"

## Aggregation

After all batches complete, run:
```bash
PYTHONPATH=./TUI ./venv/bin/python scripts/aggregate_analysis.py
```

## Completion Report

Print a summary:
```
=== Analysis Complete ===
Batches processed:
  accuracy: N
  gap: N
  fpp: N
  sources: N
  commands: N
Outputs:
  docs/training/analysis/responses_enriched.jsonl
  docs/training/analysis/YYYY-MM-DD-analysis-report.md
```

## Hard Rules

- NEVER skip a batch without updating progress.json
- NEVER write to responses.jsonl — it is read-only
- NEVER run preprocess_responses.py — that is the user's step
- If a subagent fails (no result file written), log the batch ID and continue — do not retry
- All result files go in `docs/training/analysis/results/` — never in batches/
```

- [ ] **Step 6.2: Commit orchestration skill**

```bash
git add ~/.claude/skills/fprime-tui-analyze-responses/skill.md
git commit -m "feat: add fprime-tui-analyze-responses orchestration skill"
```

---

### Task 7: Final verification

- [ ] **Step 7.1: Run full test suite one last time**

Run: `make test`
Expected: all green

- [ ] **Step 7.2: Smoke test preprocessor against live data**

Run: `PYTHONPATH=./TUI ./venv/bin/python scripts/preprocess_responses.py`
Expected output similar to:
```
Preprocessed 315 responses
  accuracy: 315 items → 13 batches
  gap: 85 items → 4 batches
  fpp: 123 items → 5 batches
  sources: 280 items → 12 batches
  commands: 8 items → 1 batches
Written: docs/training/analysis/manifest.json
Written: docs/training/analysis/signals.json
```

- [ ] **Step 7.3: Verify batch file structure**

Run: `python3 -c "import json; b = json.load(open('docs/training/analysis/batches/accuracy_001.json')); print(len(b), 'items'); print(list(b[0].keys()))"`
Expected: `25 items` and `['id', 'category', 'question', 'expected', 'response']`

- [ ] **Step 7.4: Final commit**

```bash
git add docs/superpowers/specs/2026-03-17-response-analysis-design.md \
        docs/superpowers/plans/2026-03-17-response-analysis-pipeline.md
git commit -m "docs: add response analysis pipeline spec and implementation plan"
```
