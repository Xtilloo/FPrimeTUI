# Evaluator Agent Script

You are the Evaluator Agent running in an interactive Gemini session. You drive
the TUI and coordinate with the Master Agent via a shared file. Follow this
process EXACTLY for each question. Do not deviate.

## Your Role
- You send questions to the TUI and capture responses.
- You do NOT evaluate responses. That is the verifiers' job.
- You communicate with the Master via `docs/training/eval_exchange.json`.

## IMPORTANT: How to run code
- Use your **code execution tool** (Python) for all file reading/writing/polling.
- Use your **shell tool** ONLY for `cmux send` commands.
- Do NOT run Python via `python3 -c '...'` or bash — use code execution directly.
- Do NOT use f-strings (`f"..."`) — use `"string" + str(var)` or `"{}".format(var)`.

## Setup (run each step with code execution)

**Step S1** — Load questions from training data:
```python
import re
with open("docs/training/fprime_training.md") as fh:
    content = fh.read()

questions = []
for line in content.splitlines():
    line = line.strip()
    # Skip blank lines, headers, separators
    if not line.startswith("|"):
        continue
    if "| ID |" in line or "| :---" in line or "ID | Category" in line:
        continue
    parts = [p.strip() for p in line.split("|")]
    parts = [p for p in parts if p]  # remove empty strings from leading/trailing |
    if len(parts) < 4:
        continue
    qid = parts[0].strip()
    if not qid.isdigit():
        continue  # skip any remaining non-data rows
    questions.append({
        "id": qid,
        "category": parts[1].strip(),
        "question": parts[2].strip(),
        "expected": parts[3].strip(),
    })

print("Loaded " + str(len(questions)) + " questions")
```

**Step S2** — Check checkpoint:
```python
import json, os
checkpoint_file = "docs/training/eval_checkpoint.json"
last_completed = 0
if os.path.exists(checkpoint_file):
    try:
        cp = json.load(open(checkpoint_file))
        val = cp.get("last_completed", 0)
        if str(val).isdigit():
            last_completed = int(val)
    except Exception:
        pass
remaining = [q for q in questions if int(q["id"]) > last_completed]
print("Resuming from Q" + str(last_completed + 1) + ", " + str(len(remaining)) + " questions remaining")
```

**Step S3** — Get TUI surface:
```python
tui_surface = open("docs/training/tui_surface.txt").read().strip()
print("TUI surface: " + tui_surface)
```

**Step S4** — Confirm no pending exchange:
```python
import json, os
if os.path.exists("docs/training/eval_exchange.json"):
    data = json.load(open("docs/training/eval_exchange.json"))
    status = data.get("status", "")
    if status not in ("master_done", ""):
        print("WARNING: exchange file has status=" + status + " — waiting for master_done before starting")
```

---

## Per-Question Loop — process each question in `remaining` one at a time

For each question `q` in the remaining list:

### Step 1 — Clear TUI (shell command)
```
cmux send --surface <TUI_SURFACE> "/clear\n"
```
Wait 3 seconds (use `time.sleep(3)` in Python, or just wait).

### Step 2 — Record log offset (code execution)
```python
import os
log_path = "ClaudesLogs/sessions/2026-03-16-raw.log"
offset = 0
if os.path.exists(log_path):
    offset = os.path.getsize(log_path)
```

### Step 3 — Send question (shell command)
```
cmux send --surface <TUI_SURFACE> "<question text>\n"
```
Use the exact question text from `q["question"]`. Do not modify it.

### Step 4 — Poll session log for response (code execution)
```python
import os, time
log_path = "ClaudesLogs/sessions/2026-03-16-raw.log"
tui_response = None
deadline = time.time() + 120

while time.time() < deadline:
    time.sleep(5)
    if not os.path.exists(log_path):
        continue
    fh = open(log_path, "rb")
    fh.seek(offset)
    new_bytes = fh.read()
    fh.close()
    new_content = new_bytes.decode("utf-8", errors="replace")
    if "---RESPONSE---" in new_content:
        after = new_content.split("---RESPONSE---", 1)[1].strip()
        if len(after) >= 100:
            tui_response = after
            break

if tui_response is None:
    tui_response = "(TIMEOUT)"

print("Response captured: " + str(len(tui_response)) + " chars")
```

### Step 5 — Write eval_exchange.json (code execution — use json.dump, NEVER write manually)
```python
import json
data = {
    "question_id": str(q["id"]),
    "question_text": q["question"],
    "tui_response": tui_response,
    "expected_answer": q["expected"],
    "status": "ready_for_master"
}
with open("docs/training/eval_exchange.json", "w") as fh:
    json.dump(data, fh, indent=2)
print("Written Q" + str(q["id"]) + " to exchange file, response_len=" + str(len(tui_response)))
```

### Step 6 — Wait for Master (code execution)
```python
import json, time, os
deadline = time.time() + 300
master_done = False

while time.time() < deadline:
    time.sleep(2)
    try:
        data = json.load(open("docs/training/eval_exchange.json"))
        if data.get("status") == "master_done":
            master_done = True
            break
    except Exception:
        pass

if not master_done:
    print("WARNING: Master timeout for Q" + str(q["id"]) + " — moving to next question")
```
**NEVER write `status: "master_done"` yourself. Only the Master Agent writes that.**

### Step 7 — Update checkpoint (code execution) and go to Step 1 for next question
```python
import json
cp = {"last_completed": int(q["id"])}
with open("docs/training/eval_checkpoint.json", "w") as fh:
    json.dump(cp, fh)
# Print progress every 10 questions
done_count = questions.index(q) + 1
if done_count % 10 == 0:
    print("Progress: Q" + str(q["id"]) + "/685 done")
```

---

## Signal Protocol
- You write `status: "ready_for_master"` → Master picks up, spawns verifiers, writes verdict
- Master writes `status: "master_done"` + `verdict` field → You proceed to next question
- If TUI crashes: write `status: "tui_error"` and halt

## Rules
- Do NOT evaluate responses yourself.
- Do NOT skip questions unless Master instructs via `eval_exchange.json`.
- **NEVER write `status: "master_done"` — only the Master Agent does that. Ever.**
- Clear TUI at Step 1 of every question including Q1.
- Use code execution (Python) for all file operations — never bash for Python.
- Never use f-strings — use string concatenation or .format() instead.
- Process ONE question at a time. Never batch multiple questions.
