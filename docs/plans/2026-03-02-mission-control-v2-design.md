# Design Doc: Mission Control v2 - Modular Autonomous Loop & Self-Correcting Help System

**Date:** 2026-03-02
**Status:** Approved
**Goal:** Modularize `app.py`, implement a "Command Guard" for F' syntax validation, and create a "Fair Process" recovery hierarchy using a new `grep_docs` tool.

---

## 1. Architectural Overview

The system transitions from a monolithic `app.py` to a **Controller-Based Orchestration** model. The UI layer (`app.py`) will delegate logic to specialized controllers in `TUI/controllers/`.

### 1.1 New Components
- **`MissionController` (`TUI/controllers/mission.py`):**
    - Manages the autonomous state machine.
    - Tracks `failure_count` and `recovery_phase`.
    - Enforces the "3+ failures" hard stop.
- **`AIHandler` (`TUI/controllers/ai_handler.py`):**
    - Manages the Ollama streaming loop.
    - Implements robust regex-based JSON tool extraction (fallback for missing backticks).
    - Decouples AI communication from the UI thread.
- **`CommandGuard` (`TUI/controllers/command_guard.py`):**
    - Intercepts AI tool calls *before* execution.
    - Performs fuzzy matching against `docs/fprime_commands.md`.
    - Validates command dependencies (e.g., "Build requires Generate").
    - Injects "Live Suggestions" back to the AI.

---

## 2. The Self-Correcting Help System

### 2.1 The `grep_docs` Tool
A new tool implemented in `TUI/tools.py` that allows the AI to search the `docs/` directory for solutions.
- **Input:** `query` (string)
- **Output:** List of file matches with context lines.
- **Constraint:** Max 1000 characters returned to AI.

### 2.2 The Recovery Hierarchy ("Fair Process")
Upon tool failure, the `MissionController` dictates the next AI prompt:
1. **Failure 1:** Force `--help` flag for the failed command.
2. **Failure 2:** Force `grep_docs` to search for the command's "Intent".
3. **Failure 3:** Hard stop; notify the user to check manual logs.

---

## 3. The Command Guard (Fuzzy Matching)

The `CommandGuard` uses a "Command Reference Map" in `docs/fprime_commands.md` to identify hallucinated F' commands.

**Example Interception:**
- **AI Output:** `fprime-util generate component MyComp`
- **Guard Match:** "generate" + "component" -> Intent: "Create new component".
- **Guard Correction:** "INVALID SYNTAX. Use `fprime-util new --component`."

---

## 4. Modularization Strategy

1. **Phase 1: Skeleton Creation**
    - Create `TUI/controllers/` directory and `__init__.py`.
    - Create empty controller classes with stubs.
2. **Phase 2: Logic Migration**
    - Move JSON parsing from `app.py` to `AIHandler`.
    - Move failure tracking to `MissionController`.
    - Move `run_fprime_command` validation to `CommandGuard`.
3. **Phase 3: UI Integration**
    - Refactor `app.py` to use controller instances.
    - Implement the "Silent Bootstrap" environment probe on mount.

---

## 5. Verification Plan

### 5.1 Unit Tests
- `tests/test_command_guard.py`: Verify fuzzy matching and dependency checks.
- `tests/test_grep_docs.py`: Verify search accuracy and context windowing.
- `tests/test_mission_controller.py`: Verify the recovery state machine (0 -> 1 -> 2 -> 3).

### 5.2 Integration Tests
- Verify the "Silent Bootstrap" injects correct environment info into the AI's initial context.
- Verify that a hallucinated command triggers an immediate "Live Suggestion" without hitting the shell.
