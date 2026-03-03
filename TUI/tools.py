import aiofiles
import os

async def execute_read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"Error: File {path} not found."
    
    try:
        async with aiofiles.open(path, mode='r') as f:
            content = await f.read()
            # Truncation logic if file is too large
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
    """
    Creates or overwrites a file with the given content.
    """
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
    """
    Search for a keyword within the project's docs/ directory.
    Returns a list of files and matching line snippets, capped at 1000 chars.
    """
    from pathlib import Path
    
    docs_path = Path(project_root) / "docs"
    if not docs_path.exists():
        return "Error: 'docs/' directory not found at project root."
        
    results = []
    total_len = 0
    query_lower = query.lower()
    
    # Standard walk to find all markdown files
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
