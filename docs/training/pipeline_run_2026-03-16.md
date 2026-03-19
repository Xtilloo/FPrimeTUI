# Pipeline Run Log — 2026-03-16

**Purpose:** First test run of the automated training pipeline against 685 Q&A questions.
Objectives: validate TUI response capture, verifier spawning, consensus logic, and output file writing.

## Run Configuration
- Questions: 685 (Q1–Q685) from `docs/training/fprime_training.md`
- TUI: surface:9, MISSION_CONTROL mode
- Verifier: Gemini CLI (`gemini -p ... --yolo`), headless per-question
- Branch: `rag_implementation`

---

## Issues Found & Fixed

### ISSUE-01: Screen scraping unusable for TUI response capture
**Observed:** `cmux read-screen` returns a single-line blob (Textual renders with cursor-position ANSI codes, not newlines). Long responses are clipped by the terminal viewport height — the response cut off at section 2 of a 3-section answer.
**Fix:** Switched to reading `ClaudesLogs/sessions/YYYY-MM-DD-raw.log` instead. The TUI logs every exchange in `---USER---` / `---RESPONSE---` format with the full untruncated text. We record the file byte offset before sending each question, then poll for a new `---RESPONSE---` marker after that offset.
**Verification:** Tested on Q2 — captured 1,941-char response correctly.
**Updated:** `scripts/pipeline_runner.py` — replaced `extract_tui_response()` with `wait_for_tui_response(start_offset)` using log polling.

### ISSUE-02: Verifier spawn — gemini subprocess exits silently
**Observed:** `spawn_verifier()` called `Popen(['gemini', '-p', full_skill_content, '--yolo'])` with `stdout/stderr=DEVNULL`. `pgrep -f gemini` showed no running process immediately after spawn. Root cause unknown (possibly: argument too large, gemini startup failure, or immediate exit without workspace context).
**Fix:** Changed spawn to use **stdin** to pass skill + input data. The `-p` flag only carries a short instruction (`"Write verdict to <file>"`). stderr now redirected to a per-verifier log file in `docs/training/verifier_logs/` for visibility during the test run.
**Reference:** `gemini --help` confirms: `-p` prompt is *appended* to stdin, so stdin content is read first.
**Updated:** `scripts/pipeline_runner.py` → `spawn_verifier()` function.

### ISSUE-03: Orchestrator was doing the Evaluator's job (architecture violation)
**Observed:** `pipeline_runner.py` was sending questions to TUI via CMUX and polling session log itself. Q1 worked (clean state). Q2–Q5 failed with 0 chars — TUI didn't respond after Q1, likely due to state/timing issues when the script immediately re-drove the TUI after verifier processing.
**Root Cause:** Wrong architecture. `pipeline_runner.py` conflated Evaluator role (TUI interaction) with Master/Orchestrator role (verifier spawning + consensus). Only Q1 worked because the TUI had no prior state.
**Fix:** Restructured cleanly:
- `pipeline_runner.py` → pure Master/Orchestrator: polls `eval_exchange.json`, spawns verifiers, writes results, writes `status: "master_done"` back
- `docs/training/scripts/evaluator_agent.md` → updated Evaluator script for Gemini (surface:10): reads training data, drives TUI via CMUX, reads session log, writes `eval_exchange.json`
- Training file path updated: `FPrimeSampleProject/docs/fprime_training.md` → `docs/training/fprime_training.md`
**Architecture:** surface:9=TUI | surface:10=Gemini Evaluator (interactive) | surface:1=Claude Orchestrator

### ISSUE-04: `cmux new-split` creates unusable "not a terminal" surfaces
**Observed:** `cmux new-split right --workspace workspace:1 --surface surface:9` created surface:10 but subsequent `cmux send --surface surface:10` failed with `Error: invalid_params: Surface is not a terminal`.
**Root Cause:** Unknown — possibly `new-split` from a surface running a TUI application creates a surface in a bad state. The split creation succeeds (appears in `cmux list-panels`) but the surface refuses sends.
**Fix:** Use `cmux new-pane --type terminal --direction right --workspace workspace:1` instead of `new-split`. This reliably creates a proper terminal pane.
**Verification:** surface:11 (TUI) and surface:12 (Evaluator) created with `new-pane --type terminal`, both accepted CMUX sends immediately.
**Updated:** `docs/training/start_evaluator.sh` — uses `$CMUX_SURFACE_ID` (auto-set by cmux) to self-identify and exclude from TUI surface detection.

