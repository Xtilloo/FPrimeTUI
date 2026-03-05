---
name: git-worktrees
description: Use when starting feature work that needs isolation from the current workspace or before executing implementation plans.
---

# Using Git Worktrees
## Prerequisite
> **FOR GEMINI:** Before proceeding, you MUST invoke the `core-engineering-standards` skill and apply its principles (Checklists, Negative Constraints, CoT, and Progressive Disclosure) to this task.

## Overview
Create isolated workspaces sharing the same repository.
1. Directory Selection: Check for `.worktrees/` or `worktrees/` directories. If neither exists, ask the user.
2. Safety: Verify the directory is in `.gitignore`. If not, add it and commit immediately.
3. Creation: Run `git worktree add <path> -b <branch_name>`.
4. Setup: Auto-detect project type (Node, Rust, Python, Go) and run install/setup commands.
5. Baseline: Run existing tests to ensure the worktree starts clean. Report "Ready to begin."
