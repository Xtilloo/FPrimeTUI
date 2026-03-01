# Software Design Document (SDD)

This document describes the individual Python files that make up the F-Prime-TUI (Mission Control) application, detailing their purpose, key classes, and main functions.

## 1. `TUI/app.py`
**Purpose:** The main entry point and controller for the Terminal User Interface. It integrates the UI rendering, the async ReAct loop, and tool execution dispatch.

**Key Components:**
*   `FPrimeTUI (App)`: The core Textual application class.
    *   `compose()`: Defines the layout (chat container, input area, autocomplete list).
    *   `handle_input_changed()` / `handle_ai_query()`: Captures user input, handles autocomplete, routes fast-path commands (`/`), and triggers AI generations.
    *   `stream_ai_response()`: The main async worker that streams chunks from the Ollama client to the UI, updates the chat history, and looks for JSON tool requests.
    *   `handle_tool_call()`: Intercepts JSON tool requests, triggers Human-In-The-Loop approval (if required), executes the corresponding function from `tools.py` or `shell.py`, and formats the result.
    *   `_finish_tool_call()`: Passes the result of a tool back to the AI client and recursively restarts the generation worker to close the ReAct loop.

## 2. `TUI/fprime_ai_client.py`
**Purpose:** The Brain wrapper. It manages asynchronous communication with the local Ollama instance and maintains the conversational state.

**Key Components:**
*   `FPrimeAIClient`: 
    *   `__init__()`: Initializes the `ollama.AsyncClient` and the `chat_history` list.
    *   `_get_system_prompt()`: Dynamically constructs the strict system prompt detailing the ReAct loop rules, JSON formatting constraints, and available tools.
    *   `stream_chat()`: Appends context, formats the payload, and yields an asynchronous stream of response tokens from the local LLM.

## 3. `TUI/shell.py`
**Purpose:** The environment execution handler. It provides an async bridge to the underlying bash shell.

**Key Components:**
*   `run_fprime_command()`: Uses `asyncio.create_subprocess_shell` to execute a command. Crucially, it sources the dynamic `fprime-venv` activation script in the same shell execution to ensure `fprime-util` has the proper context. It captures and returns standard output, standard error, and the exit code.

## 4. `TUI/tools.py`
**Purpose:** The file system manipulation toolbox for the AI agent.

**Key Components:**
*   `execute_read_file()`: Asynchronously reads file contents using `aiofiles`. Contains length truncation logic to protect the LLM context window from massive files.
*   `execute_replace_in_file()`: Safely edits a file. Requires an exact match of an `old_content` string to prevent accidental overwrites or partial replacements. 
*   `execute_list_directory()`: Wraps `os.listdir` to return directory contents.

## 5. `TUI/utils.py`
**Purpose:** Helper functions for environment discovery.

**Key Components:**
*   `find_fprime_venv()`: Traverses the directory tree upwards from a starting path (defaulting to the current working directory) to locate the active `fprime-venv` directory needed to run F' builds.

## 6. `TUI/widgets.py`
**Purpose:** Custom UI components built on top of Textual.

**Key Components:**
*   `FadingScrollContainer`: A specialized `VerticalScroll` container that watches scroll offset events to dynamically hide the scrollbar when inactive, providing a cleaner, more immersive terminal experience.