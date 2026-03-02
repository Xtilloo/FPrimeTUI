# Design: F-Prime-TUI Development Boosting Layer
**Date:** 2026-03-01  
**Status:** Approved  
**Topic:** Core development features, TUI fluency, and context supplementation.

## 1. Overview
The "Development Boosting" layer transforms Mission Control from a simple terminal interface into a senior-level co-pilot. It provides the AI with a deep understanding of F' internals (Knowledge Base) and common development patterns (Workflow Handbook) while maintaining user transparency through a "Flight Plan" execution loop.

## 2. Architecture: The Flight Controller
The system follows a **Plan-First Autonomous Chain** approach:
1. **Map Discovery (Anti-Bloat):** To prevent context window saturation, the AI is NOT given the full Master Index by default. Instead, it is told the file's location (`docs/fprime_master_index.md`) and must use `read_file` to consult the "Map" as needed.
2. **Environment Verification:** Before starting any multi-step mission, the AI MUST verify the build environment (e.g., using `run_fprime_command info`) to ensure the `venv` and project state are valid.
3. **Workflow SOPs:** AI references a "Handbook" with pre-defined JSON tool calls and success/failure criteria.
4. **Execution:** AI emits a "Flight Plan," then executes a sequence of tools with live status updates.

---

## 3. Knowledge Base Components

### 3.1 The Master Index (`docs/fprime_master_index.md`)
A structured, deep-dive lookup table for the F' core repository.
- **Goal:** Minimize context window usage while maximizing repo awareness.
- **Structure:** Category (Svc, Fw, etc.) -> Component/Port -> Key Files -> Role -> Usage Example.

**Example Entry:**
> **Svc/ActiveLogger**
> - **Files:** `Svc/ActiveLogger/ActiveLogger.fpp`, `Svc/ActiveLogger/ActiveLogger.cpp`
> - **Role:** Manages asynchronous logging of `Events`. It buffers logs and sends them to the Ground Interface.
> - **Usage:** Used in almost every deployment to capture component telemetry/errors.

### 3.2 The Workflow Handbook (`docs/workflow_handbook.md`)
A manual of "If-Then" logic and step-by-step procedures for the AI.
- **Goal:** Ensure the AI uses the correct tool sequence and **Correct CWD** for complex F' tasks.
- **Content:** Summary (1-2 sentences) + JSON Snippets for each step.

#### Directory Scope Rules (The "North Star")
All `fprime-util` commands are **CWD-Sensitive**. The AI MUST set the `cwd` field correctly.

| Command | Target Scope | Required `cwd` | Why? |
| :--- | :--- | :--- | :--- |
| `generate` | Project/Deployment | Project Root or Deployment Folder | Maps the entire build graph. |
| `build` | Full Binary | Deployment Folder | Compiles the deployment executable. |
| `build` | Component | Component Folder | Compiles ONLY the specific component. |
| `impl` | C++ Stubs | Component Folder (w/ .fpp) | Infers component from the local directory. |
| `check` | Unit Tests | Component Folder | Locates `-Tester` files locally. |
| `visualize`| FPP Model | Folder w/ .fpp | Parses the local model graph. |

#### Mission Abort Criteria
To prevent "The Loop of Death":
1. **Redundancy Check:** If a `build` fails twice with the same error after a `purge`, do NOT attempt a third build. 
2. **Graceful Exit:** Summarize the compiler output, identify the likely file/line, and ask the User for manual intervention.

**Example Workflow: The "Clean Build & Sync" Workflow**
> **Summary:** Use this workflow when CMake is out of sync or the build environment is corrupted. It removes existing build caches, regenerates them, and attempts a fresh compile.
>
> **Step 1: Purge Cache**
> ```json
> {"tool_name": "run_fprime_command", "command": "purge", "cwd": "."}
> ```
> **Step 2: Generate Cache**
> ```json
> {"tool_name": "run_fprime_command", "command": "generate", "cwd": "."}
> ```
> **Step 3: Build Project**
> ```json
> {"tool_name": "run_fprime_command", "command": "build", "cwd": "<target_deployment_or_component_dir>"}
> ```

---

## 4. TUI Fluency & The Flight Plan Loop

### 4.1 Plan Emission
Before starting any multi-step task, the AI MUST output a "Flight Plan" block:
```markdown
### FLIGHT PLAN
1. [Step 1 Summary]
2. [Step 2 Summary]
...
```

### 4.2 Autonomous Execution
- The TUI detects the "Flight Plan" and displays it as a header.
- The AI proceeds with tool calls. The TUI provides live status: `> [Step N/M: Action Name...]`.
- **HITL Rule:** For any file system modification (`replace_in_file`), the TUI MUST pause for user approval (1: Approve, 2: Decline).

### 4.3 Graceful Failure
If a workflow fails at a fundamental level:
1. AI stops the autonomous chain.
2. AI summarizes the root cause (e.g., "Dependency cycle in `Topology.fpp`").
3. AI directs the developer to the specific file/line for manual intervention.

---

## 5. Implementation Roadmap
1. **Master Index:** Draft the comprehensive F' core mapping.
2. **Workflow Handbook:** Define the SOPs for Build, TDD, and Niche Error Recovery.
3. **Flight Plan Loop:** Update `TUI/app.py` and `fprime_ai_client.py` to handle planning and live status.
4. **Validation:** Verify using a dummy F' project and the `MockAIClient` suite.
