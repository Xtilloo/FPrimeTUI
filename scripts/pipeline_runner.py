#!/usr/bin/env python3
"""
F Prime TUI Training Pipeline — Master/Orchestrator

Responsibilities (THIS script only):
  - Poll docs/training/eval_exchange.json for new "ready_for_master" entries
  - Spawn Gemini verifiers (V1, V2, optionally V3)
  - Apply consensus matrix
  - Write to curated_qa.md / fine_tuning.jsonl / review_queue.md / diagnosis_log.md
  - Write verdict back to eval_exchange.json (status: "master_done")
  - Checkpoint every N questions

What this script does NOT do:
  - Send questions to the TUI  ← that is the Evaluator's job (surface:10)
  - Read TUI screens           ← Evaluator handles that
  - Manage the training question list ← Evaluator handles that

Usage:
    ./venv/bin/python scripts/pipeline_runner.py
    ./venv/bin/python scripts/pipeline_runner.py --reset-checkpoint
"""

import argparse
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
PROJECT = Path("/Users/xtilloo/Projects/FPrimeTUI")
EVAL_EXCHANGE = PROJECT / "docs/training/eval_exchange.json"
CHECKPOINT = PROJECT / "docs/training/eval_checkpoint.json"
CURATED_QA = PROJECT / "TUI/rag/curated_qa.md"
FINE_TUNING = PROJECT / "docs/training/fine_tuning.jsonl"
REVIEW_QUEUE = PROJECT / "docs/training/review_queue.md"
DIAGNOSIS_LOG = PROJECT / "docs/training/diagnosis_log.md"
VERIFY_INPUT = PROJECT / "docs/training/verify_input.json"
VERIFY_V1 = PROJECT / "docs/training/verify_output_v1.json"
VERIFY_V2 = PROJECT / "docs/training/verify_output_v2.json"
VERIFY_V3 = PROJECT / "docs/training/verify_output_v3.json"
VERIFY_SKILL = Path("~/.claude/skills/fprime-tui-verify/skill.md").expanduser()
VERIFIER_LOG_DIR = PROJECT / "docs/training/verifier_logs"
RUN_LOG = PROJECT / f"docs/training/pipeline_run_{datetime.now().strftime('%Y-%m-%d')}.md"

# ─── Config ──────────────────────────────────────────────────────────────────
EXCHANGE_POLL_INTERVAL = 2    # seconds between eval_exchange.json polls
VERIFIER_TIMEOUT = 150        # seconds to wait for each verifier output
CHECKPOINT_INTERVAL = 10      # checkpoint every N questions
RATE_LIMIT_BACKOFF_BASE = 60
RATE_LIMIT_MAX = 600
INTER_VERIFIER_GAP = 3        # seconds between V1 and V2 spawn
VERIFIER_V3_COOLDOWN = 5      # seconds before V3 if disputed


