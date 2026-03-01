# Plan: Core Features

## 1. Overview
This document outlines the core feature set of Mission Control, prioritized by immediate utility and technical foundational requirements. The features are broken down into phases to ensure an iterative, stable rollout.

## 2. Phase 1: Environment & Command Execution (The Foundation)
Before the AI can write code, it must be able to compile it. This phase focuses on bridging the gap between the TUI and the F' build system.

### 2.1. Dynamic F' Virtual Environment Discovery
*   **Requirement:** The TUI must locate the `fprime-venv` associated with the project.
*   **Mechanism:** Upon startup, the TUI searches the current working directory, and traverses upwards until it finds a directory containing `fprime-venv`.
*   **Failure State:** If no venv is found, the TUI enters a degraded "chat only" mode and alerts the user.

### 2.2. Standard F' Command Execution
*   **Requirement:** Execute standard `fprime-util` commands.
*   **Mechanism:** All commands are wrapped in `bash -c "source <path_to_venv>/bin/activate && fprime-util <args>"`.
*   **Supported Commands:** `build`, `check`, `generate`, `purge`, `impl`.
*   **Output Handling:** Standard output and standard error must be captured asynchronously and streamed to a dedicated terminal widget within the TUI to avoid blocking the main UI thread.

### 2.3. Direct Command Overrides (Fast Path)
*   **Requirement:** Allow users to bypass the AI for standard commands.
*   **Mechanism:** Input prefixed with `/` (e.g., `/build`) is immediately routed to the command execution engine, skipping the LLM entirely.

## 3. Phase 2: Codebase Navigation & Manipulation (The Hands)
This phase empowers the AI to interact with the project files.

### 3.1. File System Inspection
*   **Requirement:** The AI must be able to read files and list directories.
*   **Tools:**
    *   `read_file(filepath)`: Returns file contents (with truncation for extremely large files to protect context limits).
    *   `list_directory(path)`: Returns a list of files/folders in a given directory.

### 3.2. Safe Code Modification
*   **Requirement:** The AI must be able to edit code securely.
*   **Tools:**
    *   `replace_in_file(filepath, old_str, new_str)`: Replaces a specific block of text. This requires an exact string match for safety.
    *   `write_file(filepath, content)`: Creates a new file or overwrites an existing one.
*   **Safety:** All modification tools trigger the Human-In-The-Loop (HITL) confirmation modal.

## 4. Phase 3: F' Specific Intelligence (The Brain)
With the foundational tools in place, we tune the AI for specific F' workflows.

### 4.1. Component Generation & Implementation
*   **Workflow:** User asks to "Create a new active component named IMUReader".
*   **AI Actions:**
    1.  Uses a new tool (e.g., `scaffold_fprime_component`) which leverages the `fprime-cli` programmatic API or CLI flags to generate the component *non-interactively*, passing the name, kind, and namespace as arguments to avoid blocking on user prompts.
    2.  Uses `run_fprime_command` to run `fprime-util impl` to generate `.hpp-template` and `.cpp-template`.
    3.  Uses `read_file` to inspect the templates.
    4.  Uses `write_file` to save the final `.hpp` and `.cpp` files based on the templates.

### 4.2. Build Error Diagnostics
*   **Workflow:** A build fails.
*   **AI Actions:**
    1.  The TUI automatically captures the `stderr` from the failed build command.
    2.  The TUI appends the error log to the AI context.
    3.  The AI analyzes the C++ compiler errors, uses `read_file` to inspect the failing code lines, and proposes a fix using `replace_in_file`.

## 5. Phase 4: Advanced Capabilities (Future Scope)
*   **Topology Summarization:** Parsing topology XML/FPP to generate markdown graphs of component connections.
*   **Automated Unit Testing:** Running F' unit tests and auto-generating missing test cases based on component definitions.
*   **Dictionary Generation:** Assisting in drafting command, telemetry, and event dictionaries based on natural language descriptions.