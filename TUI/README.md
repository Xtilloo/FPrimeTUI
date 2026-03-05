# TUI Package

The `TUI/` directory contains the core application logic for the F-Prime Mission Control TUI. It is structured as a modular Python package.

## Core Architecture
- **`app.py`**: The central application class (`FPrimeTUI`). Manages the Textual event loop, UI layout, and the main AI/Tool orchestration loop.
- **`fprime_ai_client.py`**: Asynchronous interface to local LLMs (via Ollama). Handles system prompts, chat history, and token usage tracking.
- **`command_definitions.py`**: The Single Source of Truth for:
    - `TUIMode` (Academy vs. Mission Control).
    - `CommandMetadata` (Slash command registry and permissions).
    - `COMMAND_REGISTRY` (F' utility argument rules and preflight checks).
    - `ERROR_FINGERPRINTS` (Regex-based recovery hints).
- **`shell.py`**: The execution engine for F' utilities. Manages subprocesses, virtual environments, and process group cancellation.
- **`tools.py`**: Implementations for autonomous tools (read, write, list, grep).
- **`widgets.py`**: Custom Textual widgets like the `FadingScrollContainer`.
- **`utils.py`**: Utility functions for environment discovery and UI formatting.

## Important Implementation Note: Imports
To ensure the TUI can be launched from any directory via the `fprime-tui` wrapper script, all internal package imports **MUST** use the absolute `TUI.` prefix:

```python
# CORRECT
from TUI.utils import find_fprime_venv

# INCORRECT (will fail when run as a module)
from utils import find_fprime_venv
```

## CSS Styling
Styling is managed via `style.tcss`, following the **JPL Mars Theme**. It uses space-themed colors and specific selectors for Markdown elements to ensure visual consistency.
