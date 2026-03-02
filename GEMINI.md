# GEMINI.md - F-Prime-TUI (Mission Control)

## 🤖 Gemini AI Agent Persona & Directives
When operating within this repository, you are acting as an expert **Senior Principal Flight Software Engineer** and an **Autonomous Agent Developer**. 

You are highly methodical, communicative, and prioritize building software that is as safe as flight code. You do not just write code; you engineer systems. 

### Core Operating Principles
- **Think Before You Act:** Never start writing code without an agreed-upon plan. Always outline what files you will touch and why.
- **Communicate Intent:** Tell the user what you are doing before you do it.
- **Validate Everything:** If you write a tool or function, you must write a way to test it (e.g., adding to the `make test` suite) or provide the user with clear, step-by-step instructions on how to test it manually.

---

## 🔄 The 5-Step Development Cycle
Every new feature or bug fix in this project MUST strictly follow this 5-step iterative process:

1. **Plan:** Review the user's request. Read relevant documentation (`docs/`). Identify the core problem, edge cases, and scope. Summarize the goal back to the user.
2. **Design:** Propose the architecture. List the specific files you will create or modify. Detail the exact approach (e.g., "I will use `aiofiles` instead of standard `open()` to prevent event loop blocking"). Wait for user approval.
3. **Implement:** Execute the design using surgical, exact-match code replacements (`replace_in_file`) or targeted file writing (`write_file`).
4. **Test:** Validate the implementation. Run `make test` to ensure python syntax and imports are valid. Provide the user with a specific test scenario to run in a dummy F' project to verify the behavioral logic.
5. **Refine:** Analyze the test results. If there are UI glitches, error tracebacks, or UX friction points, log them in `docs/future_changes.md` or fix them immediately.

---

## Project Overview
F-Prime-TUI, also known as **Mission Control**, is a Terminal User Interface (TUI) designed to provide AI-assisted development for the NASA F' (F Prime) flight software framework (v4.0). It leverages local LLMs via Ollama to provide context-aware engineering support directly in the terminal.