### ISSUE-05: Evaluator script hardcodes surface:9; surface IDs change each session
**Observed:** `evaluator_agent.md` referenced `surface:9` throughout, but surface IDs are assigned dynamically per session (this session: surface:11=TUI, surface:12=Evaluator).
**Fix:** Updated `evaluator_agent.md` to discover TUI surface via `cmux list-panels` at startup instead of assuming surface:9. Updated `start_evaluator.sh` to detect TUI surface and inject it as a runtime hint into Gemini's initial prompt.
**Approach:** `$CMUX_SURFACE_ID` env var (auto-set by cmux in terminal panes) identifies the Evaluator's own surface; TUI surface is the remaining terminal pane after excluding Claude Code and self.

---

## Per-Question Results — Run 1 (Aborted — Bad Architecture)

| Q# | Category | TUI Response (chars) | V1 | V2 | V3 | Outcome | Notes |
|----|----------|---------------------|----|----|----|---------|----|
| Q1 | Architecture | 3471 | PARTIAL | INCORRECT | — | PARTIAL |  |
| Q2 | Modeling | 0 | — | — | — | FAIL | no TUI response |
| Q3 | Framework Services | 0 | — | — | — | FAIL | no TUI response |
| Q4 | Testing | 0 | — | — | — | FAIL | no TUI response |
| Q5 | Implementation | 0 | — | — | — | FAIL | no TUI response |

---

## Run 2 — Full Pipeline (Correct Architecture)

**Started:** 2026-03-16 (second session)
**Configuration:**
- surface:11 = TUI (F Prime TUI, MISSION_CONTROL mode)
- surface:12 = Gemini Evaluator (interactive, `--yolo`)
- surface:1  = Claude Orchestrator (this Claude Code session)
- Orchestrator: `scripts/pipeline_runner.py` (background)
- Q start: Q1 (no checkpoint from Run 1 — it processed Q1 as orchestrator directly, architecture was wrong)

### Key fixes applied before this run:
- ISSUE-04: use `new-pane --type terminal` (not `new-split`) for reliable CMUX sends
- ISSUE-05: evaluator_agent.md now discovers TUI surface via `cmux list-panels` at startup

| Q# | Category | TUI Response (chars) | V1 | V2 | V3 | Outcome | Notes |
|----|----------|---------------------|----|----|----|---------|----|
| 1 | Unknown | 2619 | INCORRECT | INCORRECT | — | FAIL |  |
| 2 | Unknown | 2598 | PARTIAL | INCORRECT | — | PARTIAL |  |

### ISSUE-06: start_evaluator.sh awk extracts "terminal" instead of surface ID
**Observed:** `cmux list-panels` output format is `  surface:N  terminal  "Title"`. `awk '{print $2}'` extracted the second field ("terminal") instead of the first ("surface:N"). Also, `$CMUX_SURFACE_ID` is set to a UUID format but list-panels shows short refs — grep exclusion was unreliable.
**Fix:** Changed `awk '{print $2}'` to `awk '{print $1}'`. Added `cmux identify --no-caller` to get the short ref for self-exclusion. Fallback to UUID for grep -v if identify fails.
**Note:** Gemini self-corrected at runtime by running `cmux list-panels` as instructed in evaluator_agent.md (Setup step 3) and discovered surface:11 correctly despite the wrong hint.

