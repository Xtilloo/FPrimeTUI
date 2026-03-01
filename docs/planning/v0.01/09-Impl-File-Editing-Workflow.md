# Implementation Guide: File Editing Workflow

## 1. Goal
Implement the `read_file` and `replace_in_file` tools, including the critical Human-In-The-Loop (HITL) confirmation modal using Textual.

## 2. Step-by-Step Implementation

### Step 1: File Tools (`TUI/tools.py`)
Implement the core file manipulation logic. Use `aiofiles` to prevent blocking the async loop.

```python
import aiofiles
import os

async def execute_read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"Error: File {path} not found."
    
    try:
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
            # Truncation logic goes here if file is too large
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

async def execute_replace_in_file(path: str, old_content: str, new_content: str) -> str:
    if not os.path.exists(path):
        return f"Error: File {path} not found."
        
    async with aiofiles.open(path, mode='r') as f:
        content = await f.read()
        
    if old_content not in content:
        return "Error: Exact match for 'old_content' not found."
    if content.count(old_content) > 1:
        return "Error: 'old_content' matched multiple times. Provide more context."
        
    updated_content = content.replace(old_content, new_content)
    
    async with aiofiles.open(path, mode='w') as f:
        await f.write(updated_content)
        
    return "File updated successfully."
```

### Step 2: The Confirmation Modal (`TUI/widgets.py`)
Create a Textual `ModalScreen` that pauses the application and waits for user input.

```python
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Static
from rich.syntax import Syntax

class ConfirmEditModal(ModalScreen[bool]):
    def __init__(self, path: str, old_str: str, new_str: str):
        super().__init__()
        self.path = path
        self.old_str = old_str
        self.new_str = new_str

    def compose(self) -> ComposeResult:
        yield Static(f"AI wants to modify {self.path}")
        # Use rich.syntax or a diff generator here to show changes
        yield Static(f"Old:
{self.old_str}

New:
{self.new_str}")
        yield Button("Approve", variant="success", id="approve")
        yield Button("Reject", variant="error", id="reject")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve":
            self.dismiss(True)
        else:
            self.dismiss(False)
```

### Step 3: Wiring the ReAct Loop (`TUI/app.py`)
When the JSON parser detects a `replace_in_file` command, pause the loop and show the modal.

```python
    async def handle_tool_call(self, tool_json: dict):
        tool_name = tool_json.get("tool_name")
        
        if tool_name == "replace_in_file":
            # 1. Suspend AI execution
            # 2. Push the modal and WAIT for the result
            approved = await self.push_screen_wait(
                ConfirmEditModal(
                    tool_json["path"], 
                    tool_json["old_content"], 
                    tool_json["new_content"]
                )
            )
            
            if approved:
                result = await execute_replace_in_file(...)
                # Send 'result' back to AI
            else:
                # Send rejection back to AI
                self.send_system_feedback("User rejected the edit.")
```