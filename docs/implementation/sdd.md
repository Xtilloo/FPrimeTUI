# Software Design Document (SDD) - Mission Control v2

This document describes the individual Python files that make up the F-Prime-TUI (Mission Control) application, detailing their purpose, key classes, and main functions.

## 1. Core Application
### `TUI/app.py`
**Purpose:** The UI orchestrator. It manages the Textual layout and routes interactions between the user and the logic controllers.
*   `FPrimeTUI (App)`: Main application class.
    *   `_ai_loop()`: Orchestrates the ReAct cycle by coordinating the AI Handler, Command Guard, and Mission Controller.
    *   `_dispatch_tool()`: Maps validated tool calls to the underlying execution functions in `tools.py` and `shell.py`.

### `TUI/fprime_ai_client.py`
**Purpose:** Asynchronous client for the local Ollama instance.
*   `FPrimeAIClient`: Manages chat history and streaming interaction with the LLM.

## 2. Controllers (The Brain)
See [Controllers Deep-Dive](controllers.md) for more detail.

### `TUI/controllers/ai_handler.py`
**Purpose:** Manages the AI interaction loop and robust parsing.
*   `AIHandler`: 
    *   `parse_tool_call()`: Uses regex and JSON parsing to reliably extract tool requests from LLM markdown streams.
    *   `add_message()`: Maintains the synchronous history for the AI client.

### `TUI/controllers/command_guard.py`
**Purpose:** The safety and repair engine.
*   `CommandGuard`:
    *   `validate()`: Checks commands against the `COMMAND_REGISTRY` and identifies missing dependencies (e.g., build cache).
    *   `repair()`: **Auto-corrects** hallucinated commands (e.g., `fpp-generate`) and sets the correct `cwd` based on project root discovery.

### `TUI/controllers/mission.py`
**Purpose:** Manages the autonomous mission state.
*   `MissionController`:
    *   `on_tool_fail()` / `on_tool_success()`: Tracks failure streaks.
    *   `get_recovery_directive()`: Implements the **Fair Process Recovery Hierarchy**, escalating from a simple `help` hint to a mandatory `grep_docs` search before final fatigue.

## 3. Execution Layer (The Hands)
### `TUI/shell.py`
**Purpose:** Bridge to the bash shell and F' utilities.
*   `run_fprime_command()`: Executes commands within the virtual environment and applies **Error Fingerprinting** to provide context-aware hints for common F' failures.
*   `check_environment()`: Discovers `fprime-venv`, `settings.ini`, and the project root.

### `TUI/tools.py`
**Purpose:** Agent-accessible file system tools.
*   `execute_read_file()`: Reads file content with intelligent truncation.
*   `execute_replace_in_file()`: Performs atomic, exact-match string replacements.
*   `execute_list_directory()`: Standard directory traversal.
*   `execute_grep_docs()`: High-performance keyword search through the `docs/` folder.

## 4. Definitions & Utilities
### `TUI/command_definitions.py`
**Purpose:** Structured registry for valid F' commands and known error patterns.
*   `COMMAND_REGISTRY`: Defines safe arguments and required files for utilities.
*   `ERROR_FINGERPRINTS`: Regex-based database of known F' errors and their recovery hints.
*   `SLASH_COMMANDS`: Registry for TUI-level fast-path commands.

### `TUI/utils.py`
**Purpose:** Helper functions for path resolution and environment discovery.
