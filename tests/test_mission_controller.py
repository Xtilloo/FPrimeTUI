import pytest
from TUI.controllers.mission import MissionController

def test_mission_controller_initial_state():
    ctrl = MissionController()
    assert ctrl.state["failure_count"] == 0
    assert ctrl.state["recovery_phase"] == "none"

def test_mission_controller_success_resets_failures():
    ctrl = MissionController()
    ctrl.on_tool_fail()
    assert ctrl.state["failure_count"] == 1
    ctrl.on_tool_success()
    assert ctrl.state["failure_count"] == 0
    assert ctrl.state["recovery_phase"] == "none"

def test_mission_controller_recovery_hierarchy():
    ctrl = MissionController()
    
    # 1st Failure: Help phase
    ctrl.on_tool_fail()
    assert ctrl.state["failure_count"] == 1
    assert ctrl.state["recovery_phase"] == "help"
    directive = ctrl.get_recovery_directive({"command": "build"})
    assert "--help" in directive
    
    # 2nd Failure: Docs phase
    ctrl.on_tool_fail()
    assert ctrl.state["failure_count"] == 2
    assert ctrl.state["recovery_phase"] == "docs"
    directive = ctrl.get_recovery_directive({"command": "build"})
    assert "grep_docs" in directive
    
    # 3rd Failure: Fatigue phase (Hard Stop)
    ctrl.on_tool_fail()
    assert ctrl.state["failure_count"] == 3
    assert ctrl.state["recovery_phase"] == "fatigue"
    directive = ctrl.get_recovery_directive({"command": "build"})
    assert "MISSION ABORTED" in directive
