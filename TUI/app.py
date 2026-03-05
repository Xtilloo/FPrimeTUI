import re
import os
import time
import json
import asyncio
import difflib
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Markdown, TextArea, OptionList, LoadingIndicator, Static, Footer
from textual.widgets.option_list import Option
from textual.events import Key

from TUI.fprime_ai_client import FPrimeAIClient
from TUI.command_definitions import TUIMode, COMMANDS
from TUI.widgets import FadingScrollContainer
from TUI.shell import run_fprime_command, check_environment, get_project_settings, kill_active_process
from TUI.utils import find_fprime_venv, escape_markdown
from TUI.tools import execute_read_file, execute_write_file, execute_replace_in_file, execute_list_directory, execute_grep_docs, execute_create_component
from TUI.command_definitions import COMMAND_REGISTRY

# New Controllers
from TUI.controllers.ai_handler import AIHandler
from TUI.controllers.mission import MissionController
from TUI.controllers.command_guard import CommandGuard

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
    F-Prime-TUI: Mission Control (Iterative & Robust)
    """
    TITLE = "F-PRIME MISSION CONTROL"
    CSS_PATH = Path(__file__).parent / "style.tcss"

    BINDINGS = [
        ("ctrl+c", "cancel_generation", "Cancel"),
        ("ctrl+l", "clear_chat", "Clear"),
        ("ctrl+k", "clear_input", "Clear Input"),
        ("ctrl+t", "toggle_agent_thoughts", "Toggle Thoughts"),
    ]

    def __init__(self):
        super().__init__()
        self.mode = TUIMode.ACADEMY
        self.ai_client = FPrimeAIClient(mode=self.mode)
        self.ai_handler = AIHandler(self.ai_client)
        self.mission_controller = MissionController(project_root=os.getcwd())
        self.command_guard = CommandGuard()
        
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
        self.turn_buffer = "" 
        self.last_update_time = 0
        self.is_generating = False
        self.project_components = []

    def compose(self) -> ComposeResult:
        with FadingScrollContainer(id="chat-container"):
            pass
        with Vertical(id="input-area"):
            yield OptionList(id="autocomplete-list")
            yield LoadingIndicator(id="thinking-indicator")
            with Horizontal(id="input-container"):
                yield Static(FPRIME_LOGO, id="prompt-label")
                yield CommandInput(id="ai-input")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#ai-input").focus()
        self.query_one("#thinking-indicator").display = False
        
        # Initial Status Message
        mode_title = "MISSION CONTROL" if self.mode == TUIMode.MISSION_CONTROL else "F' ACADEMY"
        self.TITLE = f"F-PRIME {mode_title}"
        await self._mount_ai_turn(f"# {mode_title} Online\nI am ready for the mission. Use `@file` to share context, or `/command` for manual tools.")
        
        # Silent Bootstrap Environmental Probe
        self._probe_environment()

    @work
    async def _probe_environment(self) -> None:
        venv = find_fprime_venv()
        if not venv: return
        try:
            for d in ["Components", "Deployments"]:
                p = Path(os.getcwd()) / d
                if p.exists() and p.is_dir():
                    for sub in p.iterdir():
                        if sub.is_dir():
                            self.project_components.append((sub.name, f"{d[:-1]}: {sub.name}"))
        except: pass
        ver_res = await run_fprime_command("version", venv_path=venv)
        self.ai_client.add_message("system", f"Environment probe complete. Project root: {os.getcwd()} F' Version: {ver_res['stdout'][:100]}")

    def trigger_query(self, text: str) -> None:
        if not text.strip(): return
        if self.is_generating:
            self.notify("Please wait for the current task to finish.", severity="warning")
            return
        self.active_worker = self.run_worker(self._ai_loop(text))

    async def _ai_loop(self, user_query: str) -> None:
        self.is_generating = True
        self.tool_call_depth = 0
        try:
            if self.pending_action:
                await self._handle_hitl_approval(user_query)
                return
            
            if user_query.startswith("/"):
                await self._handle_slash_command(user_query)
                return

            # Standard Query
            if not self.query_history or self.query_history[-1] != user_query: 
                self.query_history.append(user_query)
            self.history_index = -1
            self._prepare_for_generation()
            await self._mount_user_turn(user_query)
            
            mentions = re.findall(r"@([\w./-]+)", user_query)
            extra_ctx = ""
            for filename in mentions:
                file_path = Path(filename)
                if file_path.exists() and file_path.is_file():
                    try: extra_ctx += f"\nFILE: {filename}\n---\n{file_path.read_text()}\n---\n"
                    except: pass
            
            self.ai_client.add_message("user", user_query)
            
            # CORE TOOL LOOP
            while self.tool_call_depth < 20:
                self.tool_call_depth += 1
                await asyncio.sleep(0.01) 
                
                full_res, tool_json = await self._stream_response(extra_ctx)
                extra_ctx = "" 
                
                if not tool_json: break
                
                # Normalize args
                if "args" in tool_json and isinstance(tool_json["args"], list):
                    tool_json["args"] = " ".join([str(a) for a in tool_json["args"]])

                repaired_json = self.command_guard.repair(tool_json, self.mission_controller)
                if repaired_json: tool_json = repaired_json
                
                is_valid, correction = self.command_guard.validate(tool_json, self.mission_controller)
                if not is_valid:
                    self._add_to_chat_history(f"\n\n> **[SYNTAX ERROR]: {correction}**\n")
                    self.ai_client.add_message("user", f"SYSTEM ERROR: {correction}")
                    continue

                if tool_json["tool_name"] in ["replace_in_file", "write_file"]:
                    await self._prompt_hitl_approval(tool_json)
                    return 

                result_text = await self._dispatch_tool_logic(tool_json)
                success = await self._process_tool_result(tool_json, result_text)
                
                if not success and self.mission_controller.state["recovery_phase"] == "fatigue":
                    self._add_to_chat_history("\n\n**[MISSION ABORTED]: Too many failures.**\n")
                    break

            if self.tool_call_depth >= 20:
                self._add_to_chat_history("\n\n**[SYSTEM]: Maximum tool depth reached.**\n")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._add_to_chat_history(f"\n\n**[SYSTEM ERROR]: {str(e)}**\n")
        finally:
            self.is_generating = False
            self._re_enable_input()

    async def _stream_response(self, extra_ctx: str = "") -> tuple[str, Optional[dict]]:
        await self._mount_ai_turn()
        initial_turn_prefix = self.turn_buffer
        full_res = ""
        try:
            async for chunk in self.ai_client.stream_chat(context=extra_ctx):
                full_res += chunk
                if self.active_ai_widget and time.time() - self.last_update_time > 0.05:
                    try:
                        indicator = self.query_one("#thinking-indicator")
                        indicator.display = False
                    except: pass
                    display_text = full_res.replace("### FLIGHT PLAN", "\n\n## ✈️ FLIGHT PLAN")
                    if not self._show_agent_thoughts:
                        m = re.search(r"```json|({[\s\n]*\"tool_name\")", display_text)
                        if m: display_text = display_text[:m.start()].strip()
                    self.active_ai_widget.update(initial_turn_prefix + display_text)
                    self._scroll_to_end_if_at_bottom()
                    self.last_update_time = time.time()
        except Exception as e:
            full_res += f"\n\n> **[AI ERROR]: {e}**"

        self.sub_title = f"Tokens - Prompt: {self.ai_client.total_prompt_tokens} | Completion: {self.ai_client.total_completion_tokens}"
        
        tool_json = self.ai_handler.parse_tool_call(text=full_res)
        display_text = full_res.replace("### FLIGHT PLAN", "\n\n## ✈️ FLIGHT PLAN")
        if tool_json and not self._show_agent_thoughts:
             tool_match = re.search(r"```json|({[\s\n]*\"tool_name\")", full_res)
             if tool_match: display_text = full_res[:tool_match.start()].strip().replace("### FLIGHT PLAN", "\n\n## ✈️ FLIGHT PLAN")

        self.turn_buffer = initial_turn_prefix + display_text
        self.chat_history += display_text
        self.ai_client.add_message("assistant", full_res)
        if self.active_ai_widget: 
            self.active_ai_widget.update(self.turn_buffer)
            self._scroll_to_end_if_at_bottom()
        return full_res, tool_json

    async def _dispatch_tool_logic(self, tool_json: dict) -> str:
        tool_name = tool_json.get("tool_name")
        actions = {
            "run_fprime_command": lambda t: f"{t.get('executable', 'fprime-util')} {t.get('command', '')} {t.get('args', '')}".strip(),
            "read_file": lambda t: f"Reading {os.path.basename(t.get('path') or t.get('args', 'unknown'))}",
            "write_file": lambda t: f"Writing {os.path.basename(t.get('path', 'unknown'))}",
            "list_directory": lambda t: f"Listing {t.get('path') or t.get('args') or t.get('cwd', '.')}",
            "replace_in_file": lambda t: f"Updating {os.path.basename(t.get('path', 'unknown'))}",
            "check_environment": lambda t: f"Probing environment in {t.get('cwd', '.')}",
            "get_project_settings": lambda t: f"Reading project settings in {t.get('cwd', '.')}",
            "grep_docs": lambda t: f"Searching docs for '{t.get('query') or t.get('args', '')}'",
            "execute_create_component": lambda t: f"Creating component '{t.get('name')}'"
        }
        
        action_desc = actions.get(tool_name, lambda t: f"Executing {tool_name}")(tool_json)
        status_msg = f"Step {self.tool_call_depth}: {action_desc}"
        pending_tag = f"\n\n> *[{status_msg}... (RUNNING)]*\n"
        self._add_to_chat_history(pending_tag)
        self.last_status_tag = pending_tag
        self.last_status_complete = f"\n\n> *[{status_msg} COMPLETE]*\n"
        
        result_text = ""
        if tool_name == "run_fprime_command":
            res = await run_fprime_command(tool_json.get("command", ""), tool_json.get("args", ""), cwd=tool_json.get("cwd", "."), executable=tool_json.get("executable", "fprime-util"))
            result_text = f"Exit code: {res['exit_code']}\nStdout: {res['stdout']}\nStderr: {res['stderr']}"
            if res.get('recovery_hint'): result_text += f"\nRECOVERY HINT: {res['recovery_hint']}"
            if res['stdout']: self._add_to_chat_history(f"\n```\n{res['stdout']}\n```\n", is_agent_thought=True)
            if res['stderr']: self._add_to_chat_history(f"\n**[ERROR]**:\n```\n{res['stderr']}\n```\n", is_agent_thought=True)
        elif tool_name == "read_file": result_text = await execute_read_file(tool_json.get("path") or tool_json.get("args"))
        elif tool_name == "list_directory": result_text = await execute_list_directory(tool_json.get("path") or tool_json.get("args") or ".")
        elif tool_name == "grep_docs": result_text = await execute_grep_docs(tool_json.get("query") or tool_json.get("args"))
        elif tool_name == "check_environment": 
            res = await check_environment(tool_json.get("cwd", "."))
            if res.get("project_root"): self.mission_controller.discovered_project_root = res["project_root"]
            result_text = json.dumps(res, indent=2)
        elif tool_name == "get_project_settings": result_text = json.dumps(get_project_settings(tool_json.get("cwd", ".")), indent=2)
        elif tool_name == "execute_create_component": result_text = await execute_create_component(tool_json)
        else: result_text = f"Error: Tool '{tool_name}' not found."
        return result_text

    async def _process_tool_result(self, tool_json: dict, result_text: str) -> bool:
        success = not ("Error:" in result_text or "Exit code: -1" in result_text)
        if success and tool_json.get("tool_name") == "run_fprime_command":
            m = re.search(r"Exit code:\s*(\d+)", result_text)
            if m and int(m.group(1)) != 0: success = False
        
        status_final = self.last_status_complete if success else self.last_status_complete.replace("COMPLETE", "FAILED")
        if success: self.mission_controller.on_tool_success()
        else: self.mission_controller.on_tool_fail()

        if hasattr(self, 'last_status_tag') and self.active_ai_widget:
            self.turn_buffer = self.turn_buffer.replace(self.last_status_tag, status_final)
            self.active_ai_widget.update(self.turn_buffer)
            self.chat_history = self.chat_history.replace(self.last_status_tag, status_final)
            
        trunc = result_text if len(result_text) < 1000 else result_text[:1000] + "...[TRUNCATED]..."
        self._add_to_chat_history(f"\n> **[Tool Result]**:\n```\n{trunc}\n```\n")
        
        prompt_msg = f"SYSTEM: Tool execution {'SUCCESSFUL' if success else 'FAILED'}.\n\nTOOL RESULT:\n{result_text}\n\n"
        prompt_msg += self.mission_controller.get_recovery_directive(tool_json) if not success else "INSTRUCTION: Summarize result and continue plan."
        self.ai_client.add_message("user", prompt_msg)
        return success

    async def _handle_slash_command(self, user_query: str):
        cmd_name = user_query.split(" ")[0]
        cmd_meta = next((c for c in COMMANDS if c.name == cmd_name), None)
        
        if not cmd_meta:
            self._add_to_chat_history(f"\n\n**[SYSTEM]: Unknown command '{cmd_name}'.**\n")
            return
        elif self.mode.value not in [m.value for m in cmd_meta.allowed_modes]:
            allowed = ", ".join([m.value for m in cmd_meta.allowed_modes])
            self._add_to_chat_history(f"\n\n**[SYSTEM]: Command '{cmd_name}' is not available in {self.mode.value} mode. (Allowed in: {allowed})**\n")
            return

        if user_query.startswith("/clear"): self.action_clear_chat(); return
        if user_query.startswith("/exit"): self.exit(); return
        if user_query.startswith("/mode"):
            parts = user_query.split(" ")
            if len(parts) > 1:
                new_mode_str = parts[1].lower()
                if new_mode_str in ["dev", "mission_control"]: self.mode = TUIMode.MISSION_CONTROL
                elif new_mode_str in ["academy", "learning"]: self.mode = TUIMode.ACADEMY
                else:
                    self._add_to_chat_history(f"\n\n**[SYSTEM]: Invalid mode '{new_mode_str}'. Use 'dev' or 'academy'.**\n")
                    return
                self.ai_client.mode = self.mode
                mode_title = "MISSION CONTROL" if self.mode == TUIMode.MISSION_CONTROL else "F' ACADEMY"
                self.TITLE = f"F-PRIME {mode_title}"
                self._add_to_chat_history(f"\n\n**[SYSTEM]: Switched to {mode_title} mode.**\n")
                return
            else:
                self._add_to_chat_history(f"\n\n**[SYSTEM]: Current mode: {self.mode.value}. Use /mode <dev|academy> to switch.**\n")
                return
        
        command = user_query[1:].strip()
        self._prepare_for_generation()
        await self._mount_user_turn(user_query)
        self._add_to_chat_history(f"\n> *Running fprime-util {command}...*\n", is_agent_thought=True)
        
        parts = command.split(" ", 1)
        res = await run_fprime_command(parts[0], parts[1] if len(parts) > 1 else "", cwd=".")
        result_text = f"Manual Result (Exit {res['exit_code']}):\n{res['stdout']}\n{res['stderr']}"
        if res['stdout']: self._add_to_chat_history(f"\n```\n{res['stdout']}\n```\n", is_agent_thought=True)
        self.ai_client.add_message("user", f"I manually ran '{user_query}'. Result: {result_text}. Summarize.")
        await self._ai_loop("SYSTEM: Summarize the manual command result.")

    async def _handle_hitl_approval(self, user_query: str):
        q_lower = user_query.strip().lower()
        approved = q_lower in ["1", "approve", "yes", "y"]
        declined = q_lower in ["2", "decline", "no", "n"]
        if not (approved or declined): 
            self.is_generating = False
            return
        
        tool_json = self.pending_action
        self.pending_action = None
        
        if approved:
            await self._mount_user_turn("Approved")
            self._prepare_for_generation()
            if tool_json.get("tool_name") == "write_file":
                result_text = await execute_write_file(tool_json.get("path"), tool_json.get("content"))
            else:
                result_text = await execute_replace_in_file(tool_json.get("path"), tool_json.get("old_content"), tool_json.get("new_content"))
            
            self._add_to_chat_history(f"\n> **[Tool Result]**:\n```\n{result_text}\n```\n")
        else:
            await self._mount_user_turn("Declined")
            result_text = "User rejected the edit."
        
        await self._ai_loop(f"SYSTEM: User {('Approved' if approved else 'Declined')} edit. Result: {result_text}")

    async def _prompt_hitl_approval(self, tool_json: dict):
        self.pending_action = tool_json
        tool_name = tool_json.get("tool_name")
        action_verb = "modify" if tool_name == "replace_in_file" else "create/overwrite"
        
        diff_text = ""
        if tool_name == "replace_in_file":
            old_lines = tool_json.get("old_content", "").splitlines(keepends=True)
            new_lines = tool_json.get("new_content", "").splitlines(keepends=True)
            diff = list(difflib.unified_diff(old_lines, new_lines, fromfile="Current", tofile="Proposed", n=3))
            if diff: diff_text = "\n```diff\n" + "".join(diff) + "\n```\n"
        elif tool_name == "write_file":
            diff_text = "\n```text\n" + str(tool_json.get("content", ""))[:1000] + ("\n...[TRUNCATED]" if len(str(tool_json.get("content", ""))) > 1000 else "") + "\n```\n"

        self._add_to_chat_history(f"\n\n**Action Required:** AI wants to {action_verb} `{os.path.basename(tool_json.get('path', ''))}`.\n{diff_text}Do you approve? (1: Approve, 2: Decline)\n")
        self._re_enable_input()

    async def _mount_ai_turn(self, initial_text: str = ""):
        if not self.in_ai_turn or not self.active_ai_widget:
            await self._mount_header("Mission Control:")
            self.in_ai_turn = True
            containers = self.query("#chat-container")
            if not containers: return
            new_md = Markdown(initial_text, classes="ai-response selection-enabled")
            await containers[0].mount(new_md)
            self.active_ai_widget = new_md
            self.turn_buffer = initial_text
        elif initial_text: self._add_to_chat_history(initial_text)
        self._scroll_to_end_if_at_bottom()

    async def _mount_user_turn(self, text: str):
        self.in_ai_turn = False
        self.active_ai_widget = None
        self.turn_buffer = ""
        await self._mount_header("User:")
        containers = self.query("#chat-container")
        if containers: await containers[0].mount(Static(text, classes="user-prompt"))
        self.chat_history += f"\n\nUser: {text}\n\n"
        self._scroll_to_end_if_at_bottom()

    async def _mount_header(self, text: str):
        containers = self.query("#chat-container")
        if containers: await containers[0].mount(Static(text, classes="chat-header"))

    def _add_to_chat_history(self, message: str, is_agent_thought: bool = False) -> None:
        if is_agent_thought and not self._show_agent_thoughts: return
        self.chat_history += message
        if self.active_ai_widget:
            self.turn_buffer += message
            self.active_ai_widget.update(self.turn_buffer)
        else: asyncio.create_task(self._mount_ai_turn(message))
        self._scroll_to_end_if_at_bottom()

    def _prepare_for_generation(self):
        try:
            self.query_one("#ai-input", CommandInput).text = ""
            self.query_one("#thinking-indicator").display = True
            self.add_class("generating")
        except: pass

    def _re_enable_input(self):
        self.remove_class("generating")
        self.is_generating = False
        try:
            self.query_one("#thinking-indicator").display = False
            self.query_one("#ai-input", CommandInput).focus()
        except: pass

    def _scroll_to_end_if_at_bottom(self) -> None:
        try:
            containers = self.query("#chat-container")
            if not containers: return
            container = containers[0]
            container.scroll_end(animate=False)
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
            self.active_worker.cancel()
            # Immediately try to kill any subprocesses
            asyncio.create_task(kill_active_process())
            self._add_to_chat_history("\n\n> *(Cancelled)*")
            self._re_enable_input()
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

    def action_clear_input(self) -> None: self.query_one("#ai-input", CommandInput).text = ""

    def action_toggle_agent_thoughts(self) -> None:
        self._show_agent_thoughts = not self._show_agent_thoughts
        self.notify(f"Thoughts {'shown' if self._show_agent_thoughts else 'hidden'}")

    @on(TextArea.Changed, "#ai-input")
    def handle_input_changed(self, event: TextArea.Changed) -> None:
        input_widget = event.text_area; row, col = input_widget.cursor_location; lines = input_widget.text.splitlines()
        if not lines: self.query_one("#autocomplete-list").display = False; return
        current_line = lines[row] if row < len(lines) else ""; text_before_cursor = current_line[:col]
        if not text_before_cursor.strip() or text_before_cursor.endswith(" "): self.query_one("#autocomplete-list").display = False; return
        last_part = text_before_cursor.split()[-1]
        if self.pending_action:
            items = [("1", "Approve"), ("2", "Decline")]
            self._update_suggestions(last_part, items, "")
        elif last_part.startswith("/"):
            filtered_cmds = [(c.name, c.description) for c in COMMANDS if self.mode.value in [m.value for m in c.allowed_modes]]
            self._update_suggestions(last_part[1:], filtered_cmds, "/")
        elif last_part.startswith("@"): self._update_suggestions(last_part[1:], self._get_file_suggestions(last_part[1:]), "@")
        elif last_part.startswith("#"): self._update_suggestions(last_part[1:], self.project_components, "#")
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
