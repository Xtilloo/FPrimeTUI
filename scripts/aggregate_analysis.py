#!/usr/bin/env python3
"""
aggregate_analysis.py — Phase 2 aggregation for the response analysis pipeline.

Reads:
  docs/training/analysis/signals.json          — per-response signals from Phase 1
  docs/training/analysis/results/<c>_NNN.json  — agent verdict files (by concern)
  docs/training/responses.jsonl                — original responses

Writes:
  docs/training/analysis/responses_enriched.jsonl
  docs/training/analysis/YYYY-MM-DD-analysis-report.md

Usage:
    python3 scripts/aggregate_analysis.py
"""

from __future__ import annotations

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
    lines: list[str] = [f"# F' TUI Response Analysis Report — {date_str}", ""]

    # Section 1: Accuracy Scorecard
    lines += ["## 1. Accuracy Scorecard", ""]
    by_category: dict[str, list] = defaultdict(list)
    for entry in enriched:
        if entry.get("accuracy"):
            by_category[entry["category"]].append(entry["accuracy"]["verdict"])

    lines += ["| Category | Total | PASS | PARTIAL | FAIL |",
              "|----------|-------|------|---------|------|"]
    totals: Counter = Counter()
    for cat, verdicts in sorted(by_category.items()):
        c = Counter(verdicts)
        total = len(verdicts)
        totals.update(c)
        totals["total"] += total
        lines.append(
            f"| {cat} | {total} "
            f"| {c['PASS']} ({100 * c['PASS'] // total if total else 0}%) "
            f"| {c['PARTIAL']} ({100 * c['PARTIAL'] // total if total else 0}%) "
            f"| {c['FAIL']} ({100 * c['FAIL'] // total if total else 0}%) |"
        )
    t = totals["total"]
    if t:
        lines.append(
            f"| **Total** | {t} "
            f"| {totals['PASS']} ({100 * totals['PASS'] // t}%) "
            f"| {totals['PARTIAL']} ({100 * totals['PARTIAL'] // t}%) "
            f"| {totals['FAIL']} ({100 * totals['FAIL'] // t}%) |"
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
        lines.append(f"- [{count}×] {topic} ({topic_cat.get(topic, 'Unknown')})")
    lines.append("")

    # Section 3: FPP Issue Summary
    lines += ["## 3. FPP Issue Summary", ""]
    fpp_severities: Counter = Counter()
    major_examples: list[dict] = []
    for entry in enriched:
        if entry.get("fpp"):
            fpp_severities[entry["fpp"].get("severity", "ok")] += 1
            if entry["fpp"].get("severity") == "major" and len(major_examples) < 5:
                major_examples.append(entry)
    lines += [
        f"- ok: {fpp_severities['ok']}",
        f"- minor: {fpp_severities['minor']}",
        f"- major: {fpp_severities['major']}",
        "",
    ]
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
    lines += ["| Category | With Sources | Relevant | Irrelevant |",
              "|----------|-------------|----------|------------|"]
    for cat, relevance_list in sorted(src_by_cat.items()):
        total = len(relevance_list)
        relevant = sum(1 for r in relevance_list if r)
        irrelevant = total - relevant
        lines.append(
            f"| {cat} | {total} "
            f"| {relevant} ({100 * relevant // total if total else 0}%) "
            f"| {irrelevant} ({100 * irrelevant // total if total else 0}%) |"
        )
    lines.append("")

    # Section 5: Command Validity Summary
    lines += ["## 5. Command Validity Summary", ""]
    cmd_entries = [e for e in enriched if e.get("commands")]
    if cmd_entries:
        for entry in cmd_entries:
            verdict = "valid" if entry["commands"].get("valid") else "invalid"
            issues = "; ".join(entry["commands"].get("issues", []))
            suffix = f" — {issues}" if issues else ""
            lines.append(f"Q{entry['id']}: {verdict}{suffix}")
    else:
        lines.append("No tool call attempts detected.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    for path, label in [(INPUT_FILE, "responses.jsonl"),
                        (SIGNALS_FILE, "signals.json (run preprocess_responses.py first)"),
                        (RESULTS_DIR, "results/ directory (run analysis session first)")]:
        if not path.exists():
            print(f"[ERROR] Not found: {path} — {label}", file=sys.stderr)
            sys.exit(1)

    entries = [
        json.loads(line)
        for line in INPUT_FILE.read_text(errors="replace").splitlines()
        if line.strip()
    ]
    signals_map: dict[str, dict] = json.loads(SIGNALS_FILE.read_text())

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
