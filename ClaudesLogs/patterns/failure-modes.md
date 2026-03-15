# Failure Mode Patterns

Recurring issues found across evaluation sessions.

---

## P1: "Sticky Junk Sources"
**Description:** `Svc/FileManager/docs/sdd.md` and `Svc/ComLogger/README.md` appear as
RAG sources for many unrelated queries. These are large service documentation files
that contain enough generic F' vocabulary to score well on BM25.
**Seen in:** Q1, Q2
**Impact:** Dilutes context with irrelevant service details, pushing correct content out of FINAL_K=3 slots.

---

## P2: "Retrieved but Ignored"
**Description:** RAG retrieves the correct source (e.g., `state-machines.md`) but the
model response does not reflect the content of that document. The model falls back on
parametric knowledge about state machines in general (generic OOP/UML patterns).
**Seen in:** Q2
**Impact:** Correct source in context, wrong answer. Suggests prompt needs stronger instruction
to use retrieved content, or the chunk content doesn't contain the FPP-specific syntax.

---

## P3: "Framework Confusion — Unit Tests vs Integration Tests"
**Description:** Questions about GTest C++ unit test macros receive answers describing
the Python `fprime_test_api` integration test API instead.
**Seen in:** Q4 (partially observed before log capture)
**Impact:** Completely wrong framework cited. `ASSERT_EVENTS_SIZE`/`ASSERT_EVENTS_EventName`
macros not mentioned.

---

## P4: "Guarded Command Mischaracterization"
**Description:** "Guarded" command type described as requiring a "guard condition on telemetry"
rather than the correct definition: mutex-protected synchronous execution.
**Seen in:** Q3
**Impact:** Misleading technical answer. A developer reading this would implement the wrong pattern.

---
