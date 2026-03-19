# Training Pipeline Findings — 2026-03-16

## What We Ran

- **685 Q&A questions** from `docs/training/fprime_training.md`
- **3-agent architecture**: TUI (surface:19) + Python Evaluator (surface:20) + Claude Orchestrator
- **Verifiers**: Headless Gemini Flash / Flash-Lite subprocesses spawned per question
- **Questions processed**: Q1–Q129 before manual stop

## Final Results (Q1–Q129)

| Outcome  | Count | % of processed |
|----------|-------|----------------|
| PASS     | 11    | 8.5%           |
| PARTIAL  | 79    | 61.2%          |
| FAIL     | 25    | 19.4%          |
| Total    | 115   | —              |

Note: 14 questions have no verifier verdict due to quota timeouts (Q36–Q57) — those got
defaulted to PARTIAL and are unreliable.

---

## What Worked

### Python Evaluator (`scripts/evaluator.py`)
Replacing the Gemini evaluator with a pure Python script was the right call.
- Deterministic, no LLM non-determinism
- Session log polling (byte offset) reliably captures full TUI responses
- Checkpoint/resume works correctly
- `cmux send` integration is solid

### Session Log as Response Capture
Polling `ClaudesLogs/sessions/YYYY-MM-DD-raw.log` for `---RESPONSE---` markers is the
correct approach. Screen scraping via `cmux read-screen` was unusable (ANSI codes, truncation).

### Orchestrator Race Condition Fix
Atomic `status: "processing"` write in `read_exchange()` correctly prevents double-spawning.

---

## What Failed

### 1. Verifier JSON Parse Errors — 22/129 (17%)
Gemini Flash and Flash-Lite both produce malformed JSON at a significant rate
(trailing commas, unescaped characters in citation strings). When parsing fails,
the orchestrator defaults the verdict to PARTIAL regardless of actual response quality.
This means:
- Real FAILs get upgraded to PARTIAL → inflate review queue
- Real PASSes get downgraded to PARTIAL → miss curated data

### 2. Gemini Flash Quota Exhaustion — Twice
- First exhaustion: Q36 (Run 2). All Q36–Q57 verifiers timed out → 22 fake PARTIALs.
- Second exhaustion: Q128 (Run 3). Switched to Flash-Lite mid-run.
- Daily quota insufficient for full 685-question run (685 × 2 = 1,370 verifier calls).

### 3. Verifier False Positive (Confirmed)
Q99: "How do you clear the event table in the GDS GUI?"
- TUI response: "In F' Academy mode, we focus on learning concepts..." (evasion/non-answer)
- Verifier verdict: PASS (both V1 and V2)
- This answer was written to `fine_tuning.jsonl` as curated truth — incorrect.

### 4. TUI Crash (Q122)
TUI process crashed silently around Q122. Q122–Q124 got 9-char `"(TIMEOUT)"` responses
and were written as FAIL. Root cause unknown (likely memory pressure or Textual bug).
Pipeline auto-recovered after manual TUI restart.

### 5. Category Not Passed to Orchestrator
`evaluator.py` writes `eval_exchange.json` without a `category` field.
Orchestrator reads `exchange.get("category", "Unknown")` → all entries logged as
`[Unknown]` category. Cosmetic only (no effect on verdicts) but breaks category-level
analysis.

### 6. Off-Topic Questions in Training Data
Questions Q120–Q130+ cover NASA Power of Ten software rules (general coding standards,
not F'-specific). The TUI correctly doesn't know these from F' documentation → legitimate
FAILs, but they skew the pass rate downward artificially.

---

## Architecture Conclusion

**The verifier/consensus layer adds more noise than signal at this stage.**

The core problems:
- Gemini quota limits make full 685-question runs infeasible in one session
- ~17% JSON parse failure rate degrades verdict quality
- False positives exist (verified above)
- The consensus matrix (PARTIAL+PARTIAL → review, CORRECT+INCORRECT → V3) adds
  complexity that depends on verifier reliability — which we don't have

**What we actually need right now:**
Just the raw TUI responses. Once we have all 685 responses stored, evaluation can be
done offline, more carefully, without quota constraints or race conditions.

---

## Recommended Next Step

See `scripts/collect_responses.py` — a stripped-down collection script that:
- Sends each question to the TUI via cmux
- Captures the full response from the session log
- Writes everything to `docs/training/responses.jsonl`
- No verifiers, no LLM agents, no consensus logic
- Resumable from checkpoint

Post-processing evaluation can then be done separately, against the stored responses,
with whatever methodology makes sense (human review, offline LLM batch, etc.).
