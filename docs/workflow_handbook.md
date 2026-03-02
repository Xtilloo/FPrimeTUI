# F' Workflow Handbook
**Goal:** Ensure the AI assistant uses the correct tool sequence and Correct CWD for complex F' tasks.
**Usage:** Follow these "If-Then" SOPs when performing development tasks.

---

## 1. Directory Scope Rules (The "North Star")
All `fprime-util` commands are **CWD-Sensitive**. The AI MUST set the `cwd` field correctly.

| Command | Target Scope | Required `cwd` | Why? |
| :--- | :--- | :--- | :--- |
| `generate` | Project/Deployment | Project Root or Deployment Folder | **Creates CMake build cache.** Setup required BEFORE any build or check. |
| `build` | Full Binary | Deployment Folder | Compiles the deployment executable. |
| `build` | Component | Component Folder | Compiles ONLY the specific component. |
| `impl` | C++ Stubs | Component Folder (w/ .fpp) | **Generates C++ code stubs** from .fpp models (Autocoder). |
| `check` | Unit Tests | Component Folder | Locates `-Tester` files locally and runs them. |

---

## 2. Standard SOPs

### 2.0 Discovery SOP (When unsure)
**Summary:** If a command fails or its arguments are unclear, use the built-in help.
- **Step 1: Get Help**
  ```json
  {"tool_name": "run_fprime_command", "command": "generate", "args": "--help", "cwd": "."}
  ```

### 2.1 Standard Build Workflow
**Summary:** Build the current component or deployment.
- **Step 1: Build**
  ```json
  {"tool_name": "run_fprime_command", "command": "build", "cwd": "<current_dir>"}
  ```

### 2.2 TDD Workflow (Unit Testing)
**Summary:** Generate and run unit tests for a component.
- **Step 1: Generate UT Cache**
  ```json
  {"tool_name": "run_fprime_command", "command": "generate --ut", "cwd": "<component_dir>"}
  ```
- **Step 2: Build UTs**
  ```json
  {"tool_name": "run_fprime_command", "command": "build --ut", "cwd": "<component_dir>"}
  ```
- **Step 3: Run UTs**
  ```json
  {"tool_name": "run_fprime_command", "command": "check", "cwd": "<component_dir>"}
  ```

### 2.3 Component Creation Workflow
**Summary:** Create a new component and generate initial stubs.
- **Step 1: Create Component**
  ```json
  {"tool_name": "run_fprime_command", "command": "new --component", "cwd": "<components_dir>"}
  ```
- **Step 2: Generate Implementation Stubs**
  ```json
  {"tool_name": "run_fprime_command", "command": "impl", "cwd": "<new_component_dir>"}
  ```

### 2.4 Clean Build & Sync (Error Recovery)
**Summary:** Use this when CMake is out of sync or the build environment is corrupted.
- **Step 1: Purge Cache**
  ```json
  {"tool_name": "run_fprime_command", "command": "purge", "cwd": "."}
  ```
- **Step 2: Generate Cache**
  ```json
  {"tool_name": "run_fprime_command", "command": "generate", "cwd": "."}
  ```
- **Step 3: Build Project**
  ```json
  {"tool_name": "run_fprime_command", "command": "build", "cwd": "."}
  ```

## 3. Mission Abort & Auto-Recovery
To prevent "The Loop of Death" and ensure command fluency:

### 3.1 Mandatory Auto-Recovery
If any `fprime-util` command fails (Exit code != 0):
1. **IMMEDIATE ACTION:** Run the failing command with `--help` (e.g. `fprime-util generate --help`).
2. **ANALYSIS:** Read the help output to identify missing flags, incorrect paths, or positional arguments.
3. **RETRY:** Re-attempt the command with corrected parameters.

### 3.2 Mission Abort Criteria
1. **Redundancy Check:** If a `build` fails twice with the same error after a `purge`, do NOT attempt a third build.
2. **Graceful Exit:** Summarize the compiler output, identify the likely file/line, and ask the User for manual intervention.
