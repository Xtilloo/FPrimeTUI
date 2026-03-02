import re
from pathlib import Path

class CommandGuard:
    """
    Intercepts and validates AI tool calls for F' command syntax and dependencies.
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
            }
        ]

    def validate(self, tool_json: dict, mission_state) -> (bool, str):
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

        # Check for deprecated executables
        if executable == "fprime-gen":
            return False, "fprime-gen is deprecated. Use fprime-util."

        # Check for hallucinated syntax in fprime-util
        for entry in self.intent_map:
            if re.search(entry["pattern"], full_cmd_str):
                return False, f"INVALID SYNTAX. {entry['correction']}"

        # Check for dependencies
        if command == "build":
            root = Path(mission_state.project_root)
            build_dir = root / "build-fprime-automatic-native"
            if not build_dir.exists():
                return False, "Error: Build cache not found. You MUST run 'generate' first."

        return True, None
