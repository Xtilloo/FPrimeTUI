# Implementation Guide: Command Execution Workflow

## 1. Goal
Implement the foundational ability for the TUI to discover the F' environment and execute commands both directly (via `/`) and autonomously via the AI.

## 2. Step-by-Step Implementation

### Step 1: Venv Discovery (`TUI/utils.py`)
Create a utility function to locate the virtual environment.
```python
import os
from pathlib import Path

def find_fprime_venv(start_path: Path = Path.cwd()) -> Path | None:
    current = start_path
    while current != current.parent:
        potential_venv = current / "fprime-venv"
        if potential_venv.is_dir() and (potential_venv / "bin" / "activate").exists():
            return potential_venv
        current = current.parent
    return None
```

### Step 2: Asynchronous Subprocess Runner (`TUI/shell.py`)
Create a robust asynchronous runner that yields output lines.
```python
import asyncio

async def run_fprime_command(venv_path: Path, command: str, args: str = "") -> dict:
    activation_cmd = f"source {venv_path}/bin/activate"
    full_cmd = f"{activation_cmd} && fprime-util {command} {args}"
    
    process = await asyncio.create_subprocess_shell(
        full_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        executable='/bin/bash' # Crucial for 'source' to work
    )

    stdout_data, stderr_data = await process.communicate()
    
    return {
        "exit_code": process.returncode,
        "stdout": stdout_data.decode().strip(),
        "stderr": stderr_data.decode().strip()
    }
```
*Note: For live streaming to the UI during long builds, `communicate()` is insufficient. You will need to use an `async for line in process.stdout:` loop and use Textual's messaging system to update the UI line-by-line.*

### Step 3: Fast-Path Routing (`TUI/app.py`)
Modify the input handler in Textual.
```python
from textual import work

class MissionControl(App):
    # ...
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value
        if user_text.startswith("/"):
            command = user_text[1:].strip()
            self.run_direct_command(command)
        else:
            self.send_to_ai(user_text)

    @work(exclusive=True)
    async def run_direct_command(self, command: str):
        # Update UI to show command is running
        self.chat_log.write(f"> fprime-util {command}")
        
        venv = find_fprime_venv()
        if not venv:
            self.chat_log.write("Error: fprime-venv not found.")
            return

        result = await run_fprime_command(venv, command)
        
        # Output results to UI
        if result['stdout']: self.chat_log.write(result['stdout'])
        if result['stderr']: self.chat_log.write(result['stderr'], style="red")
```

### Step 4: AI Tool Dispatcher
When the AI returns a JSON string, route it to the same `run_fprime_command` function, capture the returned dict, convert it to a string, and append it as a new "user" message (acting as the system) back into the `fprime_ai_client` chat history.