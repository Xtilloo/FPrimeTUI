# <img src="FPrimeLogo.png" alt="F' Logo" width="100"/> F-Prime-TUI (Mission Control)

A high-performance, asynchronous Terminal User Interface (TUI) for NASA F' (F Prime) v4.0 development. 

Mission Control serves as a direct "co-pilot" residing in your terminal. Powered by a local LLM via Ollama, it operates as an **Autonomous Agent** capable of translating natural language requests into concrete actions. It can dynamically discover your F' environment, read codebase files, execute standard `fprime-util` commands, and safely propose code modifications through a Human-in-the-Loop (HITL) approval system—all while adhering to strict flight software safety and coding standards.

## Features (Mission Control v2)
- **Local-First AI:** Optimized for `glm-4.7-flash` or `qwen3:8b` via Ollama for speed and accuracy.
- **Command Guard:** Real-time interception of malformed F' syntax and hallucinated executables (e.g., `fpp-generate`).
- **Automated Repair:** Self-correcting AI turns that automatically fix common command hallucinations and pathing errors before execution.
- **GDS Support:** Integrated `fprime-cli` capabilities for monitoring telemetry, events, and sending commands via Ground Data System.
- **Autonomous Tool Calling:** The AI can traverse directories, read files, and edit code safely.
- **Human-in-the-Loop:** All destructive actions (like editing files) pause the agent and require explicit user approval inline.
- **Fast-Path Commands:** Bypass the AI entirely to run standard build commands via `/build`, `/info`, etc.
- **Contextual Autocomplete:** Dynamically suggests files (`@filename`) and commands (`/`) based on your current project directory.

## Directory Structure
- **TUI/**: Modular package-aware TUI architecture.
    - **controllers/**: Specialized logic for autonomous operation.
- **docs/**: Architectural design docs, software implementation details, F' conventions, and Ollama installation guides.
    - **[Implementation Deep-Dive](docs/implementation/index.md)**: Architecture, SDD, and design rationale.
- **tests/**: Comprehensive test suite including deterministic UI pilots and core regression tests.
- **Makefile**: Automation for installation, testing, and global aliasing.
- **fprime-tui**: The main bash entry point script that handles working directory context mapping.

## Installation & Setup
1. **Prerequisites**: Ensure you have Python 3.9+ and [Ollama](https://ollama.com/) installed.
2. **Setup**:
   ```bash
   make install
   ```
3. **Global Access (Optional)**:
   To run `fprime-tui` from anywhere in your terminal:
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
*   **GDS Telemetry:** `Show me the telemetry channels.` (AI uses `fprime-cli channels`).
*   **Request an edit:** `Can you change the default toolchain in settings.ini to arm-linux?` (Will prompt for approval before executing).

## Development Utilities (Makefile)
The project includes a `Makefile` with several helpful commands for development and maintenance:

*   `make install`: Creates a python virtual environment and installs all dependencies.
*   `make test`: Runs the full `pytest` suite, including TUI simulations and regression tests.
*   `make alias`: Symlinks the launch script to `/usr/local/bin` for global access.
*   `make clean`: Recursively removes cache and temporary artifacts.
*   `make help`: Lists all available commands with descriptions.