# Controllers: The Brain of Mission Control v2

Version 2 of Mission Control introduces a modular controller architecture to manage the complexity of autonomous flight software engineering. This document details the three core controllers that form the "Brain".

## 1. AI Handler (`ai_handler.py`)
The `AIHandler` is responsible for the interaction loop between the TUI and the Ollama LLM.

*   **Streaming Management:** It handles the asynchronous token stream, ensuring the TUI remains responsive.
*   **Robust Tool Parsing:** It uses specialized regular expressions to extract JSON tool calls from the AI's Markdown response. It is designed to handle both standard ```json blocks and "naked" JSON strings that models sometimes emit.
*   **Stateful History:** It synchronizes the conversational history between the Textual UI widgets and the LLM client.

## 2. Command Guard (`command_guard.py`)
The `CommandGuard` acts as a safety firewall and an optimization engine.

*   **Validation:** It verifies that the AI's requested command matches the `COMMAND_REGISTRY` and that the environment is ready (e.g., preventing a `build` if no build cache exists).
*   **Automated Repair:** This is the most powerful feature of v2. It proactively fixes common LLM hallucinations before execution:
    *   `fpp-generate` -> `fprime-util new`
    *   `fprime-util create` -> `fprime-util new`
    *   **CWD Correction:** If the AI attempts to run a command in the wrong directory, the Guard automatically redirects it to the discovered project root.

## 3. Mission Controller (`mission.py`)
The `MissionController` manages the autonomous lifecycle and ensures the agent does not get stuck in infinite failure loops.

*   **Failure Tracking:** It monitors consecutive tool failures.
*   **Recovery Hierarchy (Fair Process):**
    1.  **Tier 1 (Help):** On the first failure, it directs the AI to run a specific `--help` command.
    2.  **Tier 2 (Docs):** On the second failure, it mandates a `grep_docs` search to find official syntax in the project documentation.
    3.  **Tier 3 (Fatigue):** After three consecutive failures, it aborts the autonomous mission and prompts the user for intervention.
*   **Root Discovery:** It stores the `discovered_project_root` to allow other controllers to perform path corrections.

## Inter-Controller Communication
The controllers work in concert within the `_ai_loop` in `app.py`:
1.  `AIHandler` produces a tool request.
2.  `CommandGuard` repairs and validates the request.
3.  `app.py` executes the tool.
4.  `MissionController` analyzes the result and generates the next directive for the `AIHandler`.
