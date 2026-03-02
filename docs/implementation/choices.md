# Implementation Choices & Rationale

This document outlines the reasoning behind key technical decisions made during the development of Mission Control.

## 1. Local AI & Tool-Calling vs. Direct Shell Access
**Choice:** Using a local Ollama instance with strict JSON tool-calling schemas instead of giving the AI raw shell execution capabilities.
**Rationale:** 
*   **Security:** F' flight software repositories are sensitive. A local model ensures zero data exfiltration. 
*   **Safety:** Giving an LLM direct shell access is highly unpredictable. Forcing it to emit JSON that the Python application parses and validates ensures it can only perform pre-approved actions (like `read_file` or running specific F' utilities).

## 2. Asynchronous Everything (`asyncio`, `aiofiles`, Textual)
**Choice:** The entire application stack is asynchronous.
**Rationale:** Terminal UIs must maintain 60FPS rendering for smooth typing and scrolling. If a file read or an `fprime-util build` command was performed synchronously, the entire UI would freeze until the command finished. By using `aiofiles` for I/O, `asyncio.subprocess` for shell execution, and Textual's async workers for the LLM stream, the UI remains perfectly responsive during heavy workloads.

## 3. Conversational HITL vs. Modal Overlays
**Choice:** When the AI requests to modify a file (`replace_in_file`), the user is prompted for approval inline within the chat feed via text and autocomplete options, rather than pushing a visual Modal dialog over the screen.
**Rationale:**
*   Textual's DOM lookup methods (`query_one`) are tightly bound to the active screen. Switching back and forth between a Modal screen and the main App screen during an active async data stream caused race conditions and component style lookup crashes (`KeyError: No 'code_inline' key in COMPONENT_CLASSES`).
*   An inline, chat-based approval feels more natural for an interactive agent and allows the user to simply press '1' or '2' without breaking their keyboard flow.

## 4. Exact-Match File Replacement
**Choice:** The `replace_in_file` tool requires the AI to provide an `old_content` string that exactly matches a substring in the file, replacing it with `new_content`.
**Rationale:** This is safer than providing line numbers (which drift easily if the file changes) and safer than allowing the AI to rewrite the entire file (which consumes massive amounts of tokens and increases hallucination risk). The exact-match forces the AI to be surgical.

## 5. Wrapper Script Directory Resolution
**Choice:** The `fprime-tui` bash entry script explicitly saves the caller's working directory (`ORIGINAL_DIR`), locates its own virtual environment to launch python, and then `cd`s back to `ORIGINAL_DIR` before running the TUI.
**Rationale:** The AI needs contextual awareness of the F' project the user is currently working in. If the python script launched from the tool's installation directory, it would fail to find the project's `fprime-venv` or local files. Resolving the execution path dynamically allows the tool to be symlinked globally (`/usr/local/bin/fprime-tui`) and used in any arbitrary project folder.

## 6. Modular "Brain" (Controllers)
**Choice:** Moving logic out of `app.py` and into specialized controllers (`AIHandler`, `CommandGuard`, `MissionController`).
**Rationale:** In v1, `app.py` became a "God Object" managing both UI state and complex ReAct loop logic. Modularizing these concerns makes the codebase easier to test (allowing deterministic unit tests for the Guard and Parser without a full UI) and allows for more complex autonomous behaviors (like the recovery hierarchy) to be implemented cleanly.

## 7. Automated Command Repair
**Choice:** Intercepting and fixing AI tool calls before they are executed, rather than just reporting errors.
**Rationale:** LLMs often hallucinate FPP-specific tools (like `fpp-generate`) or forget to set the correct working directory. By automatically repairing these common mistakes (e.g., redirecting `fpp-generate` to `fprime-util new`), we reduce the number of ReAct turns required to achieve a goal, making the agent feel significantly faster and more competent.