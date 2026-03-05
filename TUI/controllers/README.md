# TUI Controllers

The `controllers/` directory houses the logic layer responsible for autonomous intelligence, command safety, and mission state management.

## Components

### 1. AI Handler (`ai_handler.py`)
- **Responsibility**: Manages the high-level interaction loop between the TUI and the AI Client.
- **Capabilities**:
    - Robust parsing of JSON tool calls from streaming text.
    - Maintains the separation between "conversational" response and "structured" tool request.

### 2. Command Guard (`command_guard.py`)
- **Responsibility**: Ensures safety and correctness of all commands before they reach the shell.
- **Capabilities**:
    - **Validation**: Rejects hallucinated executables or known-bad syntax.
    - **Repair**: Automatically fixes common AI errors (e.g., converting `fpp-generate` to `fprime-util new`).
    - **CWD Correction**: Adjusts the current working directory if the AI is trying to run a command from the wrong folder.

### 3. Mission Controller (`mission.py`)
- **Responsibility**: Tracks the overall state of an autonomous task ("The Mission").
- **Capabilities**:
    - **Failure Tracking**: Monitors consecutive tool failures.
    - **Recovery Hierarchy**: Emits specific directives to the AI when a command fails (e.g., "Run --help", then "Search docs", then "Stop").
    - **State Management**: Maintains a persistent state object for the duration of a user request.
