# Plan: Agent Architecture

## 1. Introduction
This document defines the core architecture of the Mission Control AI Agent. The most critical design decision in this project is the strict separation between the "Brain" (the LLM deciding what to do) and the "Hands" (the TUI executing the actions). 

## 2. The "Brain vs. Hands" Paradigm
Directly wiring an LLM to a shell is a major security risk and leads to unpredictable behavior. Instead, we use a Tool-Calling Architecture (also known as Function Calling).

### 2.1. The Brain (Local LLM via Ollama)
*   **Role:** Intent parsing, planning, and context analysis.
*   **Capabilities:** Generates text, parses chat history, and emits structured JSON requests to invoke tools.
*   **Limitations:** Has absolutely no direct access to the file system, network, or terminal environment. It only knows what the TUI tells it.

### 2.2. The Hands (TUI Application)
*   **Role:** Safely executing system operations and managing user interaction.
*   **Capabilities:** Runs subprocesses, reads/writes files, queries the user for confirmation, and maintains the state of the chat UI.
*   **Responsibilities:** Parses the LLM's JSON tool requests, validates them, executes the corresponding Python functions, and feeds the results back to the LLM.

## 3. The ReAct (Reasoning + Acting) Loop
The core engine of Mission Control is a recursive loop. When a user submits a prompt, the following cycle initiates:

1.  **User Input:** "Add a telemetry port to `MyComponent.fpp`"
2.  **AI Analysis (Reasoning):** The LLM realizes it needs to see the file first.
3.  **AI Tool Request (Acting):** The LLM outputs a JSON payload requesting `read_file("MyComponent.fpp")`.
4.  **TUI Interception:** The TUI catches the JSON, suspends the chat stream, and executes the tool.
5.  **Tool Execution:** The TUI reads the file from disk.
6.  **Context Injection:** The TUI appends the file contents to the chat history as a "Tool Response".
7.  **Loop Restart:** The TUI sends the updated history back to the LLM.
8.  **AI Analysis 2:** The LLM reads the file content, formulates the edit.
9.  **AI Tool Request 2:** The LLM outputs JSON requesting `replace_in_file(...)`.
10. **TUI Execution & HITL:** The TUI catches the request, prompts the user for confirmation (Human-In-The-Loop), applies the change, and sends the success status back.
11. **Final Resolution:** The LLM sees the task is complete and generates a final markdown summary for the user.

## 4. Human-in-the-Loop (HITL) Protocol
Automation is powerful, but destructive actions must be gatekept by the developer.

*   **Safe Actions (Auto-Execute):** `read_file`, `run_fprime_command("info")`, `list_directory`. These execute immediately to keep the loop fast.
*   **Destructive Actions (Require Confirmation):** `replace_in_file`, `write_file`, `run_fprime_command("purge")`, `delete_file`.
*   **Implementation:** When a destructive tool is requested, the TUI pauses the ReAct loop and overlays a modal dialog (e.g., showing a diff of the proposed file changes). If the user accepts, the tool runs. If rejected, a "User rejected the action" message is sent back to the LLM, prompting it to rethink its approach.

## 5. State Management
The state of the conversation and the environment must be carefully managed.
*   **Chat History:** Maintained by the TUI. Must include System Prompts, User Messages, Assistant Messages, Tool Requests, and Tool Responses.
*   **Project State:** The TUI caches the absolute path to the project root and the `fprime-venv` upon initialization to ensure all subsequent shell commands operate in the correct context.