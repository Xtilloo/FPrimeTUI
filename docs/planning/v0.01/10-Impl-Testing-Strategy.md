# Implementation Guide: Testing Strategy

## 1. Overview
Testing an autonomous agent is complex because the LLM is non-deterministic. To build a reliable tool, we must mock the LLM for unit tests and rely on isolated, dummy F' projects for integration tests.

## 2. Unit Testing (Pytest)
Unit tests should cover the deterministic parts of the application: Tool execution, JSON parsing, and environment discovery.

### 2.1. Testing the Tool API
Create a suite of tests that directly invoke the Python functions mapped to the tools without involving Ollama or Textual.

*   `test_find_venv()`: Mock a directory structure with and without `fprime-venv` and assert the correct path is returned.
*   `test_replace_in_file_success()`: Create a temporary text file, run `execute_replace_in_file`, and assert the file contents changed correctly.
*   `test_replace_in_file_not_found()`: Pass `old_content` that doesn't exist; assert it returns the specific error string.

### 2.2. Mocking Ollama
To test the ReAct loop logic, use `unittest.mock` to replace the `fprime_ai_client.py` network calls with predefined responses.

*   **Test Case:** Ensure a tool call loop breaks correctly.
    *   Mock Ollama to yield `{"tool_name": "read_file", "path": "test.txt"}`.
    *   Assert that the App controller intercepts this, calls the read file function, and formulates the correct context string to send *back* to the mock Ollama client.

## 3. Integration Testing
Integration tests ensure that the Textual UI, the Subprocess manager, and the F' build system communicate correctly.

### 3.1. The Dummy F' Project
Create a minimal, valid F' project inside a `tests/fixtures/dummy_project` directory. It should contain a valid `fprime-venv` (or a mocked shell script that behaves like one).

### 3.2. Textual UI Testing
Textual provides a `Pilot` API specifically for testing TUIs asynchronously.

```python
async def test_fast_path_command():
    app = MissionControl()
    async with app.run_test() as pilot:
        # Simulate typing a command
        await pilot.press("/", "b", "u", "i", "l", "d", "enter")
        
        # Wait for background workers to finish
        await pilot.pause() 
        
        # Assert the chat log contains the expected output
        chat_log = app.query_one("#chat-log", RichLog)
        assert "fprime-util build" in chat_log.lines[0]
```

## 4. Continuous Integration (CI)
Since F' compilation requires specific system dependencies, running full integration tests in CI (like GitHub Actions) will require a Docker container pre-configured with F', Python, and `fprime-util`. 

**Phase 1 CI:** Focus purely on Python unit tests and Textual Pilot tests using mocked shell commands.
**Phase 2 CI:** Introduce the F' Docker container to run actual `run_fprime_command` end-to-end tests.