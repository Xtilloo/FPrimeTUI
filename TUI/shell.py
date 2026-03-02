import asyncio
import re
import os
from pathlib import Path
from .command_definitions import ERROR_FINGERPRINTS

async def run_fprime_command(command: str, args: str = "", cwd: str = ".", timeout: int = None, executable: str = "fprime-util", venv_path: Path = None) -> dict:
    """Executes an F' command with automatic venv activation."""
    from .utils import find_fprime_venv
    
    actual_venv = venv_path
    if not actual_venv or not (actual_venv / "bin" / "activate").exists():
         actual_venv = find_fprime_venv(Path(cwd))
    
    if not actual_venv:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Error: Could not find fprime-venv in {cwd} or its parents.",
            "recovery_hint": "Use list_directory to find where the F' project root (and fprime-venv) is located."
        }

    activation_cmd = f"source {actual_venv}/bin/activate"
    full_cmd = f"{activation_cmd} && {executable} {command} {args}"
    
    try:
        process = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            executable='/bin/bash',
            cwd=cwd
        )

        stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=timeout)
        
        stdout = stdout_data.decode().strip()
        stderr = stderr_data.decode().strip()
        
        print(f"DEBUG: Exit code: {process.returncode}")
        
        # Apply error fingerprinting
        recovery_hint = None
        if process.returncode != 0:
            recovery_hint = fingerprint_error(stdout + "\n" + stderr)
        
        return {
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "recovery_hint": recovery_hint
        }
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds.",
            "recovery_hint": "Command timed out. This might happen during slow builds or if waiting for input."
        }

def fingerprint_error(output: str) -> str:
    """Scan output for known F' error patterns and return a recovery hint."""
    for fingerprint in ERROR_FINGERPRINTS:
        match = re.search(fingerprint["regex"], output)
        if match:
            if "{0}" in fingerprint["hint"]:
                return fingerprint["hint"].format(*match.groups())
            return fingerprint["hint"]
    return None

async def check_environment(cwd: str = ".") -> dict:
    """Probe the environment for dependencies, including fprime-venv activation."""
    from .utils import find_fprime_venv
    
    venv_path = find_fprime_venv(Path(cwd))
    if not venv_path:
        venv_path = find_fprime_venv() # Fallback
    
    activation_cmd = ""
    if venv_path:
        activation_cmd = f"source {venv_path}/bin/activate && "

    checks = {
        "cmake": f"{activation_cmd}cmake --version",
        "ninja": f"{activation_cmd}ninja --version",
        "fprime-util": f"{activation_cmd}fprime-util -h",
    }
    results = {}
    for name, cmd in checks.items():
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                executable='/bin/bash',
                cwd=cwd
            )
            await process.wait()
            results[name] = process.returncode == 0
        except:
            results[name] = False
    
    # Check for settings.ini
    results["settings.ini"] = (Path(cwd) / "settings.ini").exists() or (Path(cwd).parent / "settings.ini").exists()
    results["venv_path"] = str(venv_path) if venv_path else None
    
    return results

def get_project_settings(cwd: str = ".") -> dict:
    """Extract toolchain and platform from settings.ini if it exists."""
    settings_path = Path(cwd) / "settings.ini"
    if not settings_path.exists():
        settings_path = Path(cwd).parent / "settings.ini" # check parent if in component
    
    settings = {"toolchain": "native", "platform": "native"}
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                content = f.read()
                tc_match = re.search(r"default_toolchain\s*:\s*(\w+)", content)
                if tc_match: settings["toolchain"] = tc_match.group(1)
                p_match = re.search(r"default_platform\s*:\s*(\w+)", content)
                if p_match: settings["platform"] = p_match.group(1)
        except:
            pass
    return settings
