# F-Prime-TUI (Mission Control)

A high-performance, asynchronous Terminal User Interface (TUI) for NASA F' (F Prime) v4.0 development, featuring local AI assistance via Ollama.

## Directory Structure
This entire repository is designed to be a standalone, "drop-in" module for F' projects.
- **TUI/**: Core UI logic, AI client, and custom widgets.
- **Ollama/**: Documentation and setup scripts for the local LLM.
- **Makefile**: Automation for installation, launching, and global aliasing.
- **fprime-tui**: The main entry point script.
- **requirements.txt**: Python dependencies.

## Installation & Setup
1. **Prerequisites**: Ensure you have Python 3.9+ and [Ollama](https://ollama.com/) installed with the `qwen3:8b` model pulled (`ollama pull qwen3:8b`).
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
Launch the TUI directly from the repository:
```bash
./fprime-tui
```
Or if you've created the alias:
```bash
fprime-tui
```

## Integration as a Module
To use this in an existing F' project, copy this directory into your project's `tools/` folder (or similar).
```bash
cp -r /path/to/FPrimeTUI/ /path/to/your/project/tools/fprime-tui
```
The TUI will automatically detect the context of the F' project it is running within.
