# Design: Tool API Specification

## 1. Overview
This document specifies the JSON schema for the tools available to the AI. The LLM must output exact JSON matching these schemas to trigger an action. The system prompt will instruct the LLM to wrap tool calls in a standard JSON markdown block to allow the TUI parser to easily extract them from conversational text.

## 2. Tool Definition Standard
Every tool request must contain at minimum a `tool_name` key.

```json
{
  "tool_name": "<name_of_the_tool>",
  ... // tool specific arguments
}
```

## 3. Tool Specifications

### 3.1. `run_fprime_command`
Executes an `fprime-util` command within the context of the activated `fprime-venv`.

*   **Arguments:**
    *   `command` (string, required): The specific `fprime-util` command to run (e.g., "build", "check", "generate", "impl").
    *   `args` (string, optional): Additional arguments to pass to the command (e.g., "--all", "-j4", "--new").
*   **Example Request:**
    ```json
    {
      "tool_name": "run_fprime_command",
      "command": "build",
      "args": "-j8"
    }
    ```
*   **Execution Logic:** Translates to `bash -c "source <venv>/bin/activate && fprime-util build -j8"`.
*   **Returns to AI:** The combined standard output and standard error of the command, plus the exit code. If the output is massive, the tail end of the output + exit code is returned.

### 3.2. `read_file`
Reads the contents of a specific file.

*   **Arguments:**
    *   `path` (string, required): The relative or absolute path to the file.
*   **Example Request:**
    ```json
    {
      "tool_name": "read_file",
      "path": "Components/MyComponent/MyComponent.fpp"
    }
    ```
*   **Execution Logic:** Asynchronously opens and reads the file.
*   **Returns to AI:** The file contents. **Constraint:** If the file exceeds a certain token limit (e.g., > 2000 lines), it must return a truncated version with a warning to the AI, to prevent blowing out the context window.

### 3.3. `replace_in_file`
Safely replaces a specific block of text within a file. Requires exact string matching.

*   **Arguments:**
    *   `path` (string, required): The file to modify.
    *   `old_content` (string, required): The exact literal text to find and replace. Must include enough surrounding context (indentation, newlines) to ensure it only matches one location.
    *   `new_content` (string, required): The new text to insert in place of `old_content`.
*   **Example Request:**
    ```json
    {
      "tool_name": "replace_in_file",
      "path": "Main.cpp",
      "old_content": "    return 0;
}",
      "new_content": "    printf("F' is running!
");
    return 0;
}"
    }
    ```
*   **Execution Logic:** 
    1. Triggers User Confirmation UI.
    2. If approved, reads file, performs `content.replace(old_content, new_content)`. 
    3. Fails if `old_content` is not found exactly once.
*   **Returns to AI:** Success string ("File updated successfully") or error string ("Error: old_content not found. Check indentation and line breaks.").

### 3.4. `list_directory`
Returns the structural contents of a directory to help the AI navigate the project.

*   **Arguments:**
    *   `path` (string, required): Path to the directory (use "." for root).
*   **Example Request:**
    ```json
    {
      "tool_name": "list_directory",
      "path": "Components/"
    }
    ```
*   **Returns to AI:** A tree-like or list representation of the files and folders.