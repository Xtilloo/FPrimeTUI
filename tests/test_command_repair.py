import pytest
from TUI.controllers.command_guard import CommandGuard
from TUI.controllers.mission import MissionController

def test_repair_fpp_generate():
    guard = CommandGuard()
    tool = {
        "tool_name": "run_fprime_command",
        "executable": "fpp-generate",
        "command": "component",
        "args": "MyComp"
    }
    repaired = guard.repair(tool)
    assert repaired["executable"] == "fprime-util"
    assert repaired["command"] == "new"
    assert "--component MyComp" in repaired["args"]

def test_repair_fprime_util_create():
    guard = CommandGuard()
    tool = {
        "tool_name": "run_fprime_command",
        "executable": "fprime-util",
        "command": "create"
    }
    repaired = guard.repair(tool)
    assert repaired["command"] == "new"

def test_repair_cwd_correction():
    guard = CommandGuard()
    mission = MissionController()
    mission.discovered_project_root = "/path/to/project"
    
    # Mocking os.getcwd to return a child of the project
    import os
    from unittest.mock import patch
    
    with patch("os.getcwd", return_value="/path/to/project/subdir"):
        tool = {
            "tool_name": "run_fprime_command",
            "command": "build",
            "cwd": "."
        }
        repaired = guard.repair(tool, mission)
        # Relpath from /path/to/project/subdir to /path/to/project is ".."
        assert repaired["cwd"] == ".."

def test_repair_cwd_auto_discover(tmp_path):
    guard = CommandGuard()
    mission = MissionController()
    mission.discovered_project_root = str(tmp_path)
    
    # Create a nested component structure
    comp_dir = tmp_path / "Components" / "MyComponent"
    comp_dir.mkdir(parents=True)
    
    import os
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        # AI hallucinated cwd as 'MyComponent' instead of 'Components/MyComponent'
        tool = {
            "tool_name": "run_fprime_command",
            "command": "build",
            "cwd": "MyComponent"
        }
        repaired = guard.repair(tool, mission)
        assert repaired is not None
        assert "Components/MyComponent" in repaired["cwd"]
    finally:
        os.chdir(old_cwd)

def test_validate_build_no_cache(tmp_path):
    guard = CommandGuard()
    mission = MissionController(project_root=str(tmp_path))
    
    tool = {
        "tool_name": "run_fprime_command",
        "command": "build"
    }
    
    # Should fail if build-fprime-automatic-native doesn't exist
    is_valid, err = guard.validate(tool, mission)
    assert is_valid is False
    assert "Build cache not found" in err
    
    # Should pass if it exists
    (tmp_path / "build-fprime-automatic-native").mkdir()
    is_valid, err = guard.validate(tool, mission)
    assert is_valid is True
