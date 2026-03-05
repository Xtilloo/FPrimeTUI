---
name: executing-plans
description: Use when you have a written implementation plan to execute with review checkpoints.
---

# Executing Plans
## Prerequisite
> **FOR GEMINI:** Before proceeding, you MUST invoke the `core-engineering-standards` skill and apply its principles (Checklists, Negative Constraints, CoT, and Progressive Disclosure) to this task.

## Overview
Load plan, review critically, execute tasks in batches, and report for review between batches.
Announce at start: "I'm using the executing-plans skill to implement this plan."

## The Process
1. Step 1: Load and Review Plan. Read the plan file. Identify concerns. If none, proceed.
2. Step 2: Execute Batch. Default to the first 3 tasks. For each task: Mark as in_progress, follow steps exactly, run verifications, and mark as completed.
3. Step 3: Report. Show what was implemented and the verification output. Say: "Ready for feedback."
4. Step 4: Continue. Apply feedback and execute the next batch.

## When to Stop
STOP immediately if:
- You hit a blocker mid-batch (missing dependency, test failure).
- The plan has critical gaps.
- Verification fails repeatedly.
