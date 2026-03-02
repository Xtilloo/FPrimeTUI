import re
import os
import time
import json
import asyncio
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Markdown, TextArea, OptionList, LoadingIndicator, Static
from textual.widgets.option_list import Option
from textual.events import Key

from fprime_ai_client import FPrimeAIClient
from command_definitions import TUIMode, COMMANDS
from widgets import FadingScrollContainer
from shell import run_fprime_command
from utils import find_fprime_venv, escape_markdown
from tools import execute_read_file, execute_replace_in_file, execute_list_directory

# FPRIME_LOGO = """ ▛▀▀ '
#  ▙▄
#  ▌ """

FPRIME_LOGO = ">"

class CommandInput(TextArea):
    """A TextArea specifically tuned for command entry."""
    def on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.app.trigger_query(self.text)

class FPrimeTUI(App):
    """
    F-Prime-TUI: Mission Control (Refined & Modular)
    """
    TITLE = "F-PRIME MISSION CONTROL"
    CSS_PATH = Path(__file__).parent / "style.tcss"

    BINDINGS = [
        ("ctrl+c", "cancel_generation", "Cancel"),
        ("ctrl+l", "clear_chat", "Clear"),
        ("ctrl+k", "clear_input", "Clear Input"),
    ]

    def __init__(self):
        super().__init__()
        self.mode = TUIMode.ACADEMY
        self.ai_client = FPrimeAIClient(mode=self.mode)
        self.chat_history = ""
        self.query_history = []
        self.history_index = -1
        self.temp_query = ""
        self.active_worker = None
        self.last_ctrl_c_time = 0
        self.pending_action = None
        self._show_agent_thoughts = False
        self.suggestion_mode = ""
        self.tool_call_depth = 0
        self.active_ai_widget = None
        self.in_ai_turn = False
        self.turn_buffer = "" # Tracks content for the current isolated Turn widget
        self.last_update_time = 0
        self.is_generating = False

    def compose(self) -> ComposeResult:
        with FadingScrollContainer(id="chat-container"):
            pass
        with Vertical(id="input-area"):
            yield OptionList(id="autocomplete-list")
            yield LoadingIndicator(id="thinking-indicator")
            with Horizontal(id="input-container"):
                yield Static(FPRIME_LOGO, id="prompt-label")
                yield CommandInput(id="ai-input")

    async def on_mount(self) -> None:
        self.query_one("#ai-input").focus()
        self.query_one("#thinking-indicator").display = False
        containers = self.query("#chat-container")
        if not containers: return
        container = containers[0]
        # Direct mount for status to avoid turn logic overhead at boot
        status_md = Markdown("# Mission Control Online\nI am ready for the mission. Use `@file` to share context, or `/command` for manual tools. I will provide a **Flight Plan** for complex operations.", classes="ai-response selection-enabled")
        status_md.can_focus = True
        status_md.content_selectable = True
        status_md.code_indent_guides = False
        status_md.code_dark_theme = "monokai"
        await container.mount(status_md)

    def trigger_query(self, text: str) -> None:
        if not text.strip(): return
        if self.is_generating:
            self.notify("Please wait for the current task to finish.", severity="warning")
            return
        self.active_worker = self._ai_loop(text)

    @work
    async def _ai_loop(self, user_query: str) -> None:
        self.is_generating = True
        try:
            if self.pending_action:
                await self._handle_hitl_approval(user_query)
                return
            if user_query.startswith("/"):
                await self._handle_slash_command(user_query)
                return
            await self._process_standard_query(user_query)
        except Exception as e:
            self._add_to_chat_history(f"\n\n**[SYSTEM ERROR]: {str(e)}**\n")
        finally:
            self.is_generating = False
            self._re_enable_input()

    async def _handle_hitl_approval(self, user_query: str):
        q_lower = user_query.strip().lower()
        approved = None
        if q_lower in ["1", "approve", "yes", "y"]: approved = True
        elif q_lower in ["2", "decline", "no", "n"]: approved = False
        if approved is None: 
            self.is_generating = False # Re-enable for further attempts
            return
        tool_json = self.pending_action
        self.pending_action = None
        self._prepare_for_generation()
        path = tool_json.get("path"); old_c = tool_json.get("old_content"); new_c = tool_json.get("new_content")
        if approved:
            await self._mount_user_turn("Approved")
            result_text = await execute_replace_in_file(path, old_c, new_c)
        else:
            await self._mount_user_turn("Declined")
            result_text = "User rejected the edit."
        await self._execute_tool_sequence(tool_json.get("tool_name"), result_text)

    async def _mount_header(self, text: str):
        containers = self.query("#chat-container")
        if not containers: return
        await containers[0].mount(Static(text, classes="chat-header"))

    async def _mount_user_turn(self, text: str):
        self.in_ai_turn = False
        self.active_ai_widget = None
        self.turn_buffer = ""
        await self._mount_header("User:")
        containers = self.query("#chat-container")
        if not containers: return
        await containers[0].mount(Static(text, classes="user-prompt"))
        self.chat_history += f"\n\nUser: {text}\n\n"
        self._scroll_to_end_if_at_bottom()

    async def _mount_ai_turn(self, initial_text: str = ""):
        if not self.in_ai_turn or not self.active_ai_widget:
            if not self.in_ai_turn:
                await self._mount_header("Mission Control:")
                self.in_ai_turn = True
            
            containers = self.query("#chat-container")
            if not containers: return
            new_md = Markdown(initial_text, classes="ai-response selection-enabled")
            new_md.can_focus = True
            new_md.content_selectable = True
            new_md.code_indent_guides = False
            new_md.code_dark_theme = "monokai"
            await containers[0].mount(new_md)
            self.active_ai_widget = new_md
            self.turn_buffer = initial_text
        elif initial_text:
            self._add_to_chat_history(initial_text)
            
        if initial_text: self.chat_history += f"Mission Control:\n{initial_text}"
        self._scroll_to_end_if_at_bottom()

    def _add_to_chat_history(self, message: str, is_agent_thought: bool = False) -> None:
        """Appends to the current Turn's widget and the global memory."""
        if is_agent_thought and not self._show_agent_thoughts: return
        
        self.chat_history += message
        if self.active_ai_widget:
            self.turn_buffer += message
            self.active_ai_widget.update(self.turn_buffer)
        else:
            asyncio.create_task(self._mount_ai_turn(message))
        self._scroll_to_end_if_at_bottom()

    async def _handle_slash_command(self, user_query: str):
        self.tool_call_depth = 0 # Reset depth to allow a fresh autonomous chain
        cmd_name = user_query.split(" ")[0]
        
        # Find command metadata
        cmd_meta = next((c for c in COMMANDS if c.name == cmd_name), None)
        if not cmd_meta:
            self._add_to_chat_history(f"\n\n**[SYSTEM]: Unknown command '{cmd_name}'.**\n")
            return

        # Check mode
        if self.mode not in cmd_meta.allowed_modes:
            allowed = ", ".join([m.value for m in cmd_meta.allowed_modes])
            self._add_to_chat_history(f"\n\n**[SYSTEM]: Command '{cmd_name}' is not available in {self.mode.value} mode. (Allowed in: {allowed})**\n")
            return

        if user_query.startswith("/clear"):
            self.action_clear_chat(); self.query_one("#ai-input", CommandInput).text = ""; return
        elif user_query.startswith("/exit"): self.exit(); return
        elif user_query.startswith("/mode"):
            parts = user_query.split(" ")
            if len(parts) > 1:
                new_mode_str = parts[1].lower()
                if new_mode_str in ["dev", "mission_control"]:
                    self.mode = TUIMode.MISSION_CONTROL
                elif new_mode_str in ["academy", "learning"]:
                    self.mode = TUIMode.ACADEMY
                else:
                    self._add_to_chat_history(f"\n\n**[SYSTEM]: Invalid mode '{new_mode_str}'. Use 'dev' or 'academy'.**\n")
                    return
                
                self.ai_client.mode = self.mode
                mode_title = "MISSION CONTROL" if self.mode == TUIMode.MISSION_CONTROL else "F' ACADEMY"
                self.TITLE = f"F-PRIME {mode_title}"
                self._add_to_chat_history(f"\n\n**[SYSTEM]: Switched to {mode_title} mode.**\n")
                self.query_one("#ai-input", CommandInput).text = ""
                return
            else:
                self._add_to_chat_history(f"\n\n**[SYSTEM]: Current mode: {self.mode.value}. Use /mode <dev|academy> to switch.**\n")
                return

        command = user_query[1:].strip()
        self._prepare_for_generation(); await self._mount_user_turn(user_query)
        self._add_to_chat_history(f"\n> *Running fprime-util {command}...*\n", is_agent_thought=True)
        venv = find_fprime_venv()
        if not venv: result_text = "Error: fprime-venv not found."
        else:
            parts = command.split(" ", 1); cmd = parts[0]; args = parts[1] if len(parts) > 1 else ""
            res = await run_fprime_command(venv, cmd, args, cwd=".")
            result_text = f"Manual Result (Exit {res['exit_code']}):\n{res['stdout']}\n{res['stderr']}"
            if res['stdout']: self._add_to_chat_history(f"\n```\n{res['stdout']}\n```\n", is_agent_thought=True)
            if res['stderr']: self._add_to_chat_history(f"\n**[ERROR]**:\n```\n{res['stderr']}\n```\n", is_agent_thought=True)
        self.ai_client.add_message("user", f"I manually ran '{user_query}'. Result: {result_text}. Please summarize.")
        await self._stream_and_handle_tools()

    async def _process_standard_query(self, user_query: str):
        self.tool_call_depth = 0
        if not self.query_history or self.query_history[-1] != user_query: self.query_history.append(user_query)
        self.history_index = -1; self._prepare_for_generation(); await self._mount_user_turn(user_query)
        mentions = re.findall(r"@([\w./-]+)", user_query); extra_ctx = ""
        for filename in mentions:
            file_path = Path(filename)
            if file_path.exists() and file_path.is_file():
                try: extra_ctx += f"\nFILE: {filename}\n---\n{file_path.read_text()}\n---\n"
                except: pass
        self.ai_client.add_message("user", user_query); await self._stream_and_handle_tools(extra_ctx)

    def _prepare_for_generation(self):
        try:
            input_widget = self.query_one("#ai-input", CommandInput)
            input_widget.text = ""
            self.query_one("#thinking-indicator").display = True
            self.add_class("generating")
        except: pass

    async def _stream_and_handle_tools(self, extra_ctx: str = "") -> None:
        self.tool_call_depth += 1
        if self.tool_call_depth > 10:
            self._add_to_chat_history("\n\n**[SYSTEM]: Maximum tool depth reached (10).**\n")
            return
        
        full_res = ""
        await self._mount_ai_turn()
        tool_json_str = None
        initial_turn_prefix = self.turn_buffer
        
        try:
            async for chunk in self.ai_client.stream_chat(context=extra_ctx):
                if chunk:
                    self.query_one("#thinking-indicator").display = False
                full_res += chunk
                
                if full_res.strip():
                    display_text = full_res
                    # Detect Flight Plan and wrap it in a special block if found
                    if "### FLIGHT PLAN" in display_text:
                        # Ensure there is a newline before the flight plan to separate from previous status
                        display_text = display_text.replace("### FLIGHT PLAN", "\n\n## ✈️ FLIGHT PLAN")

                    if not self._show_agent_thoughts:
                        match_start = full_res.find("```json")
                        if match_start != -1:
                            display_text = display_text[:match_start]
                    
                    if self.active_ai_widget:
                        current_time = time.time()
                        if current_time - self.last_update_time > 0.05: # Throttle to 20fps
                            self.active_ai_widget.update(initial_turn_prefix + display_text)
                            self._scroll_to_end_if_at_bottom()
                            self.last_update_time = current_time
        except Exception as e:
            full_res += f"\n\n> **[AI ERROR]: {e}**"
        
        final_displayed_seg = full_res
        if "### FLIGHT PLAN" in final_displayed_seg:
            final_displayed_seg = final_displayed_seg.replace("### FLIGHT PLAN", "\n\n## ✈️ FLIGHT PLAN")

        tool_match = re.search(r"```json\s*(.*?)\s*```", full_res, re.DOTALL)
        if tool_match:
            tool_json_str = tool_match.group(1)
            if not self._show_agent_thoughts:
                # We need to find where the tool block starts in the MODIFIED final_displayed_seg
                # but it's easier to just slice the original full_res and then apply the replace
                final_displayed_seg = full_res[:tool_match.start()]
                if "### FLIGHT PLAN" in final_displayed_seg:
                    final_displayed_seg = final_displayed_seg.replace("### FLIGHT PLAN", "\n\n## ✈️ FLIGHT PLAN")
        
        # Sync turn buffer and memory
        if final_displayed_seg.strip():
            self.turn_buffer = initial_turn_prefix + final_displayed_seg
            self.chat_history += final_displayed_seg
        
        self.ai_client.add_message("assistant", full_res)
        if self.active_ai_widget:
            self.active_ai_widget.update(self.turn_buffer)
        self._scroll_to_end_if_at_bottom()
        
        if tool_json_str:
            try:
                tool_json = json.loads(tool_json_str)
                # Pause to let UI render the text BEFORE the tool starts
                await asyncio.sleep(0.1)
                await self._dispatch_tool(tool_json)
            except Exception:
                self.ai_client.add_message("user", "System Error: Invalid JSON emitted by AI.")
                await self._stream_and_handle_tools()

    async def _dispatch_tool(self, tool_json: dict):
        tool_name = tool_json.get("tool_name")
        if tool_name == "run_fprime_command":
            exe = tool_json.get("executable", "fprime-util")
            cmd = tool_json.get('command', '')
            args = tool_json.get('args', '')
            action = f"{exe} {cmd} {args}".strip()
        elif tool_name == "read_file":
            action = f"Reading {os.path.basename(tool_json.get('path'))}"
        elif tool_name == "list_directory":
            action = f"Listing {tool_json.get('path')}"
        elif tool_name == "replace_in_file":
            action = f"Updating {os.path.basename(tool_json.get('path'))}"
        else:
            action = f"Executing {tool_name}"

        # Use tool_call_depth as a proxy for the step number
        status_msg = f"Step {self.tool_call_depth}: {action}"
        pending_tag = f"\n\n> *[{status_msg}... (RUNNING)]*\n"
        
        # Status lines should always be visible to user
        self._add_to_chat_history(pending_tag, is_agent_thought=False)
        if self.active_ai_widget:
            self.active_ai_widget.update(self.turn_buffer)
        
        self.last_status_tag = pending_tag
        self.last_status_complete = f"\n\n> *[{status_msg} COMPLETE]*\n"

        if tool_name == "replace_in_file":
            path = tool_json.get("path"); self.pending_action = tool_json
            # Small pause to ensure the status line is rendered before the prompt
            await asyncio.sleep(0.1)
            self._add_to_chat_history(f"\n\n**Action Required:** AI wants to modify `{os.path.basename(path)}`.\nDo you approve? (1: Approve, 2: Decline)\n", is_agent_thought=False)
            self._re_enable_input(); return
            
        result_text = ""
        if tool_name == "run_fprime_command":
            cwd = tool_json.get("cwd", "."); venv = find_fprime_venv(Path(cwd))
            if not venv: venv = find_fprime_venv() # Fallback to project root venv
            if not venv: result_text = f"Error: venv not found in {cwd} or root."
            else:
                # Use absolute path for venv
                res = await run_fprime_command(
                    venv.resolve(), 
                    tool_json.get("command", ""), 
                    tool_json.get("args", ""), 
                    cwd=cwd,
                    executable=tool_json.get("executable", "fprime-util")
                )
                result_text = f"Exit code: {res['exit_code']}\nStdout: {res['stdout']}\nStderr: {res['stderr']}"
                if res['stdout']: self._add_to_chat_history(f"\n```\n{res['stdout']}\n```\n", is_agent_thought=True)
                if res['stderr']: self._add_to_chat_history(f"\n**[ERROR]**:\n```\n{res['stderr']}\n```\n", is_agent_thought=True)
        elif tool_name == "read_file": result_text = await execute_read_file(tool_json.get("path"))
        elif tool_name == "list_directory": result_text = await execute_list_directory(tool_json.get("path"))
        else: result_text = f"Error: Tool '{tool_name}' not found."
        await self._execute_tool_sequence(tool_name, result_text)

    async def _execute_tool_sequence(self, tool_name: str, result_text: str):
        status_final = self.last_status_complete
        # Check for failure in the result text (specific to our run_fprime_command output format)
        if "Exit code:" in result_text:
            try:
                # Extract exit code: "Exit code: 1"
                parts = result_text.split("\n")[0].split(":")
                if len(parts) > 1 and int(parts[1].strip()) != 0:
                    status_final = self.last_status_complete.replace("COMPLETE", "FAILED")
            except: pass
        elif result_text.startswith("Error:"):
            status_final = self.last_status_complete.replace("COMPLETE", "FAILED")

        if hasattr(self, 'last_status_tag') and self.active_ai_widget:
            updated = self.turn_buffer.replace(self.last_status_tag, status_final)
            self.turn_buffer = updated
            self.active_ai_widget.update(self.turn_buffer)
            self.chat_history = self.chat_history.replace(self.last_status_tag, status_final)
            
        trunc = result_text if len(result_text) < 500 else result_text[:500] + "...[TRUNCATED]..."
        self._add_to_chat_history(f"\n> *Tool Result:*\n```\n{trunc}\n```\n", is_agent_thought=True)
        
        # If it failed, we explicitly tell the AI it MUST run --help
        if "FAILED" in status_final:
            prompt_msg = f"Tool Response (FAILED):\n{result_text}\n\nCRITICAL: The last command failed. You MUST now run the same command with the '--help' flag to investigate the usage. Do not attempt manual fixes yet."
        else:
            prompt_msg = f"Tool Response:\n{result_text}"
            
        self.ai_client.add_message("user", prompt_msg)
        
        # We MUST ensure the AI loop continues or input is restored
        try:
            await self._stream_and_handle_tools()
        finally:
            # If tool_call_depth returns to 0 (or loop ends), input is restored in _ai_loop
            # but _stream_and_handle_tools is recursive, so we handle re-enable at the root.
            pass

    def _re_enable_input(self):
        if self._closing: return
        self.remove_class("generating")
        self.is_generating = False
        try:
            self.query_one("#thinking-indicator").display = False
            input_widget = self.query_one("#ai-input", CommandInput)
            input_widget.focus()
        except: pass

    def on_key(self, event: Key) -> None:
        list_widget = self.query_one("#autocomplete-list")
        if event.key in ["enter", "tab"] and list_widget.display: event.prevent_default(); event.stop(); self._apply_suggestion()
        elif event.key == "up":
            if list_widget.display: event.prevent_default(); list_widget.action_cursor_up()
            else: self._history_nav(1)
        elif event.key == "down":
            if list_widget.display: event.prevent_default(); list_widget.action_cursor_down()
            else: self._history_nav(-1)

    def _history_nav(self, delta: int) -> None:
        input_widget = self.query_one("#ai-input", CommandInput)
        if not self.query_history: return
        if self.history_index == -1: self.temp_query = input_widget.text
        new_index = self.history_index + delta
        if -1 <= new_index < len(self.query_history):
            self.history_index = new_index
            input_widget.text = self.temp_query if self.history_index == -1 else self.query_history[-(self.history_index + 1)]
            lines = input_widget.text.splitlines()
            input_widget.cursor_location = (len(lines)-1, len(lines[-1])) if lines else (0, 0)

    def action_cancel_generation(self) -> None:
        if self.active_worker and self.active_worker.is_running:
            self.active_worker.cancel(); self._add_to_chat_history("\n\n> *(Cancelled)*", is_agent_thought=True); self._re_enable_input()
        else:
            if time.time() - self.last_ctrl_c_time < 1.0: self.exit()
            else: self.last_ctrl_c_time = time.time(); self.notify("Press Ctrl+C again to exit")

    def action_clear_chat(self) -> None:
        self.chat_history = ""; self.ai_client.clear_history(); self.turn_buffer = ""; self.active_ai_widget = None
        try:
            containers = self.query("#chat-container")
            if not containers: return
            container = containers[0]
            for child in list(container.children): child.remove()
            asyncio.create_task(self._mount_ai_turn("# Mission Control Cleared"))
        except: pass

    def action_clear_input(self) -> None:
        self.query_one("#ai-input", CommandInput).text = ""
        self.query_one("#autocomplete-list").display = False

    def _scroll_to_end_if_at_bottom(self) -> None:
        containers = self.query("#chat-container")
        if not containers: return
        container = containers[0]
        if container.scroll_offset.y >= container.max_scroll_y - 2: container.scroll_end(animate=False)

    @on(TextArea.Changed, "#ai-input")
    def handle_input_changed(self, event: TextArea.Changed) -> None:
        input_widget = event.text_area; row, col = input_widget.cursor_location; lines = input_widget.text.splitlines()
        if not lines: self.query_one("#autocomplete-list").display = False; return
        current_line = lines[row] if row < len(lines) else ""; text_before_cursor = current_line[:col]
        if not text_before_cursor.strip() or text_before_cursor.endswith(" "): self.query_one("#autocomplete-list").display = False; return
        last_part = text_before_cursor.split()[-1]
        if self.pending_action:
            if last_part in ["1", "2"]: self.query_one("#autocomplete-list").display = False; return
            items = [("1", "Approve"), ("2", "Decline")]
            if "1" in last_part: items = [("1", "Approve")]
            elif "2" in last_part: items = [("2", "Decline")]
            self._update_suggestions(last_part, items, "")
        elif last_part.startswith("/"):
            filtered_cmds = [(c.name, c.description) for c in COMMANDS if self.mode in c.allowed_modes]
            self._update_suggestions(last_part[1:], filtered_cmds, "/")
        elif last_part.startswith("@"): self._update_suggestions(last_part[1:], self._get_file_suggestions(last_part[1:]), "@")
        else: self.query_one("#autocomplete-list").display = False

    def _get_file_suggestions(self, partial: str):
        try:
            p_low = partial.lower()
            return sorted([(f, f"File: {f}") for f in os.listdir(".") if os.path.isfile(f) and p_low in f.lower()])
        except: return []

    def _update_suggestions(self, partial: str, items: list, mode: str):
        self.suggestion_mode = mode; list_widget = self.query_one("#autocomplete-list"); list_widget.clear_options()
        matches = []
        for label, desc in items:
            if partial.lower() in label.lower():
                display_label = label if label.startswith(mode) else f"{mode}{label}"
                matches.append(Option(f"{display_label} - {desc}", id=label))
        
        if matches: list_widget.add_options(matches); list_widget.display = True
        else: list_widget.display = False

    def _apply_suggestion(self):
        list_widget = self.query_one("#autocomplete-list"); input_widget = self.query_one("#ai-input", CommandInput)
        if list_widget.highlighted is None: return
        label = list_widget.get_option_at_index(list_widget.highlighted).id; row, col = input_widget.cursor_location; lines = input_widget.text.splitlines()
        before = lines[row][:col]; after = lines[row][col:]; last_space = before.rfind(" ")
        prefix = "" if last_space == -1 else before[:last_space + 1]
        new_word = f"{label} " if label.startswith(self.suggestion_mode) else f"{self.suggestion_mode}{label} "
        lines[row] = prefix + new_word + after; input_widget.text = "\n".join(lines); input_widget.cursor_location = (row, len(prefix) + len(new_word)); list_widget.display = False

if __name__ == "__main__":
    FPrimeTUI().run()
