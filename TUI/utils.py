import os
from pathlib import Path

def find_fprime_venv(start_path: Path = None) -> Path | None:
    if start_path is None:
        start_path = Path.cwd()
    current = start_path
    while current != current.parent:
        potential_venv = current / "fprime-venv"
        if potential_venv.is_dir() and (potential_venv / "bin" / "activate").exists():
            return potential_venv
        current = current.parent
    return None