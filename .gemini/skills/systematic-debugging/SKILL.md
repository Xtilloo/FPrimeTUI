---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes.
---

# Systematic Debugging
## Prerequisite
> **FOR GEMINI:** Before proceeding, you MUST invoke the `core-engineering-standards` skill and apply its principles (Checklists, Negative Constraints, CoT, and Progressive Disclosure) to this task.

## Core Principle
ALWAYS find the root cause before attempting fixes. Symptom fixes are a failure.

## The Four Phases
1. Phase 1: Root Cause Investigation. Read errors carefully, reproduce consistently, and check recent changes. Trace data flow backward from the error.
2. Phase 2: Pattern Analysis. Find working examples in the codebase. Identify exactly what is different between the working and broken code.
3. Phase 3: Hypothesis and Testing. State: "I think X is the root cause because Y." Make the SMALLEST possible change to test that single hypothesis.
4. Phase 4: Implementation. Create a failing test case first. Implement the single fix. Verify the fix and ensure no regressions.

## Red Flags
- "Quick fix for now, investigate later."
- "Just try changing X and see if it works."
- Proposing solutions before tracing data flow.
