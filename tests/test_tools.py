import pytest
from TUI.tools import execute_read_file

# The character limit defined in TUI/tools.py
TRUNCATION_LIMIT = 100000
TRUNCATION_MESSAGE = "\n...[TRUNCATED FOR LENGTH]..."

@pytest.mark.asyncio
async def test_read_file_truncation(tmp_path):
    """
    Tests that execute_read_file truncates files that are too long.
    """
    large_content = "a" * (TRUNCATION_LIMIT + 1000)
    large_file = tmp_path / "large_file.txt"
    large_file.write_text(large_content)

    # Read the oversized file
    content = await execute_read_file(str(large_file))

    # Verify the content was truncated
    assert len(content) == TRUNCATION_LIMIT + len(TRUNCATION_MESSAGE)
    assert content.startswith("a" * TRUNCATION_LIMIT)
    assert content.endswith(TRUNCATION_MESSAGE)

@pytest.mark.asyncio
async def test_read_file_normal(tmp_path):
    """
    Tests that execute_read_file reads a normal-sized file correctly.
    """
    normal_content = "Hello, this is a test file."
    normal_file = tmp_path / "normal_file.txt"
    normal_file.write_text(normal_content)

    content = await execute_read_file(str(normal_file))

    assert content == normal_content

@pytest.mark.asyncio
async def test_read_file_not_found():
    """
    Tests that execute_read_file returns an error for a non-existent file.
    """
    content = await execute_read_file("/non/existent/path/file.txt")
    assert "Error: File" in content
    assert "not found" in content
