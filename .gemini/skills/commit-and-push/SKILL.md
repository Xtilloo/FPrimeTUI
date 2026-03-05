---
name: commit-and-push
description: Summarize, organize, and push the latest changes in a git repository. Use when the user wants to wrap up their current development session by creating logical commits and pushing them to the remote.
---

# Commit and Push Workflow

This skill provides a structured process for organizing local changes into clean, logical commits and pushing them to the remote repository.

## Workflow Steps

### 1. Summarize Changes
- Run `git status` and `git diff HEAD` to understand the scope of all modified and untracked files.
- Group related changes into logical units. For example:
    - **feat**: New features or significant UI changes.
    - **fix**: Bug fixes.
    - **test**: New tests or test refactoring.
    - **docs**: Documentation updates.
    - **chore**: Build script changes, dependency updates, etc.

### 2. Organize and Stage
- For each logical unit:
    - Identify the specific files involved.
    - Stage them using `git add <files>`.
    - Review the staged changes to ensure they are complete and don't include unrelated work.

### 3. Commit
- Draft a concise, imperative-style commit message (e.g., "feat: implement turn-based chat UI").
- Propose the commit message to the user for approval.
- Execute `git commit -m "<message>"`.

### 4. Push
- After all commits are made, run `git push origin <current_branch>`.
- Confirm the push was successful with `git status`.

## Best Practices
- **Atomic Commits:** Each commit should represent a single logical change.
- **Clear Messages:** Start with a type (feat, fix, etc.) and use a concise summary.
- **Review Before Pushing:** Always verify the final state of the branch before pushing.
