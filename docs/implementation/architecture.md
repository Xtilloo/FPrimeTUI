# System Architecture (Mission Control v2)

Mission Control uses a decoupled, modular architecture to maintain a responsive User Interface while securely executing shell commands and querying a local LLM. Version 2 modularizes the "Brain" into specialized controllers to handle reasoning, safety, and mission state independently.

## High-Level Architecture

The system is divided into three primary layers:
1.  **The UI & Orchestrator (Textual):** The user-facing terminal (`app.py`).
2.  **The Brain (Controllers):** The logic layer that manages AI interaction and safety.
3.  **The Hands (Tools & Shell):** The file system and F' environment interactors.

### 1. The UI Layer (`app.py`)
Built on the **Textual** framework, the UI runs its own asynchronous event loop. 
*   **Non-Blocking:** All heavy computations (AI streaming, tool execution) are pushed to background `@work` routines.
*   **Routing:** Directs slash commands (`/`) to the execution layer and natural language to the Brain.
*   **State Management:** Maintains the visual chat history and input focus.

### 2. The Brain Layer (`TUI/controllers/`)
Mission Control v2 introduces specialized controllers to manage the agent's autonomy:
*   **AI Handler (`ai_handler.py`):** Manages the streaming interaction loop with Ollama. It handles token-by-token parsing and robust tool extraction from the AI's response.
*   **Command Guard (`command_guard.py`):** A safety firewall. It intercepts tool calls before execution to validate F' syntax. Crucially, it implements a **Repair System** that auto-corrects common hallucinations (e.g., changing `fpp-generate` to `fprime-util new`) before they reach the shell.
*   **Mission Controller (`mission.py`):** Manages the "Flight Plan" lifecycle. It tracks consecutive failures and implements a **Recovery Hierarchy** (Help -> Docs -> Fatigue) to guide the AI back to success without human intervention.

### 3. The Execution Layer (`tools.py`, `shell.py`)
*   **Environment discovery:** `shell.py` uses `check_environment` to find `fprime-venv` and the project root (`settings.ini`).
*   **Safe Execution:** Uses `asyncio.subprocess` to execute F' utilities within the correctly activated virtual environment.
*   **Asynchronous I/O:** Uses `aiofiles` for non-blocking file reads and surgical edits.

## The v2 Reasoning Flow

1. **User Request:** User asks: *"Create a component"*
2. **AI Reasoning:** `ai_handler` streams tokens from Ollama.
3. **Interception & Repair:** `app.py` passes the tool request to `command_guard`.
4. **Auto-Correction:** If the AI hallucinated `fpp-generate`, the Guard repairs it to `fprime-util new` and reports the fix to the user.
5. **Human-In-The-Loop:** If the tool modifies files, the UI pauses for user approval.
6. **Execution & Feedback:** The tool runs, and the result (success or error fingerprint) is fed back to the AI via the `mission_controller`'s recovery logic.
7. **Resolution:** The AI finalizes the task or escalates through the recovery hierarchy.
