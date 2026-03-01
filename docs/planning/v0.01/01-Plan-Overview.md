# Plan: Overview and Vision

## 1. Executive Summary
The F-Prime-TUI (Mission Control) project aims to revolutionize the development experience for NASA's F' (F Prime) flight software framework. F' is powerful but comes with a steep learning curve, extensive boilerplate generation, and complex build system interactions. Mission Control mitigates these friction points by wrapping the F' development environment in a Terminal User Interface (TUI) powered by a local Large Language Model (LLM), such as Ollama. 

This document outlines the high-level vision, core problem statement, and guiding principles for building a lightweight, modular, and scalable AI assistant specifically tuned for F' engineering.

## 2. Problem Statement
Developing flight software with F' involves several challenges:
*   **Boilerplate Complexity:** Creating new components, ports, and topologies requires generating and wiring multiple XML/FPP dictionaries and C++ implementation files.
*   **Context Switching:** Developers frequently switch between writing code, running `fprime-util` commands, checking logs, and reading documentation.
*   **Steep Learning Curve:** New engineers spend significant time understanding the prescriptive architecture of F' (e.g., Active vs. Passive components, synchronous vs. asynchronous ports).

## 3. The Solution: Mission Control
Mission Control serves as a "co-pilot" residing directly in the developer's terminal. By operating from within an F' project directory, it gains contextual awareness of the codebase. 

Instead of acting as a simple chatbot, Mission Control operates as an **Autonomous Agent**. It translates natural language requests into concrete actions, executing shell commands, reading file contents, and proposing code changes—all while maintaining the strict safety and coding standards required by flight software.

## 4. Guiding Principles
To ensure the tool remains effective, reliable, and maintainable, development is guided by three core principles:

### 4.1. Lightweight
*   **Local First:** Relying on local LLMs (like `qwen3:8b` via Ollama) ensures offline capability, zero data exfiltration (crucial for proprietary flight software), and low latency.
*   **Minimal Footprint:** The TUI framework (Textual) is fast and requires minimal system resources. It should not slow down the host machine's compilation times.
*   **Frictionless Setup:** The tool should be trivial to install (e.g., via `pipx` or a simple install script), minimize system-level dependencies, and be fully compatible with Linux (Ubuntu, Arch, etc.), macOS, and Windows Subsystem for Linux (WSL).

### 4.2. Modular
*   **Separation of Concerns:** The system is strictly divided into the UI layer (Textual), the AI Client layer (Ollama wrapper), and the Tool Execution layer (Subprocess management).
*   **Tool-Based Interaction:** The LLM does not have raw access to the system. It can only request the execution of predefined "Tools" (e.g., `read_file`, `run_command`). New capabilities can be added by simply registering a new tool and updating the system prompt.

### 4.3. Scalable
*   **Project Agnostic:** The TUI must not be hardcoded to a specific F' project's layout. It must dynamically discover the project root and the `fprime-venv`.
*   **Iterative Complexity:** We begin with basic command execution and file reading. The architecture must easily scale to support complex tasks like running unit tests, parsing test coverage reports, and automatically debugging compilation errors.

## 5. Success Criteria
The implementation of this planning phase will be considered successful when:
1.  A user can launch `fprime-tui` in an F' project.
2.  The user can ask the AI to "build the project" - using `fprime-util build`.
3.  The AI correctly interprets this, requests the `run_fprime_command` tool with the argument `build`.
4.  The TUI sources the `fprime-venv` and executes the build, streaming the output to the user.
5.  The AI analyzes the output and reports success or failure.