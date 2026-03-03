import pytest
import os
from pathlib import Path
from TUI.tools import execute_replace_in_file, execute_list_directory, execute_grep_docs, execute_write_file
from TUI.shell import check_environment, get_project_settings

@pytest.mark.asyncio
async def test_write_file(tmp_path):
    test_file = tmp_path / "new_file.txt"
    res = await execute_write_file(str(test_file), "content here")
    assert "written successfully" in res
    assert test_file.read_text() == "content here"

@pytest.mark.asyncio
async def test_replace_in_file_success(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World\nF' is awesome.")
    
    res = await execute_replace_in_file(str(test_file), "awesome", "incredible")
    assert res == "File updated successfully."
    assert test_file.read_text() == "Hello World\nF' is incredible."

@pytest.mark.asyncio
async def test_replace_in_file_no_match(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World")
    
    res = await execute_replace_in_file(str(test_file), "missing", "new")
    assert "Error: Exact match for 'old_content' not found." in res

@pytest.mark.asyncio
async def test_replace_in_file_multiple_matches(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("repeat repeat repeat")
    
    res = await execute_replace_in_file(str(test_file), "repeat", "once")
    assert "Error: 'old_content' matched multiple times." in res

@pytest.mark.asyncio
async def test_list_directory(tmp_path):
    (tmp_path / "file1.txt").touch()
    (tmp_path / "dir1").mkdir()
    
    res = await execute_list_directory(str(tmp_path))
    assert "file1.txt" in res
    assert "dir1" in res

@pytest.mark.asyncio
async def test_grep_docs(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("F' uses components.\nComponents are good.")
    (docs_dir / "readme.md").write_text("Welcome to F' Mission Control.")
    
    res = await execute_grep_docs("components", project_root=str(tmp_path))
    assert "guide.md" in res
    assert "L1: F' uses components." in res
    assert "readme.md" not in res

@pytest.mark.asyncio
async def test_check_environment(tmp_path):
    # This might be tricky because it runs shell commands
    # We can at least check if it finds settings.ini and project_root correctly
    (tmp_path / "settings.ini").write_text("[fprime]\ndefault_toolchain: native")
    
    res = await check_environment(str(tmp_path))
    assert res["settings.ini"] is True
    assert res["project_root"] == str(tmp_path.absolute())

@pytest.mark.asyncio
async def test_get_project_settings(tmp_path):
    settings_file = tmp_path / "settings.ini"
    settings_file.write_text("default_toolchain: rpi\ndefault_platform: linux")
    
    res = get_project_settings(str(tmp_path))
    assert res["toolchain"] == "rpi"
    assert res["platform"] == "linux"
