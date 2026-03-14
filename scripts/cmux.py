#!/usr/bin/env python3
import os
import json
import subprocess
import sys
from pathlib import Path

def run_cmux(args):
    """Executes a cmux command."""
    cmd = ["cmux"] + args
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result

def setup_workspace(workspace_config):
    """Sets up a cmux workspace with tabs from config."""
    workspace_name = workspace_config.get("name", "New Workspace")
    tabs = workspace_config.get("tabs", [])

    # Create new workspace
    run_cmux(["new-workspace", "--title", workspace_name])
    
    # Get current workspace ID (it will be the last one created)
    # Actually, new-workspace should focus it, and identify --workspace can find it
    id_res = run_cmux(["identify", "--no-caller"])
    if id_res.returncode != 0: return
    
    # We'll use the workspace name for targeting if needed, or identify
    workspace_id = None
    list_res = run_cmux(["list-workspaces"])
    for line in list_res.stdout.splitlines():
        if workspace_name in line:
            workspace_id = line.split()[0] # Assume first col is ID
            break
    
    if not workspace_id:
        print(f"Could not find workspace ID for {workspace_name}")
        return

    for i, tab in enumerate(tabs):
        tab_name = tab.get("name", f"Tab {i+1}")
        commands = tab.get("commands", [])
        tab_type = tab.get("type", "terminal")
        
        if i == 0:
            # First tab is already there, just rename and run commands
            run_cmux(["rename-tab", "--workspace", workspace_id, "--tab", "0", tab_name])
            surface_id = "0"
        else:
            # Create new surface (tab)
            # cmux new-surface defaults to terminal
            url = tab.get("url", "")
            if tab_type == "browser":
                run_cmux(["new-surface", "--type", "browser", "--workspace", workspace_id, "--url", url])
            else:
                run_cmux(["new-surface", "--workspace", workspace_id])
            
            # Identify the new surface
            # This is tricky without IDs, but we can assume it's the last one in the workspace
            # For simplicity, we'll just rename the last surface
            run_cmux(["rename-tab", "--workspace", workspace_id, "--tab", str(i), tab_name])
            surface_id = str(i)

        # Run commands if any
        if commands:
            cmd_str = " && ".join(commands) + "\n"
            run_cmux(["send", "--workspace", workspace_id, "--surface", surface_id, cmd_str])
        
        # Handle input lines (auto-typed)
        input_lines = tab.get("input", {}).get("lines", [])
        for line_config in input_lines:
            text = line_config.get("text", "")
            submit = line_config.get("submit", True)
            if submit: text += "\n"
            run_cmux(["send", "--workspace", workspace_id, "--surface", surface_id, text])

def main():
    config_path = Path(".vscode/terminals.json")
    if not config_path.exists():
        print("No .vscode/terminals.json found.")
        sys.exit(1)
        
    with open(config_path, "r") as f:
        config = json.load(f)
    
    cmux_config = config.get("cmux", [])
    for workspace in cmux_config:
        setup_workspace(workspace)

if __name__ == "__main__":
    main()
