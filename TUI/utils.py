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
    """Escapes Markdown special characters to render as literal text."""
    # Escape triple backticks first, then single ones
    text = text.replace("```", "\\`\\`\\`").replace("`", "\\`")
    # Escape other common Markdown characters (at line start or anywhere)
    return re.sub(r'([#*_{}\[\]()|+-])', r'\\\1', text)