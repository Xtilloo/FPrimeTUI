# F-Prime Mission Control Tests

This directory contains a comprehensive, deterministic test suite for the Mission Control TUI. The suite is designed to run without a live Ollama instance or a full F' installation.

## Test Categories

### 1. UI Pilot Tests (`test_app.py`, `test_input.py`, `test_cancellation.py`)
- **Strategy**: Uses Textual's `run_test()` pilot to simulate keyboard and mouse events.
- **Verification**: Asserts UI state, chat history content, and widget visibility.

### 2. Autonomous Scenarios (`test_autonomous_scenarios.py`, `test_smart_command_controller.py`)
- **Strategy**: Replays multi-step AI tool chains (e.g., a "Create Component" mission).
- **Verification**: Ensures the TUI correctly transitions through autonomous states, handles recovery, and reaches the goal.

### 3. Controller Logic (`test_ai_handler.py`, `test_command_guard.py`, `test_mission_controller.py`)
- **Strategy**: Unit tests for the specialized logic layers.
- **Verification**: Validates command repair logic, JSON parsing robustness, and failure hierarchy triggers.

### 4. Integration & Shell (`test_shell.py`, `test_tools.py`)
- **Strategy**: Mocks subprocess calls to verify environment discovery and tool execution.

### 5. Golden Files (`test_golden_files.py`)
- **Strategy**: Compares the final `chat_history` against reference Markdown files in `golden_files/`.
- **Goal**: Catches visual and formatting regressions in the conversational output.

## Running Tests
Run the entire suite via the Makefile:
```bash
make test
```

## Mocking Infrastructure
All tests that involve AI interactions use the `MockAIClient` (defined in `tests/test_helpers.py`). It uses an internal queue to feed predefined responses to the TUI, making UI tests 100% predictable and fast.
