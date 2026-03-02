import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from TUI.utils import find_fprime_venv
from TUI.shell import run_fprime_command

# The 'temp_project' fixture is now in conftest.py and available to all tests.

def test_find_venv_root(temp_project):
    """Finds venv from the project root."""
    assert find_fprime_venv(temp_project) == temp_project / "fprime-venv"

def test_find_venv_nested(temp_project):
    """Finds venv from a nested subdirectory."""
    nested = temp_project / "Components" / "MyComp"
    assert find_fprime_venv(nested) == temp_project / "fprime-venv"

def test_find_venv_relative(temp_project):
    """Finds venv using relative path '.' from a nested directory."""
    nested = temp_project / "Components" / "MyComp"
    import os
    old_cwd = os.getcwd()
    os.chdir(nested)
    try:
        assert find_fprime_venv(Path(".")) == temp_project / "fprime-venv"
    finally:
        os.chdir(old_cwd)

def test_find_venv_missing(tmp_path):
    """Returns None if no venv exists in the tree."""
    assert find_fprime_venv(tmp_path) is None

@pytest.mark.asyncio
async def test_run_command_invalid_venv():
    """Verifies behavior with an invalid venv path (should fail)."""
    # This test doesn't need a real command to run, as it should fail early.
    res = await run_fprime_command(Path("/tmp/nonexistent-venv"), "info", "", ".")
    assert res['exit_code'] != 0
    assert "source" in res['stderr'] or "No such file" in res['stderr']

@pytest.mark.asyncio
@patch("TUI.shell.asyncio.create_subprocess_shell")
async def test_run_command_timeout(mock_create_subprocess):
    """
    Tests that run_fprime_command correctly handles a command that times out.
    """
    # Configure the mock process. kill() is sync, communicate/wait are async.
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
    mock_process.wait = AsyncMock()
    mock_create_subprocess.return_value = mock_process

    # Call the function with a very short timeout
    timeout_duration = 0.1
    res = await run_fprime_command(
        Path("/dummy/venv"), "build", "", ".", timeout=timeout_duration
    )

    # Verify that a timeout error was reported
    assert res['exit_code'] == -1
    assert "Command timed out" in res['stderr']
    assert f"after {timeout_duration} seconds" in res['stderr']
    
    # Verify kill was called
    mock_process.kill.assert_called_once()