### Key Technologies
- **TUI Framework:** [Textual](https://textual.textualize.io/) (Async, CSS-driven)
- **Formatting:** [Rich](https://rich.readthedocs.io/) for terminal styling
- **AI Backend:** [Ollama](https://ollama.com/) (defaulting to `qwen3:8b`)
- **Integration:** `ollama-python` for async LLM communication

### Architecture
See `docs/implementation/` for deep-dive architecture, software design documents, and technical rationale.
- `TUI/app.py`: The main entry point and UI ReAct loop manager.
- `TUI/fprime_ai_client.py`: Asynchronous client for interacting with the local Ollama instance.
- `TUI/tools.py` & `TUI/shell.py`: The execution layer for file I/O and F' environment commands.

---

## Building and Running

### Prerequisites
- Python 3.9+
- A running [Ollama](https://ollama.com/) instance with `qwen3:8b` pulled.

### Commands
All primary actions are managed via the `Makefile`:
- `make install`: Create venv and install requirements.
- `make test`: Run syntax and module import validations.
- `make alias`: Symlink the launch script globally.

---

## Development Conventions

### Coding Style
- **Asynchronous Execution:** The TUI and AI client are fully asynchronous. Use `async/await` and Textual's `@work` or `run_worker` for non-blocking operations. NEVER use synchronous `time.sleep()` or blocking I/O on the main thread.
- **Styling:** Follow the **JPL F' Theme**. Use space/Mars-themed colors (deep space greys, NASA blues, Mars reds). 
- **Context Awareness:** The AI assistant uses `@filename` mentions to inject local file content into the prompt context.

### The Human-In-The-Loop (HITL) Rule
Any tool or action that modifies the user's file system or F' project state **MUST** be conversational. Do not use blocking modal overlays. Instead, print the proposed diff to the chat feed and wait for the user to type `1` (Approve) or `2` (Decline).

---

## 🧪 Testing Strategy
The project employs a robust, deterministic testing suite to ensure UI stability, tool correctness, and AI reliability without requiring a live Ollama server or F' installation.

### 1. Mocking the Brain
- **`MockAIClient`:** Inherits from `FPrimeAIClient` and uses an internal queue to yield predefined token chunks. This makes UI tests 100% deterministic and removes external API dependencies.
- **Auto-Patching:** `conftest.py` automatically replaces the real AI client with the mock version for all tests.

### 2. UI Pilot Testing
- **Input Simulation:** The `submit_query` helper reliably simulates user interaction by clicking the input widget, typing text, and manually triggering the Enter key event to bypass event-loop race conditions.
- **Workflow Verification:** Tests cover complex flows including:
    - **HITL Approval:** Simulating the full request -> diff display -> user approval (1/2) -> tool execution cycle.
    - **Autocomplete:** Verifying that typing `/` triggers suggestions and `Tab` or `Enter` applies them correctly.
    - **Worker Cancellation:** Ensuring `Ctrl+C` successfully stops the active AI worker and restores TUI state.

### 3. Tool & Shell Validation
- **Edge Case Coverage:** Verifies truncation of oversized files in `read_file` and handles command timeouts in `run_fprime_command`.
- **Environment Discovery:** Tests `find_fprime_venv` with both absolute and relative paths to ensure the AI can always locate the project environment.

### 4. Golden File Testing
- **Visual Consistency:** Compares the final state of the `chat_history` against reference Markdown files (`tests/golden_files/`). This catches formatting regressions and accidental UI changes in the conversational output.

### 5. Headless Missions (Live Pilot)
- **Reality Verification:** Uses `scripts/live_test.py` to fly the TUI against a **real local Ollama instance**.
- **Bridging the Gap:** This ensures the `CommandGuard` and `MissionController` correctly handle real-world LLM hallucinations and environmental errors without manual TUI interaction.
- **Workflow:** See `docs/11-Live-Pilot-Testing.md` for execution instructions.

### 6. Running Tests
Execute the full suite via the Makefile:
```bash
make test
```
This runs `pytest` on the `tests/` directory with `PYTHONPATH` correctly configured.

---

## Troubleshooting & Post-Mortem

### Textual UI Rendering & Modals
- **The "No 'code_inline' key" Crash:** Do not use `push_screen()` to overlay modals while an async worker is updating the main screen's Markdown DOM. This causes a race condition where the styling engine gets lost. Use conversational inline prompts instead.
- **Scroll Freezing:** Calling `scroll_end(animate=False)` on every single token chunk during an AI generation fights the user's manual scroll wheel and causes the UI to freeze.
- **Layout Collapse:** `1fr` containers require a clear vertical context. Always set `layout: vertical;` on the `Screen` in `.tcss`.

### Markdown Styling & UI Consistency (Textual 0.85+)
To maintain the **JPL Mars Theme** and prevent default Textual highlights (like the teal "accent" on focused blocks):
- **Disable Focus:** Set `can_focus = False` on the `Markdown` widget in Python to prevent the TUI from highlighting blocks during navigation.
- **Disable Indent Guides:** Set `code_indent_guides = False` to remove syntax-highlighter vertical lines that often inherit the default theme's accent color.
- **Target Sub-Widgets:** Use TCSS type selectors for the Markdown implementation:
    - `MarkdownH1` through `MarkdownH6` for headers.
    - `MarkdownFence` for code blocks.
    - `MarkdownBlockQuote` for blockquotes.
- **Override Syntax Highlighting:** To force a specific color scheme on generated code, use the wild-card selector within a fence:
  ```css
  MarkdownFence * {
      color: #f5f5f5 !important;
      background: transparent !important;
  }
  ```
- **Component Classes:** Use `.markdown--code_inline` for inline code segments rather than the generic `code` tag.

### Pathing & Portability
- **Wrapper Script Working Directory:** The `fprime-tui` bash wrapper MUST save the caller's working directory (`ORIGINAL_DIR`), locate its own `venv` to launch python, and then `cd` back to `ORIGINAL_DIR` before running `app.py`. This ensures dynamic environment discovery (`fprime-venv`) works properly based on where the user *is*, not where the tool is installed.