### ISSUE-09: Evaluator parsed markdown table header as Q1
**Observed:** `evaluator_agent.md` said "685 Q&A pairs in a markdown table" but did not say to skip the header row. Gemini treated `| ID | Category | Question (Prompt) | ... |` as the first question, sending "Question (Prompt)" to the TUI.
**Fix:** Added explicit header-skip logic in the Step S1 Python block: skip any row matching `"| ID |"`, `"| :---"`, or `"ID | Category"`, and skip rows where the ID column is not numeric.
**Updated:** `docs/training/scripts/evaluator_agent.md`

### ISSUE-10: Double-processing race condition in read_exchange()
**Observed:** `pipeline_runner.py` called `read_exchange()` every 2 seconds. While `process_exchange()` was running (spawning verifiers, ~60s), the same question was read again from the exchange file and spawned 2x verifiers per question.
**Fix:** `read_exchange()` now atomically writes `status: "processing"` immediately when it reads a `ready_for_master` entry. Subsequent polls see non-`ready_for_master` status and return None.
**Updated:** `scripts/pipeline_runner.py` → `read_exchange()`

### ISSUE-11: Verifier `read_file` tool uses HOME-relative paths
**Observed:** Gemini's `read_file` tool resolves relative paths from HOME (`/Users/xtilloo`), not from the process `cwd`. Verifiers tried to open `docs/training/verify_input.json` (relative) which resolved to `/Users/xtilloo/docs/training/verify_input.json` — not found.
**Fix (partial):** Updated `-p` flag and stdin hint to use absolute paths via `str(PROJECT / output_filename)` and `str(VERIFY_INPUT)`. Still failed because skill content also had relative path instructions.
**Updated:** `scripts/pipeline_runner.py` → `spawn_verifier()`

### ISSUE-12: Verifier skill instructs file reads that block output writing
**Observed:** Even with absolute path in `-p`, verifier skill content (`~/.claude/skills/fprime-tui-verify/skill.md`) instructed "Read input from `docs/training/verify_input.json`" (relative). Gemini tried the read, got "File not found", and exited without writing output verdict.
**Root cause:** Gemini followed skill instructions that included file reads before it could use the inline data already provided in stdin.
**Fix:** Restructured stdin to put input data FIRST, before skill content. Added explicit override: "Do NOT try to read docs/training/verify_input.json or any other file for input — it is already above." This ensures Gemini uses inline data regardless of skill instructions.
**Updated:** `scripts/pipeline_runner.py` → `spawn_verifier()`
**Verification:** Q4 processed end-to-end successfully (V1=PARTIAL, V2=INCORRECT → PARTIAL). First fully successful pipeline run.
| 3 | Unknown | 3090 | INCORRECT | INCORRECT | — | FAIL |  |
| 4 | Unknown | 2441 | INCORRECT | INCORRECT | — | FAIL |  |
| 5 | Unknown | 1783 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |

---

## Run 3 — Session 2 (2026-03-16 resumed)

**Fixes applied before this run:**
- ISSUE-07: evaluator_agent.md rewrote with clean Python blocks (no heredocs), no f-strings
- ISSUE-08: `--surface` prefix fix in start_evaluator.sh hint
- ISSUE-09: evaluator header row parsing (skip `| ID |` row)
- ISSUE-10: `read_exchange()` atomic `processing` state prevents double-processing race
- ISSUE-11: verifier spawn uses absolute paths for both input and output files
- ISSUE-12: verifier stdin restructured — inline data FIRST with explicit override, preventing Gemini from trying to read files that fail

