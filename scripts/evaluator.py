#!/usr/bin/env python3
"""
Evaluator Agent — pure Python, no LLM required.
Sends F' training questions to the TUI via CMUX, captures responses from
the session log, and signals the Master Orchestrator via eval_exchange.json.

Usage: python3 scripts/evaluator.py
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT = Path("/Users/xtilloo/Projects/FPrimeTUI")
TRAINING_FILE = PROJECT / "docs/training/fprime_training.md"
CHECKPOINT_FILE = PROJECT / "docs/training/eval_checkpoint.json"
EXCHANGE_FILE = PROJECT / "docs/training/eval_exchange.json"
TUI_SURFACE_FILE = PROJECT / "docs/training/tui_surface.txt"
SESSION_LOG = PROJECT / "ClaudesLogs/sessions/2026-03-16-raw.log"

RESPONSE_TIMEOUT = 120   # seconds to wait for TUI response
MASTER_TIMEOUT = 300     # seconds to wait for master_done
POLL_INTERVAL = 3        # seconds between polls
MIN_RESPONSE_LEN = 100   # minimum chars to consider a real response


def load_questions():
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


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            cp = json.loads(CHECKPOINT_FILE.read_text())
            val = cp.get("last_completed", 0)
            return int(val) if str(val).isdigit() else 0
        except Exception:
            pass
    return 0


def save_checkpoint(qid: str):
    CHECKPOINT_FILE.write_text(json.dumps({"last_completed": int(qid)}))


def get_tui_surface():
    if TUI_SURFACE_FILE.exists():
        return TUI_SURFACE_FILE.read_text().strip()
    print("[ERROR] tui_surface.txt not found", file=sys.stderr)
    sys.exit(1)


def cmux_send(surface: str, text: str):
    subprocess.run(["cmux", "send", "--surface", surface, text], check=True)


def get_log_offset():
    if SESSION_LOG.exists():
        return SESSION_LOG.stat().st_size
    return 0


def wait_for_response(offset: int) -> str:
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
                return after
    return "(TIMEOUT)"


def write_exchange(q: dict, tui_response: str):
    data = {
        "question_id": q["id"],
        "question_text": q["question"],
        "tui_response": tui_response,
        "expected_answer": q["expected"],
        "status": "ready_for_master",
    }
    EXCHANGE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def wait_for_master(qid: str) -> bool:
    deadline = time.time() + MASTER_TIMEOUT
    while time.time() < deadline:
        time.sleep(2)
        try:
            data = json.loads(EXCHANGE_FILE.read_text())
            if data.get("status") == "master_done":
                return True
        except Exception:
            pass
    print(f"[WARN] Master timeout on Q{qid}")
    return False


def main():
    print("=" * 60)
    print("F PRIME TUI — EVALUATOR AGENT (Python)")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    questions = load_questions()
    print(f"Loaded {len(questions)} questions")

    last_completed = load_checkpoint()
    remaining = [q for q in questions if int(q["id"]) > last_completed]
    print(f"Resuming from Q{last_completed + 1}, {len(remaining)} remaining")

    tui_surface = get_tui_surface()
    print(f"TUI surface: {tui_surface}")
    print()

    for i, q in enumerate(remaining):
        qid = q["id"]
        print(f"[Q{qid}] {q['question'][:70]}...")

        # Step 1 — Clear TUI
        cmux_send(tui_surface, "/clear\n")
        time.sleep(3)

        # Step 2 — Record log offset
        offset = get_log_offset()

        # Step 3 — Send question
        cmux_send(tui_surface, q["question"] + "\n")

        # Step 4 — Wait for TUI response
        tui_response = wait_for_response(offset)
        print(f"  Response: {len(tui_response)} chars")

        # Step 5 — Write exchange
        write_exchange(q, tui_response)

        # Step 6 — Wait for master
        wait_for_master(qid)

        # Step 7 — Checkpoint
        save_checkpoint(qid)

        done = i + 1
        if done % 10 == 0:
            print(f"\nProgress: Q{qid}/685 done ({done} this run)")

    print("\nAll questions processed.")


if __name__ == "__main__":
    main()
