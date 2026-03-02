from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class MissionState:
    """
    Data structure to track the autonomous session state.
    """
    failure_count: int = 0
    recovery_phase: str = "none" # none, help, docs, fatigue
    project_root: str = "."

class MissionController:
    """
    Manages the autonomous lifecycle and recovery hierarchy.
    """
    def __init__(self, project_root: str = "."):
        self.state = {
            "failure_count": 0,
            "recovery_phase": "none",
            "project_root": project_root
        }

    def on_tool_success(self):
        """Reset failure tracking on success."""
        self.state["failure_count"] = 0
        self.state["recovery_phase"] = "none"

    def on_tool_fail(self):
        """Increment failure tracking and advance recovery phase."""
        self.state["failure_count"] += 1
        
        if self.state["failure_count"] == 1:
            self.state["recovery_phase"] = "help"
        elif self.state["failure_count"] == 2:
            self.state["recovery_phase"] = "docs"
        elif self.state["failure_count"] >= 3:
            self.state["recovery_phase"] = "fatigue"

    def get_recovery_directive(self, tool_json: dict) -> str:
        """
        Returns a system directive for the AI based on the current recovery phase.
        Analyzes the tool_json to suggest a simplified --help command.
        """
        phase = self.state["recovery_phase"]
        
        # Determine the base command for help
        exe = tool_json.get("executable", "fprime-util")
        cmd = tool_json.get("command", "")
        base_help = f"{exe} {cmd} --help".strip()
        
        if phase == "help":
            return (
                f"CRITICAL: The command failed. You MUST now run a simplified diagnostic command "
                f"to investigate usage: `{base_help}`."
            )
        elif phase == "docs":
            return (
                f"CRITICAL: `{base_help}` was insufficient. "
                f"You MUST now use 'grep_docs' with a keyword related to the intent (e.g., 'new', 'component') "
                f"to find the correct syntax in the project documentation."
            )
        elif phase == "fatigue":
            return (
                f"MISSION ABORTED: 3+ consecutive failures detected. "
                f"STOP all autonomous actions and advise the user to check the manual build logs."
            )
        
        return "Proceed with the next step of your Flight Plan."
