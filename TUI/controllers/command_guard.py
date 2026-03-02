import re
from pathlib import Path
from typing import Tuple, Optional, Dict

class CommandGuard:
    """
    Intercepts, validates, and repairs AI tool calls for F' command syntax and dependencies.
    """
    def __init__(self):
        # Map of hallucinated/invalid patterns to correct F' commands
        self.intent_map = [
            {
                "pattern": r"generate\s+component",
                "correction": "Did you mean fprime-util new --component?"
            },
            {
                "pattern": r"generate\s+deployment",
                "correction": "Did you mean fprime-util new --deployment?"
            },
            {
                "pattern": r"create\s+(component|deployment)",
                "correction": "Did you mean fprime-util new --component or --deployment?"
            },
            {
                "pattern": r"fpp-component",
                "correction": "fpp-component is not a tool. Use fprime-util new --component."
            }
        ]

    def repair(self, tool_json: dict, mission_state=None) -> Optional[dict]:
        """
        Attempts to automatically fix common AI hallucinations.
        Returns a new repaired tool_json or None if no repair possible.
        """
        tool_name = tool_json.get("tool_name")
        if tool_name not in ["run_fprime_command", "check_environment", "get_project_settings", "list_directory", "read_file"]:
            return None

        executable = tool_json.get("executable", "fprime-util")
        command = tool_json.get("command", "")
        args = tool_json.get("args", "")
        cwd = tool_json.get("cwd", ".")
        
        repaired = False
        new_json = tool_json.copy()

        # Repair 1: fpp-generate -> fprime-util new
        if tool_name == "run_fprime_command" and executable == "fpp-generate":
            new_json["executable"] = "fprime-util"
            if command == "component":
                new_json["command"] = "new"
                new_json["args"] = "--component " + args
                repaired = True
            elif command == "deployment":
                new_json["command"] = "new"
                new_json["args"] = "--deployment " + args
                repaired = True

        # Repair 2: fprime-util create -> fprime-util new
        if tool_name == "run_fprime_command" and executable == "fprime-util" and command == "create":
            new_json["command"] = "new"
            repaired = True

        # Repair 3: fpp-check -> fprime-util fpp-check
        if tool_name == "run_fprime_command" and executable == "fpp-check":
            new_json["executable"] = "fprime-util"
            new_json["command"] = "fpp-check"
            new_json["args"] = f"{command} {args}".strip()
            repaired = True

        # Repair 4: Automatic CWD correction if we know where the project is
        if mission_state and mission_state.discovered_project_root:
            # If AI is trying to run at root but project is in a sub-folder
            if cwd == "." or cwd == "./":
                # Special case: run_fprime_command MUST run in project root (with settings.ini)
                if tool_name == "run_fprime_command":
                    root_rel = os.path.relpath(mission_state.discovered_project_root, os.getcwd())
                    if root_rel != ".":
                        new_json["cwd"] = root_rel
                        repaired = True

        return new_json if repaired else None

    def validate(self, tool_json: dict, mission_state) -> Tuple[bool, Optional[str]]:
        """
        Validates a tool call. Returns (is_valid, error_message).
        """
        tool_name = tool_json.get("tool_name")
        if tool_name != "run_fprime_command":
            return True, None

        executable = tool_json.get("executable", "fprime-util")
        command = tool_json.get("command", "")
        args = tool_json.get("args", "")
        full_cmd_str = f"{command} {args}".strip()

        # Check for deprecated or hallucinated executables
        if executable in ["fprime-gen", "fpp-component", "fpp-generate", "fpp-to-cpp", "fpp-to-json"]:
            return False, f"INVALID EXECUTABLE. '{executable}' is not a valid tool. Most F' tasks use 'fprime-util'."

        # Check for hallucinated syntax in fprime-util
        if command == "create":
            return False, "INVALID SYNTAX. Use 'fprime-util new --component' or 'fprime-util new --deployment'."

        for entry in self.intent_map:
            if re.search(entry["pattern"], full_cmd_str):
                return False, f"INVALID SYNTAX. {entry['correction']}"

        # Check for dependencies
        if command == "build":
            # Use discovered root if available
            root_path = mission_state.discovered_project_root or mission_state.project_root
            build_dir = Path(root_path) / "build-fprime-automatic-native"
            if not build_dir.exists():
                return False, "Error: Build cache not found. You MUST run 'generate' first."

        return True, None

import os
