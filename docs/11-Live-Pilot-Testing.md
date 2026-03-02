# Live Pilot Testing (Headless Missions)

Mission Control supports **Headless Missions**, allowing developers to verify AI prompts against a real local Ollama instance without manual interaction. This system uses the **Textual Pilot** to simulate user input and monitor the autonomous ReAct loop.

---

## 🚀 Why Use Live Pilot?
- **Reality Testing:** Verify how a specific LLM (e.g., Qwen3, GLM4) handles F' command syntax.
- **Interception Checks:** Confirm the `CommandGuard` catches real-world hallucinations.
- **Autonomous Validation:** Ensure the AI correctly recovers from environmental errors (directory confusion, missing build cache).

---

## 🛠 How to Run a Live Mission

A template script is provided in `scripts/live_test.py`.

### 1. Configure the Script
Update the `pilot.press` line with the prompt you wish to test:
```python
await pilot.press(*"Create a new component called TempSensor")
```

### 2. Execute
Run the script using the project's virtual environment:
```bash
PYTHONPATH=. ./venv/bin/python3 scripts/live_test.py
```

### 3. Analyze Flight Logs
The script will output the full `chat_history`. Look for:
- **`[SYNTAX ERROR]`**: Indicates the `CommandGuard` intercepted a bad call.
- **`[Step N: ...]`**: Indicates tool execution progress.
- **`RECOVERY HINT`**: Indicates the system provided a diagnostic clue to the AI.

---

## 🧪 Automated Scenarios
For permanent, deterministic tests that use **Mocks** (to verify TUI logic), see:
- `tests/test_autonomous_scenarios.py`: Verifies the state machine and guards.
- `tests/headless_mission_demo.py`: A reusable template for mocked missions.

---

## ⚠️ Requirements
- A running Ollama instance on `localhost:11434`.
- The model defined in `TUI/fprime_ai_client.py` (default: `glm-4.7-flash:latest`) must be pulled.
