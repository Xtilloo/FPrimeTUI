---
name: brainstorming
description: Use this before any creative work—creating features, building components, adding functionality, or modifying behavior. It explores user intent, requirements, and design before implementation.
---

# Brainstorming Ideas Into Designs
## Prerequisite
> **FOR GEMINI:** Before proceeding, you MUST invoke the `core-engineering-standards` skill and apply its principles (Checklists, Negative Constraints, CoT, and Progressive Disclosure) to this task.

## Overview
Help turn ideas into fully formed designs and specs through natural collaborative dialogue. Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to EVERY project regardless of perceived simplicity.

## Checklist
You MUST create a task for each of these items and complete them in order:
1. Explore project context — check files, docs, recent commits.
2. Ask clarifying questions — one at a time, understand purpose/constraints/success criteria.
3. Propose 2-3 approaches — with trade-offs and your recommendation.
4. Present design — in sections scaled to their complexity, get user approval after each section.
5. Write design doc — save to docs/plans/YYYY-MM-DD-<topic>-design.md and commit.
6. Transition to implementation — invoke writing-plans skill.

## Key Principles
- One question at a time: Don't overwhelm with multiple questions.
- Multiple choice preferred: Easier to answer than open-ended.
- YAGNI ruthlessly: Remove unnecessary features from all designs.
- Incremental validation: Present design, get approval before moving on.
