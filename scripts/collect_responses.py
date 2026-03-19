#!/usr/bin/env python3
"""
collect_responses.py — TUI Response Collector

Sends every question from fprime_training.md to the TUI via CMUX and
captures the full response from the session log. No verifiers, no LLM agents.

Output: docs/training/responses.jsonl
  One JSON object per line:
    {"id": "1", "category": "Architecture", "question": "...",
     "expected": "...", "response": "...", "status": "ok"|"timeout",
     "timestamp": "..."}

Usage:
    # Write TUI surface ID first:
    echo -n "surface:N" > docs/training/tui_surface.txt

    # Run (resumes automatically from checkpoint):
    python3 -u scripts/collect_responses.py

    # Reset and start over:
    python3 -u scripts/collect_responses.py --reset
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT = Path("/Users/xtilloo/Projects/FPrimeTUI")
TRAINING_FILE = PROJECT / "docs/training/fprime_training.md"
OUTPUT_FILE = PROJECT / "docs/training/responses.jsonl"
CHECKPOINT_FILE = PROJECT / "docs/training/collect_checkpoint.json"
TUI_SURFACE_FILE = PROJECT / "docs/training/tui_surface.txt"
SESSION_LOG = PROJECT / "ClaudesLogs" / "sessions" / f"{datetime.now().strftime('%Y-%m-%d')}-raw.log"

RESPONSE_TIMEOUT = 120   # seconds to wait for TUI response
POLL_INTERVAL = 3        # seconds between log polls
MIN_RESPONSE_LEN = 50    # chars — below this is considered no response
CLEAR_WAIT = 3           # seconds after /clear before sending question


def load_questions() -> list[dict]:
    content = TRAINING_FILE.read_text(encoding="utf-8")
    questions = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        if "| ID |" in line or "| :---" in line or "ID | Category" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 4:
            continue
        qid = parts[0].strip()
        if not qid.isdigit():
            continue
        questions.append({
            "id": qid,
            "category": parts[1].strip(),
            "question": parts[2].strip(),
            "expected": parts[3].strip(),
        })
    return questions


def load_checkpoint() -> int:
    if CHECKPOINT_FILE.exists():
        try:
            cp = json.loads(CHECKPOINT_FILE.read_text())
            val = cp.get("last_completed", 0)
            return int(val) if str(val).isdigit() else 0
        except Exception:
            pass
    return 0


def save_checkpoint(qid: str) -> None:
    CHECKPOINT_FILE.write_text(json.dumps({"last_completed": int(qid)}))


def load_completed_ids() -> set[str]:
    """Read output file to find already-collected question IDs."""
    completed = set()
    if OUTPUT_FILE.exists():
        for line in OUTPUT_FILE.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                completed.add(str(json.loads(line)["id"]))
            except Exception:
                pass
    return completed


def get_tui_surface() -> str:
    if TUI_SURFACE_FILE.exists():
        surface = TUI_SURFACE_FILE.read_text().strip()
        if surface:
            return surface
    print("[ERROR] docs/training/tui_surface.txt not found or empty.", file=sys.stderr)
    print("  Write the TUI surface ID before running:", file=sys.stderr)
    print("    echo -n 'surface:N' > docs/training/tui_surface.txt", file=sys.stderr)
    sys.exit(1)


def cmux_send(surface: str, text: str) -> None:
    subprocess.run(["cmux", "send", "--surface", surface, text], check=True)


def get_log_offset() -> int:
    if SESSION_LOG.exists():
        return SESSION_LOG.stat().st_size
    return 0


def wait_for_response(offset: int) -> tuple[str, str]:
    """
    Poll session log for a new ---RESPONSE--- block after `offset`.
    Returns (response_text, status) where status is 'ok' or 'timeout'.
    """
    deadline = time.time() + RESPONSE_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        if not SESSION_LOG.exists():
            continue
        with open(SESSION_LOG, "rb") as f:
            f.seek(offset)
            new_content = f.read().decode("utf-8", errors="replace")
        if "---RESPONSE---" in new_content:
            after = new_content.split("---RESPONSE---", 1)[1].strip()
            if len(after) >= MIN_RESPONSE_LEN:
                return after, "ok"
    return "", "timeout"


def append_result(entry: dict) -> None:
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect TUI responses for all training questions.")
    parser.add_argument("--reset", action="store_true", help="Clear checkpoint and output, start from Q1.")
    args = parser.parse_args()

    if args.reset:
        CHECKPOINT_FILE.unlink(missing_ok=True)
        OUTPUT_FILE.unlink(missing_ok=True)
        print("Reset: checkpoint and output file cleared.")

    print("=" * 60)
    print("F PRIME TUI — RESPONSE COLLECTOR")
    print(f"Started:    {datetime.now().isoformat()}")
    print(f"Output:     {OUTPUT_FILE.relative_to(PROJECT)}")
    print(f"Session log:{SESSION_LOG.relative_to(PROJECT)}")
    print("=" * 60)

    questions = load_questions()
    print(f"Loaded {len(questions)} questions from training file.")

    # Resume: skip already-collected IDs (more reliable than checkpoint alone)
    completed_ids = load_completed_ids()
    remaining = [q for q in questions if q["id"] not in completed_ids]
    print(f"Already collected: {len(completed_ids)}  |  Remaining: {len(remaining)}")

    if not remaining:
        print("All questions already collected. Done.")
        return

    tui_surface = get_tui_surface()
    print(f"TUI surface: {tui_surface}")
    print()

    ok_count = 0
    timeout_count = 0

    for i, q in enumerate(remaining):
        qid = q["id"]
        print(f"[Q{qid}/{len(questions)}] {q['question'][:70]}...")

        # Clear TUI context
        cmux_send(tui_surface, "/clear\n")
        time.sleep(CLEAR_WAIT)

        # Record log position before sending
        offset = get_log_offset()

        # Send question
        cmux_send(tui_surface, q["question"] + "\n")

        # Wait for response
        response, status = wait_for_response(offset)

        if status == "ok":
            ok_count += 1
            print(f"  -> {len(response)} chars")
        else:
            timeout_count += 1
            print(f"  -> TIMEOUT (no response in {RESPONSE_TIMEOUT}s)")

        # Write result
        entry = {
            "id": qid,
            "category": q["category"],
            "question": q["question"],
            "expected": q["expected"],
            "response": response,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        append_result(entry)
        save_checkpoint(qid)

        # Progress summary every 25 questions
        done = i + 1
        if done % 25 == 0:
            total_done = len(completed_ids) + done
            print(f"\n-- Progress: {total_done}/{len(questions)} total | "
                  f"ok={ok_count} timeout={timeout_count} this run --\n")

    total_done = len(completed_ids) + len(remaining)
    print()
    print("=" * 60)
    print(f"Collection complete: {total_done}/{len(questions)} questions")
    print(f"  ok={ok_count}  timeout={timeout_count} (this run)")
    print(f"  Output: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
