#!/usr/bin/env python3
"""Launch autonomous Claude agent for RAG evaluation Q41-Q262."""
import pathlib
import subprocess

prompt_path = pathlib.Path("/Users/xtilloo/Projects/FPrimeTUI/ClaudesLogs/scratch/autonomous-agent-prompt.md")
prompt = prompt_path.read_text()

subprocess.run([
    "claude",
    "--dangerously-skip-permissions",
    "-p", prompt
], cwd="/Users/xtilloo/Projects/FPrimeTUI")
