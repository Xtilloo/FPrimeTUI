import asyncio
from pathlib import Path

async def run_fprime_command(venv_path: Path, command: str, args: str = "", cwd: str = ".", timeout: int = None, executable: str = "fprime-util") -> dict:
    activation_cmd = f"source {venv_path}/bin/activate"
    full_cmd = f"{activation_cmd} && {executable} {command} {args}"
    
    # Debug: Print to console (will show up in the terminal that launched the TUI)
    print(f"DEBUG: Executing command in {cwd}")
    print(f"DEBUG: Full command: {full_cmd}")
    
    try:
        process = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            executable='/bin/bash', # Crucial for 'source' to work
            cwd=cwd
        )

        stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=timeout)
        
        stdout = stdout_data.decode().strip()
        stderr = stderr_data.decode().strip()
        
        print(f"DEBUG: Exit code: {process.returncode}")
        if stderr:
            print(f"DEBUG: Stderr: {stderr[:100]}...")
        
        return {
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr
        }
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds."
        }
