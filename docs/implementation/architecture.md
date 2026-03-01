# System Architecture

Mission Control uses a decoupled, layered architecture to maintain a responsive User Interface while securely executing shell commands and querying a local LLM.

## High-Level Architecture

The system is divided into three primary layers:
1.  **The UI & Orchestrator (Textual):** The user-facing terminal.
2.  **The Brain (AI Client):** The connection to the local reasoning engine (Ollama).
3.  **The Hands (Tools & Shell):** The file system and F' environment interactors.

### 1. The UI & Orchestrator (`app.py`)
Built on the **Textual** framework, the UI runs its own asynchronous event loop. 
*   All heavy computations (AI streaming, tool execution, subprocess generation) are pushed to background `@work` routines to prevent the UI from freezing.
*   It acts as the **Router**. User input starting with `/` (e.g., `/build`) is routed directly to the Shell layer. Natural language is routed to the Brain.
*   It acts as the **ReAct Loop Manager**. It parses responses from the AI, executes local tools, and recursively feeds the output back into the AI.

### 2. The Brain (`fprime_ai_client.py` & Ollama)
Mission Control uses a **Tool-Calling (Function-Calling) Architecture**. 
*   The AI (defaulting to `qwen3:8b`) has **zero direct access** to the computer. 
*   It is provided a strict system prompt containing a JSON schema for available tools (`read_file`, `replace_in_file`, etc.).
*   When it determines an action is needed, it stops generating conversational text and emits a JSON payload.

### 3. The Hands (`tools.py`, `shell.py`, `utils.py`)
The execution layer.
*   **Virtual Environment Discovery:** `utils.py` dynamically scans the directory tree to find `fprime-venv`, ensuring the system is strictly bound to the local F' project scope.
*   **Safe Execution:** `shell.py` uses `asyncio.subprocess` to spawn bash shells, activate the discovered venv, and run `fprime-util`.
*   **Asynchronous I/O:** `tools.py` uses `aiofiles` for all read/write operations so disk latency does not block the UI rendering thread.

## The ReAct (Reasoning and Acting) Loop Flow

1. **User Request:** User asks: *"Change settings.ini"*
2. **AI Reasoning:** The LLM processes the request and streams back `{"tool_name": "replace_in_file", ...}`.
3. **Interception:** `app.py` catches the JSON block and suspends the AI stream.
4. **Human-In-The-Loop:** The UI presents the requested change to the user inline.
5. **Execution:** If approved by the user, `tools.py` edits the file.
6. **Feedback Loop:** `app.py` sends `Tool Response: Success` back to the AI.
7. **Resolution:** The AI reads the success message and streams a final conversational confirmation to the user.