# F' Framework Commands & Tooling Context

This document contains reference material regarding the core utility commands used to build and manage F' (F Prime) framework projects.

## Environment & Tooling
*   **Virtual Environment:** Always activate the project-local venv before running commands:
    ```bash
    source fprime-venv/bin/activate
    ```
*   **Primary Build Cache:** `build-fprime-automatic-native`
*   **Unit Test Build Cache:** `build-fprime-automatic-native-ut`
*   **Component Creation:** Use `fprime-util new --component` to scaffold new modules.

---

## The `fprime-util` Command

`fprime-util` wraps the F' build system enabling developers to follow standard patterns. It translates between the developer's context (working directory and supplied flags) to the build system targets defined for that context. 

*Always run `fprime-util` commands from the directory you want to target.*

### Common Commands
*   `build`: Build F' components, deployments, and unit tests
*   `check`: Run F' unit tests with optional test coverage
*   `generate`: Generate build caches for the specified deployment
*   `purge`: Remove build caches for specified project
*   `impl`: Generate implementation templates (`.hpp-template`, `.cpp-template`)
*   `new`: Generate a new F' object (component, deployment, module)

### Examples
**Setup and Build on Default Platform**
```bash
cd Ref
fprime-util generate
fprime-util build
```

**Setup and Build Unit Tests**
```bash
cd Ref
fprime-util generate --ut
fprime-util build --ut
fprime-util check  # Runs UTs ('--ut' is implied)
```

**Build Everything in Project**
```bash
fprime-util build --all
```

---

## The `fprime-util new` Command

Runs a wizard (or accepts flags) to create new objects in F'.

### Targets
*   `--component`: Generate a new component. (Prompts for type and included features. Ends with an option to automatically add to build system and run impl generator).
*   `--deployment`: Generate a new F' deployment within a project. Expected to be run at the root of the project.
*   `--subtopology`: Generate a new subtopology.
*   `--module`: Generate a new module.

### Options
*   `--overwrite`: Generated files will overwrite existing ones.
*   `--no-venv`: Prevent updating the virtual environment during project creation.
*   `--force`: Override warning about creating a new deployment/component within an existing one.

---

### COMMAND REFERENCE (AI Guidance Map)
- **Intent:** Create a new component
  **Command:** `fprime-util new --component`
- **Intent:** Create a new deployment
  **Command:** `fprime-util new --deployment`
- **Intent:** Generate build cache
  **Command:** `fprime-util generate`
- **Intent:** Build component or project
  **Command:** `fprime-util build`
- **Intent:** Run unit tests
  **Command:** `fprime-util check`
- **Intent:** Generate implementation templates
  **Command:** `fprime-util impl`
- **Intent:** Purge build caches
  **Command:** `fprime-util purge`
- **Intent:** Visualize FPP model
  **Command:** `fprime-util visualize`