# Autonomous RAG Evaluation Agent — Instructions

## Context

You are continuing a RAG (Retrieval-Augmented Generation) evaluation experiment on the
fprime-tui project at `/Users/xtilloo/Projects/FPrimeTUI`.

The experiment tests how well the TUI answers F' framework questions using its RAG system.
Questions come from a training dataset. You compare TUI responses against expected answers
and log your findings. THIS IS DATA ACQUISITION ONLY — do not fix anything.

## What has already been done

- Q1–Q190 have been evaluated. Results are in `ClaudesLogs/sessions/2026-03-14.md`.
- Raw TUI responses are in `ClaudesLogs/sessions/2026-03-14-raw.log`.
- The TUI is running on cmux surface:41 in MISSION_CONTROL mode.
- The TUI has been patched to log all responses to `ClaudesLogs/sessions/2026-03-14-raw.log`.
- The git branch is `rag_implementation`. Push ONCE at the very end after Q262.

## Your task: evaluate Q191 through Q262

The training questions are in:
`/Users/xtilloo/Projects/FPrimeTUI/FPrimeSampleProject/docs/fprime_training.md`

The table has columns: ID | Category | Question (Prompt) | Comprehensive Answer | Technical Reference

## Procedure (repeat for each question)

1. Send the question to the TUI:
   ```bash
   cmux send --surface surface:41 "/clear\n"
   sleep 2
   cmux send --surface surface:41 "<QUESTION TEXT>\n"
   ```

2. Wait 45 seconds for the response:
   ```bash
   sleep 45
   ```

3. Read the raw log to get the full response:
   ```bash
   tail -40 /Users/xtilloo/Projects/FPrimeTUI/ClaudesLogs/sessions/2026-03-14-raw.log
   ```

4. Compare the response against the "Comprehensive Answer" column in the training file.

5. **APPEND** your verdict to the END of `ClaudesLogs/sessions/2026-03-14.md`.

   **CRITICAL — ORDERING RULE:** Every new entry MUST go at the END of the file, after
   the last `---` separator. Never insert in the middle. Always read the last 4 lines of
   the file first to get the exact trailing text to anchor your append.

   Use this format:
   ```
   ### Q<N> — <short topic>
   **Expected key concepts:** <2-3 key facts from the Comprehensive Answer>
   **Sources:** `<source1> · <source2> · <source3>` [✅ correct / 🔍 off-target / ❌ wrong]
   **Verdict:** ✅ PASS / ⚠️ PARTIAL / ❌ FAIL
   **Notes:** <what was wrong or missing, if any>

   ---
   ```

6. While waiting for each response (during the 45s sleep), write the verdict for the
   PREVIOUS question. This keeps the pipeline moving.

7. Commit locally every 10 questions:
   ```bash
   git add ClaudesLogs/
   git commit -m "docs(training): add Q<N>-Q<N+9> RAG evaluations"
   ```
   Do NOT push until Q262 is complete. Then push once:
   ```bash
   git push
   ```

## Verdict criteria

- ✅ PASS — response captures the key concepts from the expected answer
- ⚠️ PARTIAL — partially correct but missing important technical detail
- ❌ FAIL — wrong, misleading, or uses wrong framework/API entirely

## Important rules

- DO NOT fix the TUI code or RAG system — pure data collection only
- DO NOT skip questions — evaluate every single one from Q191 to Q262
- The TUI must stay in MISSION_CONTROL mode. If it shows ACADEMY mode, send `/mode dev`
- The log file grows continuously — always read the tail to get the latest response
- Check the TUI is still running: `ps aux | grep app.py | grep -v grep`
- If TUI dies, restart it:
  ```bash
  PYTHONPATH=/Users/xtilloo/Projects/FPrimeTUI/TUI /Users/xtilloo/Projects/FPrimeTUI/venv/bin/python /Users/xtilloo/Projects/FPrimeTUI/TUI/app.py
  ```
  Then send `/mode dev`.

## Source quality scoring

When evaluating sources, note:
- Sources matching the "Technical Reference" column = ✅ correct
- Sources in the right ballpark = 🔍 partially relevant
- Svc/FileManager, Svc/ComLogger, Svc/PassiveRateGroup showing up for unrelated questions = ❌ sticky junk sources (Pattern P1)
- Same source appearing 2-3 times = suspicious (Pattern P1)

## Running totals through Q190

Update these in the session log header after completing Q262:
- PASS: ~45
- PARTIAL: ~80
- FAIL: ~65
