import pytest
import os
from TUI.tools import execute_grep_docs

@pytest.mark.asyncio
async def test_grep_docs_finds_content(tmp_path):
    # Setup: Create a dummy docs folder
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    test_file = docs_dir / "test.md"
    test_file.write_text("The intent is to create a new component using fprime-util new --component.")
    
    # Mock the project root for the tool
    import TUI.tools
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        result = await execute_grep_docs("component")
        assert "test.md" in result
        assert "fprime-util new --component" in result
    finally:
        os.chdir(original_cwd)

@pytest.mark.asyncio
async def test_grep_docs_truncation(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    test_file = docs_dir / "long.md"
    # Create content longer than 1000 chars
    test_file.write_text("Keyword match here. " + ("A" * 1200))
    
    import TUI.tools
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        result = await execute_grep_docs("Keyword")
        assert len(result) <= 1100 # Allow some overhead for headers
        assert "...[TRUNCATED]..." in result
    finally:
        os.chdir(original_cwd)
