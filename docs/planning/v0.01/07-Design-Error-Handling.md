# Design: Error Handling & Context Strategy

## 1. Context Window Management (Memory)
To ensure the AI understands the full context of a task, the TUI maintains a **continuous conversational state** throughout a session. The context is *not* reset after every command. 

### 1.1. The Message Array
The `fprime_ai_client` maintains a rolling list of messages in standard OpenAI/Ollama format (Role + Content). A typical sequence looks like this:
1.  **System:** (The Base Prompt, Tool Definitions)
2.  **User:** "Create a component and build the project."
3.  **Assistant (AI):** `{"tool_name": "scaffold_component", ...}`
4.  **Tool (System):** "Component created successfully."
5.  **Assistant (AI):** `{"tool_name": "run_fprime_command", "command": "build"}`
6.  **Tool (System):** "Build successful. Output: ..."
7.  **Assistant (AI):** "I have successfully created the component and the build passed. Here is a summary..."

By appending the tool outputs directly into this rolling array, the AI always "remembers" what step of the plan it is currently on and what it just accomplished.

### 1.2. State Reset
The context is only reset when the user explicitly triggers a clear command (e.g., `Ctrl+L` or `/clear`), or if the token limit of the model is reached, at which point older tool executions may be summarized or pruned.

## 2. Overview of Error Handling
In an autonomous agent system, errors are not just terminal exceptions; they are feedback mechanisms. The system must gracefully handle failures from the OS, the user, and the AI itself. This document outlines how errors are caught, formatted, and fed back into the ReAct loop.

## 3. Categories of Errors

### 2.1. AI Hallucinations & Parsing Errors
*   **The Error:** The LLM outputs malformed JSON, requests a tool that doesn't exist, or provides the wrong arguments for a tool.
*   **Handling:** The TUI's JSON parser catches the `JSONDecodeError` or Schema Validation Error.
*   **Resolution:** The TUI does *not* crash. Instead, it creates a "Tool Response" message describing the error and sends it back to the LLM automatically.
    *   *Example feedback:* "System Error: Invalid JSON format. Please ensure your tool request is valid JSON wrapped in ```json tags."
    *   *Example feedback:* "System Error: Tool 'delete_everything' does not exist. Available tools are..."

### 2.2. Subprocess Command Failures
*   **The Error:** An `fprime-util` command exits with a non-zero status code (e.g., compilation failed).
*   **Handling:** The `ShellManager` captures the non-zero exit code along with `stdout` and `stderr`.
*   **Resolution:** The output is fed back to the AI as a standard Tool Response. The AI reads the compiler errors and attempts to diagnose them.
    *   *Example feedback:* "Command exited with code 2. Stderr: error: expected ';' before '}' token."

### 2.3. File System Errors
*   **The Error:** `read_file` is called on a non-existent file, or `replace_in_file` cannot find the exact `old_content` string.
*   **Handling:** Python's `FileNotFoundError` or the string `.replace()` logic failure is caught.
*   **Resolution:** Fed back to the AI.
    *   *Example feedback:* "System Error: File 'MyComponent.fpp' not found in path."
    *   *Example feedback:* "System Error: 'old_content' exact match not found. The file may have changed, or your indentation is incorrect. Use read_file to check the current contents."

### 2.4. User Rejection (HITL)
*   **The Error:** The AI requests `replace_in_file`, but the user looks at the diff in the UI and clicks "Reject".
*   **Handling:** The UI modal returns a `False` boolean to the Tool Dispatcher.
*   **Resolution:** Fed back to the AI to prompt a course correction.
    *   *Example feedback:* "User rejected the proposed file modification. Please ask the user for clarification on what should be changed."

### 2.5. Catastrophic UI Failures
*   **The Error:** Textual rendering crash, disconnected Ollama server.
*   **Handling:** Global exception handlers. If Ollama is unreachable, display a red banner in the TUI: "Connection to local AI lost. Ensure Ollama is running."

## 3. The "Three Strikes" Rule
To prevent infinite loops where the AI repeatedly hallucinates bad JSON or tries to read a missing file:
1.  The TUI maintains a counter of consecutive tool failures.
2.  If the AI fails to execute a valid tool 3 times in a row, the TUI breaks the ReAct loop.
3.  The TUI displays an error to the user: "The AI agent got confused and aborted the task." and clears the active task state.