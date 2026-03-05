---
name: core-engineering-standards
description: Global engineering directives for Flash and Pro models. Use as a prerequisite for any task-specific skill (Brainstorming, Writing Plans, etc.) to ensure procedural consistency and Flash-proofing.
---

# Core Engineering Standards
## Overview
These global rules apply to ALL high-level engineering tasks. They are designed to "Flash-proof" complex workflows and ensure deterministic outcomes.

## Global Checklist (MANDATORY)
1. **The Checklist Principle:** You MUST explicitly state your current step from the active skill's checklist.
2. **Negative Constraints:** You MUST identify what NOT to do before taking any action (e.g., "I will NOT write code until the design is approved").
3. **Chain-of-Thought (CoT):** You MUST briefly summarize your reasoning and data flow backward from the goal BEFORE proposing a solution.
4. **Progressive Disclosure:** You MUST only read the files or documentation required for the current sub-step. Do NOT overload the context.

## Directives for Every Response
- **Status First:** Start every response with: `[Current Step: <Step Name>]`.
- **Validation-First:** Always identify how you will verify your next action before performing it.
- **Minimalism:** YAGNI (You Aren't Gonna Need It) is the law. Delete or ignore unnecessary feature requests.
