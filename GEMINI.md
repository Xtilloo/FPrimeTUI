# GEMINI.md - F-Prime-TUI (Mission Control)

## Project Overview
F-Prime-TUI, also known as **Mission Control**, is a Terminal User Interface (TUI) designed to provide AI-assisted development for the NASA F' (F Prime) flight software framework (v4.0). It leverages local LLMs via Ollama to provide context-aware engineering support directly in the terminal.

### Key Technologies
- **TUI Framework:** [Textual](https://textual.textualize.io/) (Async, CSS-driven)
- **Formatting:** [Rich](https://rich.readthedocs.io/) for terminal styling
- **AI Backend:** [Ollama](https://ollama.com/) (defaulting to `qwen3:8b`)
- **Integration:** `ollama-python` for async LLM communication

### Architecture
- `TUI/app.py`: The main entry point and UI logic using Textual.
- `TUI/fprime_ai_client.py`: Asynchronous client for interacting with the local Ollama instance.
- `Ollama/`: Contains installation guides and scripts for setting up the local LLM.

---

## Building and Running

### Prerequisites
- Python 3.9+
- A running [Ollama](https://ollama.com/) instance.
- The `qwen3:8b` model pulled (`ollama pull qwen3:8b`).

### Commands
All primary actions are managed via the `Makefile`:

- **Install Dependencies:**
  ```bash
  make install
  ```
- **Launch Mission Control:**
  ```bash
  make TUI
  ```
- **Cleanup:**
  ```bash
  make clean
  ```

---

## Development Conventions

### Coding Style
- **Asynchronous Execution:** The TUI and AI client are fully asynchronous. Use `async/await` and Textual's `@work` or `run_worker` for non-blocking operations.
- **Styling:** UI styling is managed via a CSS string within `TUI/app.py`. Follow existing color schemes (e.g., `#f39c12` for highlights, `#0b0b0b` for background).
- **Context Awareness:** The AI assistant uses `@filename` mentions to inject local file content into the prompt context.

### AI Integration & Target F' Environment
- The system prompt instructs the AI to act as a **Senior Principal Flight Software Engineer at NASA JPL**.
- It prioritizes **flight-safe C++** and **FPP (F' Prime Prescriptive)** code.
- It adheres to **JPL's C++ Coding Standards**.

> **CRITICAL REFERENCE:** 
> When developing logic for how the agent interacts with F' codebases, always refer to the strict constraints listed in:
> - `docs/fprime_commands.md` (CLI tooling rules)
> - `docs/fprime_conventions.md` (NASA's 10 rules, Memory Safety, FPP workflow)

---

## Development Standards & Lessons

### Modularization
- **CSS:** Always keep styles in `TUI/style.tcss`. Do not embed large CSS strings in `app.py`.
- **Widgets:** Move custom UI components (like `FadingScrollContainer`) to `TUI/widgets.py`.
- **Imports:** Run the app via `make TUI` to ensure `PYTHONPATH` is correctly set to include the `TUI/` directory.

### UI & UX Best Practices
- **Scrollbars:** Use `scrollbar-visibility: hidden` and `scrollbar-gutter: stable` for a minimal, non-intrusive feel.
- **Scroll Detection:** Use `watch_scroll_offset` in widgets to react to scrolling instead of looking for scroll events.
- **State Management:** Use CSS classes (e.g., `.generating`) on the `Screen` or `App` to toggle UI elements during long-running tasks.
- **Auto-Scrolling:** Always call `scroll_end(animate=False)` after updating the chat log during streaming to keep the latest output pinned above the prompt.

### TUI Interactions
- **Autocomplete:** Supports `/` for commands and `@` for file lookups.
- **Keybindings:**
  - `Ctrl+C`: Cancel AI generation.
  - `Ctrl+L`: Clear chat history.
  - `Ctrl+K`: Clear input field.
  - `Up/Down`: Navigate input history (or autocomplete suggestions).
  - `Tab`: Apply autocomplete suggestion.

---

## Troubleshooting & Post-Mortem

### The "Black Screen" Issue
The TUI may occasionally render only the input bar or a completely black screen.
- **Cause:** Usually a CSS failure. Textual stops loading a stylesheet if it encounters an invalid property.
- **Fix:** Ensure properties like `scrollbar-visibility` are avoided; use `scrollbar-size: 0 0` if hiding is required.
- **Cause:** Layout collapse. `1fr` containers require a clear vertical context.
- **Fix:** Always set `layout: vertical;` on the `Screen` in `style.tcss`.

### Pathing & Portability
- **Symlinks:** The `fprime-tui` script uses `readlink` to ensure it finds its `venv` even when called from a global alias in `/usr/local/bin`.
- **CSS Loading:** `CSS_PATH` is resolved relative to the file defining the `App` class. Ensure `style.tcss` is in the same directory as `app.py`.
- **Venv Corruption:** Moving the project folder can break the absolute paths inside `venv/bin/pip`. Always run `rm -rf venv && make install` after moving the project.