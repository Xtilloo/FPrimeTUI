# <img src="FPrimeLogo.png" alt="F' Logo" width="100"/> F-Prime-TUI (Mission Control)

A high-performance, asynchronous Terminal User Interface (TUI) for NASA F' (F Prime) v4.0 development. 

Mission Control serves as a direct "co-pilot" residing in your terminal. Powered by a local LLM via Ollama, it operates as an **Autonomous Agent** capable of translating natural language requests into concrete actions. It can dynamically discover your F' environment, read codebase files, execute standard `fprime-util` commands, and safely propose code modifications through a Human-in-the-Loop (HITL) approval system—all while adhering to strict flight software safety and coding standards.

## Features
- **Local-First AI:** Powered by `qwen3:8b` via Ollama for offline capability and zero data exfiltration.
- **Autonomous Tool Calling:** The AI can traverse directories, read files, and edit code safely.
- **Human-in-the-Loop:** All destructive actions (like editing files) pause the agent and require explicit user approval inline.
- **Fast-Path Commands:** Bypass the AI entirely to run standard build commands via `/build`, `/info`, etc.
- **Contextual Autocomplete:** Dynamically suggests files (`@filename`) and commands (`/`) based on your current project directory.

## Directory Structure
- **TUI/**: Core UI logic, async subprocess handlers, tool execution, and the AI ReAct loop client.
- **docs/**: Architectural design docs, software implementation details, F' conventions, and Ollama installation guides.
- **Makefile**: Automation for installation, testing, and global aliasing.
- **fprime-tui**: The main bash entry point script that handles working directory context mapping.

## Installation & Setup
1. **Prerequisites**: Ensure you have Python 3.9+ and [Ollama](https://ollama.com/) installed with the `qwen3:8b` model pulled (`ollama pull qwen3:8b`). 
   *For detailed instructions on setting up Ollama, please refer to the [Ollama Installation Guide](docs/Ollama_install.md).*
2. **Setup**:
   ```bash
   make install
   ```
3. **Global Access (Optional)**:
   To run `fprime-tui` from anywhere in your terminal, regardless of what F' project you are in:
   ```bash
   make alias
   ```

## Quick Start
Navigate to your F' project directory and launch the TUI:
```bash
cd /path/to/your/FPrimeProject
fprime-tui
```

### Example Usage
*   **Run a build:** `/build`
*   **Ask a question about a file:** `What does @settings.ini say?`
*   **Request an edit:** `Can you change the default toolchain in settings.ini to arm-linux?` (Will prompt for approval before executing).

## Development Utilities (Makefile)
The project includes a `Makefile` with several helpful commands for development and maintenance:

*   `make install`: Creates a python virtual environment and installs all dependencies from `requirements.txt`.
*   `make TUI`: Launches the application directly (useful for testing without the global alias).
*   `make alias`: Symlinks the launch script to `/usr/local/bin` for global terminal access.
*   `make test`: Runs python compilation checks and import validation across all files in the `TUI/` directory.
*   `make clean`: Recursively removes `__pycache__` directories and compiled `.pyc` files from the project.
*   `make help`: Lists all available commands with descriptions.