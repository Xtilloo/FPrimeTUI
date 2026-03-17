# tests/analysis/conftest.py
import sys
from pathlib import Path

# Allow tests to import directly from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
