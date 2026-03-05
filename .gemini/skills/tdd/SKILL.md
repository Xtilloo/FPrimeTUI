---
name: tdd
description: Use when implementing any feature or bugfix, before writing any implementation code.
---

# Test-Driven Development (TDD)
## Prerequisite
> **FOR GEMINI:** Before proceeding, you MUST invoke the `core-engineering-standards` skill and apply its principles (Checklists, Negative Constraints, CoT, and Progressive Disclosure) to this task.

## The Iron Law
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST. If you write code before the test, delete it and start over.

## Red-Green-Refactor Cycle
1. RED: Write one minimal test showing what should happen. Watch it fail. Confirm the failure message is what you expected (not a syntax error).
2. GREEN: Write the simplest, most minimal code to pass the test. Don't add features or "improve" things yet.
3. REFACTOR: Clean up duplication, improve names, and extract helpers while keeping the tests green.

## Why Order Matters
Tests written after code pass immediately and prove nothing. Test-first forces you to see the test fail, proving it actually validates the requirement.
