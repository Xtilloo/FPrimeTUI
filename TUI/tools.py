import os

import aiofiles


async def execute_read_file(path: str) -> str:
    if not os.path.exists(path):
        return f"Error: File {path} not found."

    try:
        async with aiofiles.open(path) as f:
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
        async with aiofiles.open(path) as f:
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
