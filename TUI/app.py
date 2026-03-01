import re
import os
import time
from pathlib import Path
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Markdown, Input, OptionList
from textual.widgets.option_list import Option
from textual.events import Key

# Use absolute imports if running from root with PYTHONPATH=./TUI
# Or relative if this were a proper package. 
# Given the Makefile usage, PYTHONPATH=./TUI is assumed.
from fprime_ai_client import FPrimeAIClient
from widgets import FadingScrollContainer

COMMANDS = [
    ("/clear", "Clear chat history"),
    ("/help", "Show help documentation"),
    ("/build", "Trigger F' build process"),
    ("/exit", "Exit Mission Control"),
]

class FPrimeTUI(App):
    """
    F-Prime-TUI: Mission Control (Refined & Modular)
    """
    TITLE = "F-PRIME MISSION CONTROL"
    CSS_PATH = "style.tcss"

    BINDINGS = [
        ("ctrl+c", "cancel_generation", "Cancel"),
        ("ctrl+l", "clear_chat", "Clear"),
        ("ctrl+k", "clear_input", "Clear Input"),
    ]

    def __init__(self):
        super().__init__()
        self.ai_client = FPrimeAIClient()
        self.chat_history = "# Mission Control Online\nAwaiting command. Use `@file` or `/command`.\n"
        self.query_history = []
        self.history_index = -1
        self.temp_query = ""
        self.active_worker = None
        self.last_ctrl_c_time = 0

    def compose(self) -> ComposeResult:
        with FadingScrollContainer(id="chat-container"):
            yield Markdown(self.chat_history, id="chat-log")
        with Vertical(id="input-area"):
            yield OptionList(id="autocomplete-list")
            yield Input(placeholder="> Ask FPrime AI...", id="ai-input")


    async def on_mount(self) -> None:
        self.query_one("#ai-input").focus()

    def on_key(self, event: Key) -> None:
        input_widget = self.query_one("#ai-input")
        list_widget = self.query_one("#autocomplete-list")

        if event.key == "tab":
            event.prevent_default()
            event.stop()
            if list_widget.display:
                self._apply_suggestion()

        elif event.key == "up":
            if list_widget.display:
                event.prevent_default()
                list_widget.action_cursor_up()
            else:
                self._history_nav(1)
                
        elif event.key == "down":
            if list_widget.display:
                event.prevent_default()
                list_widget.action_cursor_down()
            else:
                self._history_nav(-1)

    def _history_nav(self, delta: int) -> None:
        input_widget = self.query_one("#ai-input")
        if not self.query_history: return
        
        if self.history_index == -1:
            self.temp_query = input_widget.value
            
        new_index = self.history_index + delta
        if -1 <= new_index < len(self.query_history):
            self.history_index = new_index
            if self.history_index == -1:
                input_widget.value = self.temp_query
            else:
                input_widget.value = self.query_history[-(self.history_index + 1)]
            input_widget.cursor_position = len(input_widget.value)

    def action_cancel_generation(self) -> None:
        if self.active_worker and self.active_worker.is_running:
            self.active_worker.cancel()
            self.chat_history += "\n\n> *(Generation cancelled)*"
            try:
                self.query_one("#chat-log", Markdown).update(self.chat_history)
            except: pass
            self._re_enable_input()
            self.last_ctrl_c_time = 0
        else:
            current_time = time.time()
            if current_time - self.last_ctrl_c_time < 1.0:
                self.exit()
            else:
                self.last_ctrl_c_time = current_time
                self.notify("Press Ctrl+C again to exit")

    def action_clear_chat(self) -> None:
        self.chat_history = "# Mission Control Cleared\n"
        try:
            self.query_one("#chat-log", Markdown).update(self.chat_history)
        except: pass

    def action_clear_input(self) -> None:
        input_widget = self.query_one("#ai-input", Input)
        input_widget.value = ""
        self.query_one("#autocomplete-list").display = False

    @on(Input.Changed, "#ai-input")
    def handle_input_changed(self, event: Input.Changed) -> None:
        text = event.value
        cursor_pos = event.input.cursor_position
        if not text:
            self.query_one("#autocomplete-list").display = False
            return
        if cursor_pos > 0 and cursor_pos <= len(text) and text[cursor_pos-1] == " ":
            self.query_one("#autocomplete-list").display = False
            return
        if not text[:cursor_pos].strip():
            self.query_one("#autocomplete-list").display = False
            return
        last_part = text[:cursor_pos].split()[-1]
        if last_part.startswith("/"):
            self._update_suggestions(last_part[1:], COMMANDS, "/")
        elif last_part.startswith("@"):
            self._update_suggestions(last_part[1:], self._get_file_suggestions(last_part[1:]), "@")
        else:
            self.query_one("#autocomplete-list").display = False

    def _get_file_suggestions(self, partial: str):
        try:
            p_low = partial.lower()
            return sorted([(f, f"File: {f}") for f in os.listdir(".") if os.path.isfile(f) and p_low in f.lower()])
        except: return []

    def _update_suggestions(self, partial: str, items: list, mode: str):
        self.suggestion_mode = mode
        list_widget = self.query_one("#autocomplete-list")
        list_widget.clear_options()
        p_low = partial.lower()
        matches = [Option(f"{label} - {desc}", id=label) for label, desc in items if p_low in label.lower()]
        if matches:
            list_widget.add_options(matches)
            list_widget.display = True
        else:
            list_widget.display = False

    def _apply_suggestion(self):
        list_widget = self.query_one("#autocomplete-list")
        input_widget = self.query_one("#ai-input")
        if list_widget.highlighted is None: return
        label = list_widget.get_option_at_index(list_widget.highlighted).id
        
        val = input_widget.value
        cursor = input_widget.cursor_position
        before_cursor = val[:cursor]
        after_cursor = val[cursor:]
        
        last_space_idx = before_cursor.rfind(" ")
        if last_space_idx == -1:
            prefix = ""
        else:
            prefix = before_cursor[:last_space_idx + 1]
            
        if label.startswith(self.suggestion_mode):
            new_word = f"{label} "
        else:
            new_word = f"{self.suggestion_mode}{label} "
            
        new_val = prefix + new_word + after_cursor
        
        input_widget.value = new_val
        input_widget.cursor_position = len(prefix) + len(new_word)
        list_widget.display = False

    @on(Input.Submitted, "#ai-input")
    async def handle_ai_query(self, event: Input.Submitted) -> None:
        if self.query_one("#autocomplete-list").display:
            self._apply_suggestion()
            return
        user_query = event.value
        if not user_query.strip(): return
        
        if user_query.startswith("/clear"):
            self.action_clear_chat()
            self.query_one("#ai-input").value = ""
            return
        elif user_query.startswith("/exit"):
            self.exit()
            return

        if not self.query_history or self.query_history[-1] != user_query:
            self.query_history.append(user_query)
        self.history_index = -1
        
        input_widget = self.query_one("#ai-input")
        input_widget.value = ""
        input_widget.disabled = True
        
        self.add_class("generating")
        self.chat_history += f"\n\n> {user_query}\n\n"
        self.query_one("#chat-log", Markdown).update(self.chat_history + "\n\n*Thinking...*")
        self.query_one("#chat-container").scroll_end(animate=False)
        
        mentions = re.findall(r"@([\w./-]+)", user_query)
        extra_ctx = ""
        for filename in mentions:
            file_path = Path(filename)
            if file_path.exists() and file_path.is_file():
                try: extra_ctx += f"\nFILE: {filename}\n---\n{file_path.read_text()}\n---\n"
                except: pass
        self.active_worker = self.run_worker(self.stream_ai_response(user_query, extra_ctx))

    async def stream_ai_response(self, query: str, extra_ctx: str) -> None:
        full_res = ""
        chat_log = self.query_one("#chat-log", Markdown)
        chat_container = self.query_one("#chat-container")
        try:
            async for chunk in self.ai_client.stream_chat(query, context=extra_ctx):
                full_res += chunk
                if full_res.strip():
                    chat_log.update(self.chat_history + full_res)
                    chat_container.scroll_end(animate=False)
            self.chat_history += full_res
        except Exception as e:
            if not full_res:
                self.chat_history += f"\n\n> **[ERROR]: {e}**"
                chat_log.update(self.chat_history)
        finally:
            self._re_enable_input()
            chat_container.scroll_end(animate=False)

    def _re_enable_input(self):
        self.remove_class("generating")
        input_widget = self.query_one("#ai-input")
        input_widget.disabled = False
        input_widget.focus()

if __name__ == "__main__":
    FPrimeTUI().run()
