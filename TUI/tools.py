import aiofiles
import os
from pathlib import Path

async def execute_read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"Error: File {path} not found."
    
    try:
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
            if len(content) > 100000:
                return content[:100000] + "\n...[TRUNCATED FOR LENGTH]..."
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

async def execute_replace_in_file(path: str, old_content: str, new_content: str) -> str:
    if not os.path.exists(path):
        return f"Error: File {path} not found."
        
    try:
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
            
        if old_content not in content:
            return "Error: Exact match for 'old_content' not found."
        if content.count(old_content) > 1:
            return "Error: 'old_content' matched multiple times. Provide more context."
            
        updated_content = content.replace(old_content, new_content)
        
        async with aiofiles.open(path, mode='w') as f:
            await f.write(updated_content)
            
        return "File updated successfully."
    except Exception as e:
        return f"Error modifying file: {str(e)}"

async def execute_write_file(path: str, content: str) -> str:
    try:
        async with aiofiles.open(path, mode='w') as f:
            await f.write(content)
        return f"File '{os.path.basename(path)}' written successfully."
    except Exception as e:
        return f"Error writing file: {str(e)}"

async def execute_list_directory(path: str) -> str:
    if not os.path.exists(path):
         return f"Error: Directory {path} not found."
    if not os.path.isdir(path):
         return f"Error: Path {path} is not a directory."
    try:
        items = os.listdir(path)
        return "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {str(e)}"

async def execute_grep_docs(query: str, project_root: str = ".") -> str:
    from pathlib import Path
    docs_path = Path(project_root) / "docs"
    if not docs_path.exists():
        return "Error: 'docs/' directory not found at project root."
    results = []
    total_len = 0
    query_lower = query.lower()
    for md_file in docs_path.rglob("*.md"):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            matches_in_file = []
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    matches_in_file.append(f"L{i+1}: {line.strip()}")
            if matches_in_file:
                file_rel = md_file.relative_to(project_root)
                header = f"\n--- {file_rel} ---\n"
                content = "\n".join(matches_in_file)
                entry = header + content
                if total_len + len(entry) > 1000:
                    results.append(entry[:1000 - total_len] + "...[TRUNCATED]...")
                    break
                results.append(entry)
                total_len += len(entry)
        except Exception:
            continue
    if not results:
        return f"No matches found for '{query}' in documentation."
    return "".join(results)

async def execute_create_component(data: dict) -> str:
    """
    Executes fprime-util new --component with non-interactive piped input.
    Ensures the command is run from the correct directory.
    """
    from .shell import run_fprime_command
    
    name = data.get("name", "MyComponent")
    desc = data.get("desc", "F' Component")
    namespace = data.get("namespace", "Components")
    
    # Map friendly names to fprime-util codes
    kind_raw = str(data.get("kind", "1")).lower()
    kind_map = {"active": "1", "passive": "2", "queued": "3", "1": "1", "2": "2", "3": "3"}
    kind = kind_map.get(kind_raw, "1")
    
    commands = "1" # yes
    tlm = "1" # yes
    events = "1" # yes
    prms = "1" # yes
    add_to_cmake = "yes"
    gen_impl = "yes"
    
    # Construct piped input
    # 1: name, 2: desc, 3: ns, 4: kind, 5: cmds, 6: tlm, 7: evts, 8: prms, 9: cmake, 10: impl
    piped_input = f"{name}\n{desc}\n{namespace}\n{kind}\n{commands}\n{tlm}\n{events}\n{prms}\n{add_to_cmake}\n{gen_impl}\n"
    
    # Determine the best CWD. If namespace folder exists, run there.
    project_root = data.get("cwd", ".")
    ns_path = Path(project_root) / namespace
    exec_cwd = str(ns_path) if ns_path.exists() and ns_path.is_dir() else project_root
    
    full_args = f"--component"
    # Use printf for more reliable newline handling in shell pipes
    executable = f"printf '{piped_input}' | fprime-util"
    
    res = await run_fprime_command("new", full_args, cwd=exec_cwd, executable=executable)
    
    if res["exit_code"] == 0:
        return f"SUCCESS: Component '{name}' created in {namespace}."
    else:
        return f"ERROR: Could not create component.\nStderr: {res['stderr']}\nStdout: {res['stdout']}"
