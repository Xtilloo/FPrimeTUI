# ClaudesLogs

My working directory. Gitignored. Structured for clarity across sessions.

## Layout

```
ClaudesLogs/
├── sessions/          # One file per testing session, raw TUI responses + quick verdict
├── rag-analysis/      # Aggregated findings: patterns, root causes, fix candidates
├── patterns/          # Recurring failure types extracted from session data
└── scratch/           # Throwaway notes, debug snippets, temp files
```

## Current Focus

RAG evaluation — testing all 262 questions from `FPrimeSampleProject/docs/fprime_training.md`
against the live TUI in MISSION_CONTROL mode.

Goal: identify prompts where the RAG retrieval is off-target, missing, or where
the model ignores retrieved context.

## Session Log

| Date | File | Questions Tested | Issues Found |
| :--- | :--- | :---: | :---: |
| 2026-03-14 | sessions/2026-03-14.md | ongoing | ongoing |
