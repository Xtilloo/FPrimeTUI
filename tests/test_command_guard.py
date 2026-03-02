import pytest
from pathlib import Path
from TUI.controllers.command_guard import CommandGuard

class MockMissionState:
    def __init__(self, project_root):
        self.project_root = Path(project_root)

def test_command_guard_hallucination(tmp_path):
    guard = CommandGuard()
    state = MockMissionState(tmp_path)
    
    # AI tries: fprime-util generate component MyComp
    tool_json = {
        "tool_name": "run_fprime_command",
        "executable": "fprime-util",
        "command": "generate",
        "args": "component MyComp"
    }
    
    is_valid, error_msg = guard.validate(tool_json, state)
    
    assert is_valid is False
    assert "Did you mean fprime-util new --component?" in error_msg

def test_command_guard_deprecated(tmp_path):
    guard = CommandGuard()
    state = MockMissionState(tmp_path)
    
    # AI tries: fprime-gen
    tool_json = {
        "tool_name": "run_fprime_command",
        "executable": "fprime-gen",
        "command": "",
        "args": ""
    }
    
    is_valid, error_msg = guard.validate(tool_json, state)
    
    assert is_valid is False
    assert "fprime-gen is deprecated" in error_msg

def test_command_guard_missing_generate(tmp_path):
    guard = CommandGuard()
    state = MockMissionState(tmp_path)
    
    # AI tries: build (but no build directory exists in tmp_path)
    tool_json = {
        "tool_name": "run_fprime_command",
        "executable": "fprime-util",
        "command": "build",
        "args": ""
    }
    
    is_valid, error_msg = guard.validate(tool_json, state)
    
    assert is_valid is False
    assert "run 'generate' first" in error_msg.lower()

def test_command_guard_valid(tmp_path):
    guard = CommandGuard()
    state = MockMissionState(tmp_path)
    
    # Create build directory to satisfy dependency check
    (tmp_path / "build-fprime-automatic-native").mkdir()
    
    tool_json = {
        "tool_name": "run_fprime_command",
        "executable": "fprime-util",
        "command": "build",
        "args": ""
    }
    
    is_valid, error_msg = guard.validate(tool_json, state)
    
    assert is_valid is True
    assert error_msg is None