| Q# | Category | TUI Response (chars) | V1 | V2 | V3 | Outcome | Notes |
|----|----------|---------------------|----|----|----|---------|-------|
| ID | Unknown | 358 | INCORRECT | CORRECT | INCORRECT | FAIL | header row bug (fixed by ISSUE-09) |
| 1 | Unknown | 2624 | CORRECT | PARTIAL | — | SOFT_PASS | master timeout (orchestrator killed mid-run) |
| 2 | Unknown | 1619 | — | — | — | SKIP | master killed mid-run |
| 3 | Unknown | 2473 | — | — | — | SKIP | verifiers failed (ISSUE-11,12 not yet applied) |
| 4 | Unknown | 1784 | PARTIAL | INCORRECT | — | PARTIAL | first fully successful end-to-end run |
| 5 | Unknown | 684 | INCORRECT | INCORRECT | — | FAIL | |
| 6 | Unknown | 3457 | CORRECT | CORRECT | — | PASS |  |
| 7 | Unknown | 1552 | INCORRECT | INCORRECT | — | FAIL |  |
| 8 | Unknown | 1498 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 9 | Unknown | 1653 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 10 | Unknown | 2151 | INCORRECT | INCORRECT | — | FAIL |  |
| 11 | Unknown | 1691 | INCORRECT | PARTIAL | — | PARTIAL |  |
| 12 | Unknown | 1142 | CORRECT | CORRECT | — | PASS |  |
| 13 | Unknown | 1385 | CORRECT | CORRECT | — | PASS |  |
| 14 | Unknown | 1480 | INCORRECT | INCORRECT | — | FAIL |  |
| 15 | Unknown | 2606 | CORRECT | CORRECT | — | PASS |  |
| 16 | Unknown | 2008 | CORRECT | PARTIAL | — | SOFT_PASS |  |
| 17 | Unknown | 2631 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 18 | Unknown | 2632 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 19 | Unknown | 1672 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 20 | Unknown | 1755 | INCORRECT | INCORRECT | — | FAIL |  |
| 21 | Unknown | 1992 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 22 | Unknown | 1821 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 23 | Unknown | 1760 | CORRECT | CORRECT | — | PASS |  |
| 24 | Unknown | 2808 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 25 | Unknown | 2697 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 26 | Unknown | 1093 | INCORRECT | PARTIAL | — | PARTIAL |  |
| 27 | Unknown | 2961 | INCORRECT | INCORRECT | — | FAIL |  |
| 28 | Unknown | 2454 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 29 | Unknown | 2817 | CORRECT | CORRECT | — | PASS |  |
| 30 | Unknown | 1929 | CORRECT | PARTIAL | — | SOFT_PASS |  |
| 31 | Unknown | 1003 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 32 | Unknown | 2351 | INCORRECT | PARTIAL | — | PARTIAL |  |
| 33 | Unknown | 1514 | CORRECT | CORRECT | — | PASS |  |
| 34 | Unknown | 1380 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 35 | Unknown | 1379 | INCORRECT | INCORRECT | — | FAIL |  |
| 36 | Unknown | 2142 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 37 | Unknown | 2607 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 38 | Unknown | 1909 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 39 | Unknown | 1680 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 40 | Unknown | 1858 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 41 | Unknown | 2286 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 42 | Unknown | 2241 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 43 | Unknown | 1341 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 44 | Unknown | 2091 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 45 | Unknown | 1840 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 46 | Unknown | 2480 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 47 | Unknown | 2896 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 48 | Unknown | 1088 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 49 | Unknown | 1467 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 50 | Unknown | 1451 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 51 | Unknown | 2034 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 52 | Unknown | 688 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 53 | Unknown | 1006 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 54 | Unknown | 1803 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 55 | Unknown | 1236 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 56 | Unknown | 1188 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 57 | Unknown | 2053 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 58 | Unknown | 2467 | INCORRECT | PARTIAL | — | PARTIAL |  |
| 59 | Unknown | 1419 | INCORRECT | INCORRECT | — | FAIL |  |
| 60 | Unknown | 1135 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 61 | Unknown | 1366 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 62 | Unknown | 3361 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 63 | Unknown | 1000 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 64 | Unknown | 1761 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 65 | Unknown | 1083 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 66 | Unknown | 9 | — | — | — | FAIL | no TUI response from Evaluator |
| 67 | Unknown | 1773 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 68 | Unknown | 1474 | PARTIAL | CORRECT | — | SOFT_PASS |  |
| 69 | Unknown | 1504 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 70 | Unknown | 1673 | CORRECT | PARTIAL | — | SOFT_PASS |  |
| 71 | Unknown | 1196 | INCORRECT | INCORRECT | — | FAIL |  |
| 72 | Unknown | 1965 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 73 | Unknown | 640 | INCORRECT | INCORRECT | — | FAIL |  |
| 74 | Unknown | 1567 | INCORRECT | PARTIAL | — | PARTIAL |  |
| 75 | Unknown | 853 | PARTIAL | CORRECT | — | SOFT_PASS |  |
| 76 | Unknown | 2522 | CORRECT | PARTIAL | — | SOFT_PASS |  |
| 77 | Unknown | 908 | INCORRECT | INCORRECT | — | FAIL |  |
| 78 | Unknown | 1017 | PARTIAL | INCORRECT | — | PARTIAL |  |
| 79 | Unknown | 2034 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 80 | Unknown | 2042 | PARTIAL | CORRECT | — | SOFT_PASS |  |
| 81 | Unknown | 1811 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 82 | Unknown | 2071 | CORRECT | PARTIAL | — | SOFT_PASS |  |
| 83 | Unknown | 670 | INCORRECT | PARTIAL | — | PARTIAL |  |
| 84 | Unknown | 1670 | CORRECT | CORRECT | — | PASS |  |
| 85 | Unknown | 1238 | PARTIAL | CORRECT | — | SOFT_PASS |  |
| 86 | Unknown | 1718 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 87 | Unknown | 1016 | CORRECT | CORRECT | — | PASS |  |
| 88 | Unknown | 2091 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 89 | Unknown | 1519 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 90 | Unknown | 1993 | INCORRECT | INCORRECT | — | FAIL |  |
| 91 | Unknown | 2127 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 92 | Unknown | 1824 | CORRECT | PARTIAL | — | SOFT_PASS |  |
| 93 | Unknown | 1572 | PARTIAL | CORRECT | — | SOFT_PASS |  |
| 94 | Unknown | 1511 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 95 | Unknown | 1649 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 96 | Unknown | 973 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 97 | Unknown | 1469 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 98 | Unknown | 1738 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 99 | Unknown | 426 | CORRECT | CORRECT | — | PASS |  |
| 100 | Unknown | 1690 | PARTIAL | CORRECT | — | SOFT_PASS |  |
| 101 | Unknown | 1086 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 102 | Unknown | 2399 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 103 | Unknown | 1600 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 104 | Unknown | 1798 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 105 | Unknown | 584 | INCORRECT | PARTIAL | — | PARTIAL |  |
| 106 | Unknown | 1567 | INCORRECT | INCORRECT | — | FAIL |  |
| 107 | Unknown | 1758 | CORRECT | PARTIAL | — | SOFT_PASS |  |
| 108 | Unknown | 1484 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 109 | Unknown | 1523 | INCORRECT | INCORRECT | — | FAIL |  |
| 110 | Unknown | 1329 | CORRECT | CORRECT | — | PASS |  |
| 111 | Unknown | 2362 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 112 | Unknown | 1394 | INCORRECT | INCORRECT | — | FAIL |  |
| 113 | Unknown | 1340 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 114 | Unknown | 1338 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 115 | Unknown | 798 | PARTIAL | CORRECT | — | SOFT_PASS |  |
| 116 | Unknown | 3365 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 117 | Unknown | 1003 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
| 121 | Unknown | 9 | — | — | — | FAIL | no TUI response from Evaluator |
| 122 | Unknown | 9 | — | — | — | FAIL | no TUI response from Evaluator |
| 123 | Unknown | 9 | — | — | — | FAIL | no TUI response from Evaluator |
| 124 | Unknown | 9 | — | — | — | FAIL | no TUI response from Evaluator |
| 125 | Unknown | 9 | — | — | — | FAIL | no TUI response from Evaluator |
| 126 | Unknown | 1440 | INCORRECT | INCORRECT | — | FAIL |  |
| 127 | Unknown | 1850 | PARTIAL | PARTIAL | — | PARTIAL |  |
| 128 | Unknown | 1300 | PARTIAL | INCORRECT | — | PARTIAL |  |
| 129 | Unknown | 1903 | TIMEOUT | TIMEOUT | — | PARTIAL | verifier timeout |
