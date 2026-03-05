---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching any code.
---

# Writing Plans
## Prerequisite
> **FOR GEMINI:** Before proceeding, you MUST invoke the `core-engineering-standards` skill and apply its principles (Checklists, Negative Constraints, CoT, and Progressive Disclosure) to this task.

## Overview
Write comprehensive implementation plans assuming the engineer has zero context for our codebase. Document everything: which files to touch for each task, code, testing, and verification steps. Give the whole plan as bite-sized tasks (2-5 minutes each).

## Plan Structure
Every plan MUST start with this header:
# [Feature Name] Implementation Plan
> **For Gemini:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.
**Goal:** [One sentence description]
**Architecture:** [Approach details]
---

## Task Granularity
Each step must follow this sequence:
1. Write the failing test.
2. Run it to make sure it fails.
3. Implement the minimal code to make the test pass.
4. Run the tests and make sure they pass.
5. Commit.

## Remember
- Exact file paths always.
- Complete code in plan (no "add validation" placeholders).
- Exact commands with expected output.
- DRY, YAGNI, TDD, and frequent commits.
