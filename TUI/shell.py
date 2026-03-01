import asyncio
from pathlib import Path

async def run_fprime_command(venv_path: Path, command: str, args: str = "") -> dict:
    activation_cmd = f"source {venv_path}/bin/activate"
    full_cmd = f"{activation_cmd} && fprime-util {command} {args}"
    
    process = await asyncio.create_subprocess_shell(
        full_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        executable='/bin/bash' # Crucial for 'source' to work
    )

    stdout_data, stderr_data = await process.communicate()
    
    return {
        "exit_code": process.returncode,
        "stdout": stdout_data.decode().strip(),
        "stderr": stderr_data.decode().strip()
    }
