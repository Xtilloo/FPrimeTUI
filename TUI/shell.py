import asyncio
import re
import os
import signal
from pathlib import Path
from TUI.command_definitions import ERROR_FINGERPRINTS

# Track the currently active subprocess for cancellation
_active_process = None

async def run_fprime_command(command: str, args: str = "", cwd: str = ".", timeout: int = 300, executable: str = "fprime-util", venv_path: Path = None) -> dict:
    """Executes an F' command with automatic venv activation and process tracking."""
    global _active_process
    from TUI.utils import find_fprime_venv
    
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
    # Ensure non-interactive mode for fprime-util if possible
    full_cmd = f"{activation_cmd} && {executable} {command} {args}"
    
    try:
        # We use a process group (preexec_fn) to ensure we can kill children if needed
        # Note: start_new_session=True is a cleaner way to handle this in modern Python
        process = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            executable='/bin/bash',
            cwd=cwd,
            start_new_session=True 
        )
        _active_process = process

        try:
            stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=timeout)
            stdout = stdout_data.decode().strip()
            stderr = stderr_data.decode().strip()
            return_code = process.returncode
        except asyncio.TimeoutError:
            process.kill() # Call kill() for mock compatibility
            await kill_active_process()
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds.",
                "recovery_hint": "Command timed out. This might happen during slow builds or if waiting for input."
            }
        except asyncio.CancelledError:
            await kill_active_process()
            raise
        finally:
            _active_process = None
        
        # Apply error fingerprinting
        recovery_hint = None
        if return_code != 0:
            recovery_hint = fingerprint_error(stdout + "\n" + stderr)
        
        return {
            "exit_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "recovery_hint": recovery_hint
        }
    except Exception as e:
        if isinstance(e, asyncio.CancelledError): raise
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution Error: {str(e)}",
            "recovery_hint": "System execution error. Check permissions and paths."
        }

async def kill_active_process():
    """Forcefully kills the currently active subprocess and its children."""
    global _active_process
    if _active_process and _active_process.returncode is None:
        try:
            # Kill the entire process group
            os.killpg(os.getpgid(_active_process.pid), signal.SIGKILL)
            await _active_process.wait()
        except:
            pass
    _active_process = None

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
    from TUI.utils import find_fprime_venv
    
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
    
    settings_ini_path = Path(cwd) / "settings.ini"
    project_root = str(Path(cwd).absolute()) if settings_ini_path.exists() else None
    
    if not project_root:
        settings_ini_path = Path(cwd).parent / "settings.ini"
        if settings_ini_path.exists():
            project_root = str(Path(cwd).parent.absolute())

    results["settings.ini"] = project_root is not None
    results["project_root"] = project_root
    results["venv_path"] = str(venv_path) if venv_path else None
    
    return results

def get_project_settings(cwd: str = ".") -> dict:
    """Extract toolchain and platform from settings.ini if it exists."""
    settings_path = Path(cwd) / "settings.ini"
    if not settings_path.exists():
        settings_path = Path(cwd).parent / "settings.ini" 
    
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
