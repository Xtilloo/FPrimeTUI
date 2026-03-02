import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from TUI.shell import fingerprint_error, check_environment, get_project_settings, run_fprime_command

def test_fingerprint_error_cmake_missing():
    output = "bash: cmake: command not found"
    hint = fingerprint_error(output)
    assert "CMake is not installed" in hint

def test_fingerprint_error_settings_missing():
    output = "Could not find settings.ini in project root"
    hint = fingerprint_error(output)
    assert "settings.ini is missing" in hint

def test_fingerprint_error_python_dependency():
    output = "ModuleNotFoundError: No module named 'fprime_gds'"
    hint = fingerprint_error(output)
    assert "Missing Python dependency: fprime_gds" in hint

def test_fingerprint_error_unknown():
    output = "Some random error"
    hint = fingerprint_error(output)
    assert hint is None

@pytest.mark.asyncio
@patch("asyncio.create_subprocess_shell")
async def test_check_environment(mock_shell, tmp_path):
    # Mock subprocesses for cmake, ninja, fprime-util
    mock_process = MagicMock()
    mock_process.wait = AsyncMock()
    mock_process.returncode = 0
    mock_shell.return_value = mock_process
    
    # Create settings.ini
    (tmp_path / "settings.ini").write_text("default_toolchain: native")
    
    results = await check_environment(str(tmp_path))
    assert results["cmake"] is True
    assert results["ninja"] is True
    assert results["fprime-util"] is True
    assert results["settings.ini"] is True

def test_get_project_settings(tmp_path):
    (tmp_path / "settings.ini").write_text("default_toolchain: raspberrypi\ndefault_platform: linux")
    settings = get_project_settings(str(tmp_path))
    assert settings["toolchain"] == "raspberrypi"
    assert settings["platform"] == "linux"

def test_get_project_settings_missing(tmp_path):
    settings = get_project_settings(str(tmp_path))
    assert settings["toolchain"] == "native"
    assert settings["platform"] == "native"

@pytest.mark.asyncio
@patch("asyncio.create_subprocess_shell")
async def test_run_fprime_command_with_hint(mock_shell, tmp_path):
    # Setup a dummy venv so find_fprime_venv (or the manual path) works
    venv_dir = tmp_path / "venv"
    (venv_dir / "bin").mkdir(parents=True)
    (venv_dir / "bin" / "activate").touch()
    
    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b"bash: cmake: command not found"))
    mock_process.returncode = 127
    mock_shell.return_value = mock_process
    
    res = await run_fprime_command("generate", "", str(tmp_path), venv_path=venv_dir)
    assert res["exit_code"] == 127
    assert "CMake is not installed" in res["recovery_hint"]
