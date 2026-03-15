# 🗺️ Agent Map: F-Prime-TUI (Mission Control)

This document serves as a high-level technical map of the F-Prime-TUI project. It is designed to help AI agents understand the codebase's architecture, component responsibilities, and operational flows without exhaustive exploration.

---

## 🏗️ Core Architecture
F-Prime-TUI is a Terminal User Interface (TUI) built with **Textual**, designed to provide AI-assisted engineering support for the **NASA F' (F Prime)** framework. It follows a **ReAct (Reason + Act)** loop architecture.

### 1. The Brain: `TUI/app.py`
- **Role**: Main application entry point and orchestrator.
- **Key Functions**:
    - `_ai_loop`: The primary async worker managing the conversational flow.
    - `_stream_and_handle_tools`: Parses AI responses, extracts JSON tool calls, and manages recursive AI turns.
    - `_dispatch_tool`: Routes JSON requests to the appropriate execution layer (`tools.py` or `shell.py`).
    - `_handle_hitl_approval`: Manages the "Human-In-The-Loop" flow for file modifications.
- **UI State**: Manages `TUIMode` (Mission Control vs. Academy), chat history, and input/output widgets.

### 2. The Voice: `TUI/fprime_ai_client.py`
- **Role**: Asynchronous interface for local LLMs via **Ollama**.
- **Key Functions**:
    - `stream_chat`: Streams tokens from Ollama.
    - `_get_system_prompt`: Injects the "Mission Control" or "Academy" persona and tool schemas into the system context.
    - `add_message`: Manages the sliding window of conversation history.

### 2.5 The Knowledge Layer: `TUI/rag/`
- **Role**: Offline retrieval-augmented generation for F' domain knowledge.
- **Key Files**:
    - `chunker.py`: Splits `.md`, `.fpp`, and `.py` source files into semantic chunks with SHA-256 deduplication.
    - `retriever.py`: Hybrid BM25 + ChromaDB dense search, merged via Reciprocal Rank Fusion. Public interface: `query(text) -> {answer_context, sources}`.
    - `indexer.py`: One-time CLI script (`python -m rag.indexer`) that clones fprime repos, embeds via `nomic-embed-text`, and writes `TUI/rag/db/`.
    - `prompt.py`: Standalone prompt builder for CLI/batch use (not used by TUI directly).
- **Integration Point**: `app.py::_process_standard_query()` — RAG context is injected into `extra_ctx` before the Ollama call, Mission Control mode only.
- **Index location**: `TUI/rag/db/` (gitignored). Must be built by user before RAG activates.

### 3. The Hands (File I/O): `TUI/tools.py`
- **Role**: Low-level asynchronous file system operations.
- **Key Functions**:
    - `execute_read_file`: Reads file content with safety truncation (100k limit).
    - `execute_replace_in_file`: Performs surgical, exact-match string replacements (prevents accidental mass overwrites).
    - `execute_list_directory`: Provides directory tree visibility to the AI.

### 4. The Legs (Execution): `TUI/shell.py`
- **Role**: Subprocess management for the F' build environment.
- **Key Functions**:
    - `run_fprime_command`: Automatically locates and activates the `fprime-venv`, executing `fprime-util` commands (`build`, `check`, `generate`, etc.) within the correct project context.

---

## 📂 Directory Structure & Navigation

### Source Code (`TUI/`)
- `app.py`: Main TUI logic and event handling.
- `fprime_ai_client.py`: Ollama client and prompt engineering.
- `tools.py`: File system tool implementations.
- `shell.py`: F' command execution logic.
- `command_definitions.py`: Definitions for slash commands (`/mode`, `/clear`) and `TUIMode` enums.
- `widgets.py`: Custom UI components like `FadingScrollContainer`.
- `style.tcss`: The **JPL Mars Theme** styling (Textual CSS).
- `utils.py`: Helper functions (e.g., `find_fprime_venv`).

### Documentation (`docs/`)
- `implementation/`: Deep dives into architecture (`architecture.md`) and technical decisions (`choices.md`).
- `planning/`: Historical and future implementation plans.
- `fprime-docs/`: Domain-specific reference for F' conventions and commands.

### Testing (`tests/`)
- `conftest.py`: Critical file that **mocks the AI client** for deterministic testing.
- `test_app.py`: UI-level integration tests.
- `test_tools.py` / `test_shell.py`: Unit tests for the execution layer.
- `golden_files/`: Reference Markdown files used to verify chat history formatting.

### Project Root
- `fprime-tui`: The entry-point bash script. Handles Python venv resolution and path switching.
- `Makefile`: Automation for `install`, `test`, and `alias` (global install).
- `GEMINI.md`: Core mandates and development principles for AI agents.

---

## 🔄 The Tool Execution Flow
1. **Request**: AI emits a Markdown block: ` ```json {"tool_name": "read_file", ...} ``` `.
2. **Extraction**: `app.py` extracts the JSON and updates the UI with a "PENDING" status.
3. **Validation**:
    - For `replace_in_file`: `app.py` pauses and asks the user for approval (`1` or `2`).
    - For other tools: Execution proceeds automatically.
4. **Execution**: `tools.py` or `shell.py` performs the action.
5. **Feedback**: The tool result (stdout, stderr, or file content) is wrapped as a `user` message and sent back to Ollama.
6. **Finalization**: AI analyzes the result and either requests another tool or provides a final textual answer.

---

## 🛠️ Developer & Agent Tools
- **Slash Commands**: `/mode dev`, `/mode academy`, `/clear`, `/exit`.
- **Mentions**: Use `@filename` in the input to inject file content directly into the next AI prompt.
- **Testing**: Run `make test` to verify any changes to the TUI or tool logic.
