import os
import re
from pathlib import Path

def find_fprime_venv(start_path: Path = None) -> Path | None:
    if start_path is None:
        start_path = Path.cwd()
    current = start_path.resolve()
    while current != current.parent:
        potential_venv = current / "fprime-venv"
        if potential_venv.is_dir() and (potential_venv / "bin" / "activate").exists():
            return potential_venv
        current = current.parent
    return None

def escape_markdown(text: str) -> str:
    """Escapes markdown special characters so they don't get interpreted by the UI."""
    # List of characters to escape: \ ` * _ { } [ ] ( ) # + - . !
    # We mainly care about those common in paths or error logs
    chars = [r'\\', r'\*', r'_', r'\{', r'\}', r'\[', r'\]', r'\(', r'\)', r'#', r'\+', r'-', r'\.', r'!']
    for char in chars:
        text = text.replace(char.replace('\\', ''), char)
    return text
