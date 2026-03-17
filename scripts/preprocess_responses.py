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

from __future__ import annotations

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
    "not in my knowledge base",
    "not in the knowledge base",
    "not mentioned in",
    "do not have",
    "don't have",
    "no information about",
    "not aware of",
    "cannot find",
    "not enough info",
    "not enough information",
]


def extract_signals(entry: dict) -> dict:
    """Extract all deterministic signals from a single response entry."""
    response = entry.get("response", "")
    response_lower = response.lower()

    # Knowledge gap detection
    has_gap = any(re.search(r'\b' + re.escape(kw) + r'\b', response_lower) for kw in GAP_KEYWORDS)

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
    skipped = 0
    for entry in entries:
        try:
            signals_map[str(entry["id"])] = extract_signals(entry)
        except (KeyError, TypeError) as exc:
            print(f"[WARN] Skipping malformed entry: {exc}", file=sys.stderr)
            skipped += 1

    # Write signals.json for aggregator
    (ANALYSIS_DIR / "signals.json").write_text(
        json.dumps(signals_map, ensure_ascii=False, indent=2)
    )

    # Build per-concern item lists (only the fields each agent needs)
    valid_entries = [e for e in entries if str(e.get("id", "")) in signals_map]
    accuracy_items = [
        {
            "id": e["id"],
            "category": e.get("category"),
            "question": e.get("question"),
            "expected": e.get("expected"),
            "response": e.get("response"),
        }
        for e in valid_entries
    ]
    gap_items = [
        {
            "id": e["id"],
            "category": e.get("category"),
            "question": e.get("question"),
            "response": e.get("response"),
        }
        for e in valid_entries
        if signals_map[str(e["id"])]["has_gap"]
    ]
    fpp_items = [
        {
            "id": e["id"],
            "category": e.get("category"),
            "question": e.get("question"),
            "expected": e.get("expected"),
            "fpp_blocks": signals_map[str(e["id"])]["fpp_blocks"],
        }
        for e in valid_entries
        if signals_map[str(e["id"])]["has_fpp"]
    ]
    sources_items = [
        {
            "id": e["id"],
            "category": e.get("category"),
            "question": e.get("question"),
            "sources_cited": signals_map[str(e["id"])]["sources_cited"],
            "response": e.get("response", "")[:1000],
        }
        for e in valid_entries
        if signals_map[str(e["id"])]["source_count"] > 0
    ]
    commands_items = [
        {
            "id": e["id"],
            "category": e.get("category"),
            "question": e.get("question"),
            "tool_calls": signals_map[str(e["id"])]["tool_calls"],
        }
        for e in valid_entries
        if signals_map[str(e["id"])]["has_tool_call"]
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
    if skipped:
        print(f"[WARN] Skipped {skipped} malformed entries", file=sys.stderr)

    print(f"Preprocessed {len(entries)} responses")
    for concern, count in batch_counts.items():
        print(f"  {concern}: {count} batches")
    print(f"Written: {ANALYSIS_DIR}/manifest.json")
    print(f"Written: {ANALYSIS_DIR}/signals.json")


if __name__ == "__main__":
    main()
