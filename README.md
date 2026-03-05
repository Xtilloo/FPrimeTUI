# <img src="FPrimeLogo.png" alt="F' Logo" width="100"/> F-Prime-TUI (Mission Control)

A high-performance, asynchronous Terminal User Interface (TUI) for NASA F' (F Prime) v4.0 development. 

Mission Control serves as a direct "co-pilot" residing in your terminal. Powered by a local LLM via Ollama, it operates as an **Autonomous Agent** capable of translating natural language requests into concrete actions. It can dynamically discover your F' environment, read codebase files, execute standard `fprime-util` commands, and safely propose code modifications through a Human-in-the-Loop (HITL) approval system—all while adhering to strict flight software safety and coding standards.

## Key Features
- **Dual-Mode Operation:** 
    - **F' Academy (Learning Mode):** The default educational state. AI acts as a patient instructor, restricted to read-only tools and concept explanations. Perfect for onboarding.
    - **Mission Control (Dev Mode):** The full engineering state. Enables all tools, including build, generate, and file modification. Optimized for senior flight software engineers.
- **Local-First AI:** Optimized for `qwen3:8b` via Ollama for speed and accuracy.
- **Autonomous Tool Calling:** The AI traversed directories, reads files, and performs multi-step tasks (e.g., creating a component from scratch).
- **Command Guard & Automated Repair:** Real-time interception and self-correction of malformed F' syntax before execution.
- **Human-in-the-Loop (HITL):** All destructive actions (like editing files) pause the agent and require explicit user approval (`1: Approve`, `2: Decline`) inline.
- **GDS Support:** Integrated `fprime-cli` capabilities for monitoring telemetry and events.
- **Fast-Path Commands:** Bypass the AI entirely to run standard build commands via `/build`, `/info`, etc.

## 📂 Directory Structure
- **TUI/**: Modular package-aware TUI architecture.
    - **controllers/**: Specialized logic for autonomous operation (AI, Mission, and Command Guard).
- **docs/**: Architectural design docs, software implementation details, and F' conventions.
- **tests/**: Comprehensive suite of 60+ tests including deterministic UI pilots and regression scenarios.
- **Makefile**: Automation for installation, testing, and global aliasing.
- **fprime-tui**: The main bash entry point script.

## 🛠️ Installation & Setup
1. **Prerequisites**: Ensure you have Python 3.9+ and [Ollama](https://ollama.com/) installed.
2. **Setup**:
   ```bash
   make install
   ```
3. **Global Access (Optional, but recommended)**:
   ```bash
   make alias
   ```

## Quick Start
Launch the TUI from your F' project directory:
```bash
fprime-tui
```

### Switching Modes
*   **Check mode:** `/mode`
*   **Switch to Dev:** `/mode dev`
*   **Switch to Academy:** `/mode academy`

### Example Interaction
*   **Academy:** `Explain what a Port is in F'.`
*   **Mission Control:** `Create an active component named GpsHandler in the Drv namespace.` (AI will guide you through the process).

## Testing
The project uses `pytest` for comprehensive validation:
```bash
make test
```
All core workflows, including mode switching and autonomous recovery, are verified.