# ─── Checkpoint ──────────────────────────────────────────────────────────────
def load_checkpoint() -> dict:
    defaults = {"last_completed": None, "pass": 0, "fail": 0, "partial": 0, "total": 0}
    if CHECKPOINT.exists():
        try:
            with open(CHECKPOINT) as f:
                data = json.load(f)
            # Merge with defaults to handle stale/mismatched checkpoint formats
            return {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


def save_checkpoint(cp: dict) -> None:
    cp["timestamp"] = datetime.now().isoformat()
    with open(CHECKPOINT, "w") as f:
        json.dump(cp, f, indent=2)
    print(f"  [CHECKPOINT] {cp['last_completed']} | PASS={cp['pass']} FAIL={cp['fail']} PARTIAL={cp['partial']}")


# ─── eval_exchange.json protocol ─────────────────────────────────────────────
def _sanitize_json(content: str) -> str:
    """Escape unescaped control characters inside JSON string values.
    Gemini sometimes writes literal newlines into JSON strings instead of \\n."""
    result = []
    in_string = False
    i = 0
    while i < len(content):
        c = content[i]
        if c == '"':
            backslashes = 0
            j = i - 1
            while j >= 0 and content[j] == '\\':
                backslashes += 1
                j -= 1
            if backslashes % 2 == 0:
                in_string = not in_string
            result.append(c)
        elif in_string and c == '\n':
            result.append('\\n')
        elif in_string and c == '\r':
            result.append('\\r')
        elif in_string and c == '\t':
            result.append('\\t')
        elif in_string and ord(c) < 0x20:
            result.append(f'\\u{ord(c):04x}')
        else:
            result.append(c)
        i += 1
    return ''.join(result)


def read_exchange() -> dict | None:
    """Read eval_exchange.json. Returns None if file missing or not ready."""
    if not EVAL_EXCHANGE.exists():
        return None
    try:
        content = EVAL_EXCHANGE.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = json.loads(_sanitize_json(content))
        if data.get("status") == "ready_for_master":
            # Atomically mark as processing to prevent double-processing
            data["status"] = "processing"
            EVAL_EXCHANGE.write_text(json.dumps(data, indent=2))
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def write_exchange_verdict(question_id: str, verdict: str) -> None:
    """Write master_done status back so Evaluator can proceed."""
    try:
        with open(EVAL_EXCHANGE) as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["status"] = "master_done"
    data["verdict"] = verdict
    data["master_timestamp"] = datetime.now().isoformat()
    with open(EVAL_EXCHANGE, "w") as f:
        json.dump(data, f, indent=2)


# ─── Verifier ────────────────────────────────────────────────────────────────
def spawn_verifier(output_filename: str, verifier_label: str = "v?") -> subprocess.Popen:
    """
    Spawn a headless Gemini verifier.
    Skill + input data passed via stdin; -p carries only the short output instruction.
    Stderr logged to verifier_logs/ for diagnostics.
    """
    VERIFIER_LOG_DIR.mkdir(parents=True, exist_ok=True)

    skill_content = VERIFY_SKILL.read_text()
    input_data = VERIFY_INPUT.read_text() if VERIFY_INPUT.exists() else "{}"
    abs_output = str(PROJECT / output_filename)

    # Put input data FIRST so Gemini sees it before skill instructions.
    # Explicit override: use inline data, do not try to read any files for input.
    stdin_content = (
        f"## VERIFICATION INPUT (use this data — do not read any files for input)\n\n"
        f"```json\n{input_data}\n```\n\n"
        f"---\n\n"
        f"{skill_content}\n\n"
        f"---\n\n"
        f"The input data is at the top of this message. "
        f"Do NOT try to read docs/training/verify_input.json or any other file for input — it is already above.\n"
        f"Write your verdict JSON to `{abs_output}`."
    ).encode()

    log_name = f"{verifier_label}_{datetime.now().strftime('%H%M%S')}.log"
    stderr_log = open(VERIFIER_LOG_DIR / log_name, "w")

    proc = subprocess.Popen(
        ["gemini", "--yolo", "-m", "gemini-2.5-flash-lite", "-p",
         f"The verification input is in stdin. Write verdict JSON to {abs_output}. Start immediately."],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=stderr_log,
        cwd=str(PROJECT),
    )
    proc.stdin.write(stdin_content)
    proc.stdin.close()
    return proc


def poll_file(path: Path, timeout: int = 150) -> bool:
    for _ in range(timeout):
        if path.exists() and path.stat().st_size > 10:
            return True
        time.sleep(1)
    return False


def read_verdict(path: Path) -> dict | None:
    try:
        content = path.read_text().strip()
        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(content)
    except Exception as e:
        print(f"    [WARN] Failed to parse {path.name}: {e}")
        return None


# ─── Consensus ───────────────────────────────────────────────────────────────
def apply_consensus(v1: str, v2: str, v3: str | None = None) -> tuple[str, str]:
    if v1 == "CORRECT" and v2 == "CORRECT":
        return "PASS", "curated"
    if (v1 == "CORRECT" and v2 == "PARTIAL") or (v1 == "PARTIAL" and v2 == "CORRECT"):
        return "SOFT_PASS", "curated_soft"
    if v1 == "PARTIAL" and v2 == "PARTIAL":
        return "PARTIAL", "review"
    if (v1 == "CORRECT" and v2 == "INCORRECT") or (v1 == "INCORRECT" and v2 == "CORRECT"):
        if v3 is None:
            return "DISPUTED", "need_v3"
        votes = [v1, v2, v3]
        if votes.count("CORRECT") > votes.count("INCORRECT"):
            return "PASS", "curated"
        if votes.count("INCORRECT") > votes.count("CORRECT"):
            return "FAIL", "diagnosis"
        return "PARTIAL", "review"
    if v1 == "INCORRECT" and v2 == "INCORRECT":
        return "FAIL", "diagnosis"
    return "PARTIAL", "review"


# ─── Output writers ──────────────────────────────────────────────────────────
def write_curated_qa(qid: str, question: str, response: str, verdict_type: str, v1_data: dict) -> None:
    tag = "[A]" if verdict_type == "PASS" else "[A][soft]"
    entry = (
        f"\n## {qid} {tag}\n\n"
        f"**Q:** {question}\n\n"
        f"**A:** {response}\n\n"
        f"**Citation:** {v1_data.get('citation', 'N/A')}\n\n"
        f"---\n"
    )
    with open(CURATED_QA, "a") as f:
        f.write(entry)


def write_fine_tuning(qid: str, question: str, response: str, category: str) -> None:
    entry = {
        "question_id": qid,
        "category": category,
        "prompt": question,
        "response": response,
        "verified_at": datetime.now().isoformat(),
        "verdict": "PASS",
    }
    with open(FINE_TUNING, "a") as f:
        f.write(json.dumps(entry) + "\n")


def write_review_queue(qid: str, question: str, response: str, v1_data: dict, v2_data: dict) -> None:
    def fmt(d: dict) -> str:
        disc = ", ".join(d.get("discrepancies", []))
        return f"{d.get('verdict','?')} — {d.get('citation','N/A')}" + (f"\n  Discrepancies: {disc}" if disc else "")

    entry = (
        f"\n## {qid} [PARTIAL]\n\n"
        f"**Q:** {question}\n\n"
        f"**TUI Response:** {response[:600]}{'...' if len(response) > 600 else ''}\n\n"
        f"**V1:** {fmt(v1_data)}\n\n"
        f"**V2:** {fmt(v2_data)}\n\n"
        f"---\n"
    )
    with open(REVIEW_QUEUE, "a") as f:
        f.write(entry)


def write_diagnosis(qid: str, question: str, response: str, v1_data: dict, v2_data: dict) -> None:
    def fmt(d: dict) -> str:
        disc = ", ".join(d.get("discrepancies", []))
        return f"{d.get('verdict','?')} — {d.get('citation','N/A')}" + (f"\n  Discrepancies: {disc}" if disc else "")

    entry = (
        f"\n## {qid} [FAIL]\n\n"
        f"**Q:** {question}\n\n"
        f"**TUI Response:** {response[:600]}{'...' if len(response) > 600 else ''}\n\n"
        f"**V1:** {fmt(v1_data)}\n\n"
        f"**V2:** {fmt(v2_data)}\n\n"
        f"---\n"
    )
    with open(DIAGNOSIS_LOG, "a") as f:
        f.write(entry)


# ─── Run log ─────────────────────────────────────────────────────────────────
def log_run_result(qid: str, category: str, response_len: int,
                   v1: str, v2: str, v3: str | None, outcome: str, notes: str = "") -> None:
    row = f"| {qid} | {category} | {response_len} | {v1} | {v2} | {v3 or '—'} | {outcome} | {notes} |\n"
    with open(RUN_LOG, "a") as f:
        f.write(row)


# ─── Process one exchange ─────────────────────────────────────────────────────
def process_exchange(exchange: dict, cp: dict) -> dict:
    qid = exchange["question_id"]
    question = exchange["question_text"]
    response = exchange["tui_response"]
    expected = exchange.get("expected_answer", "")
    category = exchange.get("category", "Unknown")

    print(f"\n{'=' * 65}")
    print(f"[{qid}] [{category}] {question[:75]}...")
    print(f"  Response: {len(response)} chars")

    cp["total"] = cp.get("total", 0) + 1

    # Handle timeout/missing response from Evaluator
    if not response or len(response) < 40 or response == "(TIMEOUT)":
        print("  [FAIL] No usable TUI response")
        cp["fail"] += 1
        write_diagnosis(
            qid, question, response or "(NONE)",
            {"verdict": "INCORRECT", "citation": "NO_RESPONSE", "discrepancies": ["Evaluator reported no TUI response"]},
            {"verdict": "INCORRECT", "citation": "NO_RESPONSE", "discrepancies": []},
        )
        log_run_result(qid, category, len(response or ""), "—", "—", None, "FAIL", "no TUI response from Evaluator")
        cp["last_completed"] = qid
        return cp

    # Write verify_input.json for verifiers
    verify_data = {
        "question_id": qid,
        "question_text": question,
        "tui_response": response,
        "expected_answer": expected,
    }
    VERIFY_INPUT.write_text(json.dumps(verify_data, indent=2))

    # Clean up previous verifier outputs
    for vf in (VERIFY_V1, VERIFY_V2, VERIFY_V3):
        if vf.exists():
            vf.unlink()

    # Spawn V1
    print("  Spawning V1...")
    spawn_verifier("docs/training/verify_output_v1.json", verifier_label="v1")
    time.sleep(INTER_VERIFIER_GAP)

    # Spawn V2
    print("  Spawning V2...")
    spawn_verifier("docs/training/verify_output_v2.json", verifier_label="v2")

    # Poll
    print(f"  Polling verifiers (timeout={VERIFIER_TIMEOUT}s)...")
    v1_ready = poll_file(VERIFY_V1, VERIFIER_TIMEOUT)
    v2_ready = poll_file(VERIFY_V2, VERIFIER_TIMEOUT)

    if not v1_ready or not v2_ready:
        print("  [WARN] Verifier timeout — marking PARTIAL")
        cp["partial"] += 1
        write_review_queue(
            qid, question, response,
            {"verdict": "TIMEOUT", "citation": "VERIFIER_TIMEOUT", "discrepancies": []},
            {"verdict": "TIMEOUT", "citation": "VERIFIER_TIMEOUT", "discrepancies": []},
        )
        log_run_result(qid, category, len(response), "TIMEOUT", "TIMEOUT", None, "PARTIAL", "verifier timeout")
        cp["last_completed"] = qid
        return cp

    v1_data = read_verdict(VERIFY_V1) or {"verdict": "PARTIAL", "citation": "PARSE_ERROR", "discrepancies": ["JSON parse error"]}
    v2_data = read_verdict(VERIFY_V2) or {"verdict": "PARTIAL", "citation": "PARSE_ERROR", "discrepancies": ["JSON parse error"]}

    v1v = v1_data.get("verdict", "PARTIAL")
    v2v = v2_data.get("verdict", "PARTIAL")
    print(f"  V1={v1v}  V2={v2v}")

    outcome, destination = apply_consensus(v1v, v2v)
    v3v = None

    if destination == "need_v3":
        print("  DISPUTED → spawning V3 (5s cooldown)...")
        time.sleep(VERIFIER_V3_COOLDOWN)
        spawn_verifier("docs/training/verify_output_v3.json", verifier_label="v3")
        v3_ready = poll_file(VERIFY_V3, VERIFIER_TIMEOUT)
        if v3_ready:
            v3_data = read_verdict(VERIFY_V3) or {}
            v3v = v3_data.get("verdict", "PARTIAL")
            print(f"  V3={v3v}")
            outcome, destination = apply_consensus(v1v, v2v, v3v)
        else:
            print("  [WARN] V3 timeout → PARTIAL")
            outcome, destination = "PARTIAL", "review"
            v3v = "TIMEOUT"

    print(f"  Outcome: {outcome} → {destination}")

    if destination == "curated":
        write_curated_qa(qid, question, response, "PASS", v1_data)
        write_fine_tuning(qid, question, response, category)
        cp["pass"] += 1
    elif destination == "curated_soft":
        write_curated_qa(qid, question, response, "SOFT_PASS", v1_data)
        cp["pass"] += 1
    elif destination == "review":
        write_review_queue(qid, question, response, v1_data, v2_data)
        cp["partial"] += 1
    elif destination == "diagnosis":
        write_diagnosis(qid, question, response, v1_data, v2_data)
        cp["fail"] += 1

    log_run_result(qid, category, len(response), v1v, v2v, v3v, outcome)
    cp["last_completed"] = qid
    return cp


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="F Prime TUI Training Pipeline — Master/Orchestrator")
    parser.add_argument("--reset-checkpoint", action="store_true", help="Delete checkpoint and start fresh")
    args = parser.parse_args()

    if args.reset_checkpoint and CHECKPOINT.exists():
        CHECKPOINT.unlink()
        print("[RESET] Checkpoint deleted")

    print("=" * 65)
    print("F PRIME TUI TRAINING PIPELINE — MASTER ORCHESTRATOR")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 65)
    print("Waiting for Evaluator Agent to write eval_exchange.json...")
    print("(Launch: bash docs/training/start_evaluator.sh)")
    print()

    cp = load_checkpoint()
    print(f"[CHECKPOINT] PASS={cp['pass']} FAIL={cp['fail']} PARTIAL={cp['partial']}")

    processed = 0
    backoff = RATE_LIMIT_BACKOFF_BASE

    try:
        while True:
            exchange = read_exchange()

            if exchange is None:
                # Nothing ready — poll
                time.sleep(EXCHANGE_POLL_INTERVAL)
                continue

            qid = exchange.get("question_id", "?")
            print(f"\n[MASTER] Received {qid} from Evaluator")

            try:
                cp = process_exchange(exchange, cp)
                backoff = RATE_LIMIT_BACKOFF_BASE
                processed += 1

                # Signal Evaluator: done with this question
                write_exchange_verdict(qid, cp.get("last_completed", qid))
                print("  → Signalled Evaluator: master_done")

                # Checkpoint every N
                if processed % CHECKPOINT_INTERVAL == 0:
                    save_checkpoint(cp)

            except Exception as e:
                err = str(e)
                if "429" in err:
                    backoff = min(backoff * 2, RATE_LIMIT_MAX)
                    print(f"  [RATE_LIMIT] 429 error, backing off {backoff}s...")
                    time.sleep(backoff)
                    # Don't signal Evaluator yet — they'll wait (300s timeout)
                else:
                    print(f"  [ERROR] {e}")
                    write_exchange_verdict(qid, "ERROR")

    except KeyboardInterrupt:
        save_checkpoint(cp)
        total = cp["pass"] + cp["fail"] + cp["partial"]
        print(f"\n\n[INTERRUPTED] Saved checkpoint after {processed} questions")
        print(f"  PASS={cp['pass']} FAIL={cp['fail']} PARTIAL={cp['partial']} / {total} total")
        print(f"  Last completed: {cp.get('last_completed')}")


if __name__ == "__main__":
    main()
