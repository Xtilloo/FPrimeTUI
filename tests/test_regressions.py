import pytest
import os
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
from TUI.app import FPrimeTUI
from textual.widgets import TextArea, OptionList, Markdown
from tests.test_helpers import submit_query

@pytest.mark.asyncio
async def test_regression_autocomplete_tab_behavior():
    """
    REGRESSION: Autocomplete must trigger on '/' and Tab must apply the selection.
    This ensures the keybindings and suggestion logic remain intact.
    """
    app = FPrimeTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        input_area = app.query_one("#ai-input", TextArea)
        input_area.focus()
        
        # 1. Trigger suggestions
        await pilot.press("slash")
        await asyncio.sleep(0.1) 
        await pilot.pause()

        option_list = app.query_one(OptionList)
        assert option_list.display is True
        assert option_list.option_count > 0
        
        # 2. Select and apply with Tab
        await pilot.press("down")
        await pilot.press("tab")
        await pilot.pause()

        # Should have applied the first command (usually /clear or /help)
        assert input_area.text.startswith("/")
        assert input_area.text.endswith(" ")
        assert option_list.display is False

@pytest.mark.asyncio
async def test_regression_slash_command_bypass(mock_ai_client):
    """
    REGRESSION: /commands must bypass AI and execute shell commands directly.
    """
    app = FPrimeTUI()
    app._show_agent_thoughts = True # Crucial: results are thoughts
    
    mock_res = {"exit_code": 0, "stdout": "REGRESSION_TEST_PASSED", "stderr": ""}
    await mock_ai_client.queue_response(["Summary of success."])

    with patch("TUI.app.run_fprime_command", new_callable=AsyncMock) as mock_run, \
         patch("TUI.app.find_fprime_venv", return_value=Path("/dummy/venv")):
        mock_run.return_value = mock_res
        
        async with app.run_test() as pilot:
            # Bypass AI by using a slash command
            await submit_query(pilot, app, "/info")
            
            # Wait for turn processing
            for _ in range(20):
                await pilot.pause(0.1)
                if "REGRESSION_TEST_PASSED" in app.chat_history:
                    break
            
            # Verify shell tool was called directly
            assert mock_run.called
            assert "REGRESSION_TEST_PASSED" in app.chat_history

@pytest.mark.asyncio
async def test_regression_at_file_injection(mock_ai_client, tmp_path):
    """
    REGRESSION: @filename must inject the file content into the AI prompt context.
    """
    app = FPrimeTUI()
    test_file = tmp_path / "regression_context.txt"
    secret_content = "SECRET_TOKEN_12345"
    test_file.write_text(secret_content)
    
    # Switch to tmp_path so @file finding works
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        await mock_ai_client.queue_response(["Acknowledged file."])

        async with app.run_test() as pilot:
            await submit_query(pilot, app, f"Check this: @{test_file.name}")
            
            # Verify AI received the file content in system context
            last_call = mock_ai_client.stream_chat_calls[-1]
            assert secret_content in last_call['system_prompt']
            assert f"FILE: {test_file.name}" in last_call['system_prompt']
    finally:
        os.chdir(old_cwd)

@pytest.mark.asyncio
async def test_regression_ai_turn_lifecycle(mock_ai_client):
    """
    REGRESSION: Core AI-TUI loop: User Input -> AI Stream -> Tool Parse -> Result.
    """
    app = FPrimeTUI()
    app._show_agent_thoughts = True
    
    # 1. AI decides to list directory
    await mock_ai_client.queue_response(['I will check the files. ```json\n{"tool_name": "list_directory", "path": "."}\n```'])
    # 2. AI summarizes after tool result
    await mock_ai_client.queue_response(["I see the files now."])

    with patch("TUI.app.execute_list_directory", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = "file1.txt\nfile2.txt"
        
        async with app.run_test() as pilot:
            await submit_query(pilot, app, "What files are here?")
            
            # Allow multiple turns to process
            for _ in range(20):
                await pilot.pause(0.1)
                if "I see the files now." in app.chat_history:
                    break
            
            assert "I will check the files." in app.chat_history
            assert "[Tool Result]" in app.chat_history

            assert "file1.txt" in app.chat_history
            assert "I see the files now." in app.chat_history

@pytest.mark.asyncio
async def test_regression_tui_mounting_state():
    """
    REGRESSION: Fundamental TUI mounting and focus logic.
    """
    app = FPrimeTUI()
    async with app.run_test() as pilot:
        # Verify initial state
        assert app.query_one("#ai-input").has_focus
        assert app.query_one("#chat-container").display is True
        assert app.query_one("#thinking-indicator").display is False
        
        # Verify status message is present
        # In Textual 0.85+, Markdown content is not easily accessible via attributes
        # but we can verify that a Markdown widget exists in the chat container.
        mdown_widgets = list(app.query(Markdown))
        assert len(mdown_widgets) >= 1
