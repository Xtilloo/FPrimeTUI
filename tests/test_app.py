import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from command_definitions import TUIMode
from textual.widgets import OptionList, TextArea

# Note: The 'mock_ai_client' fixture is auto-injected by conftest.py
# and automatically patches the app's AI client.
from tests.test_helpers import submit_query
from TUI.app import FPrimeTUI


@pytest.mark.asyncio
async def test_ui_immediate_user_message(mock_ai_client):
    """Verifies that user message appears immediately in the chat log."""
    app = FPrimeTUI()
    await mock_ai_client.queue_response([""]) # AI gives an empty response

    async with app.run_test() as pilot:
        await submit_query(pilot, app, "Hello")
        assert "User: Hello" in app.chat_history

@pytest.mark.asyncio
async def test_ui_hides_json_streaming(mock_ai_client):
    """Verifies that raw JSON blocks are hidden from display during streaming."""
    app = FPrimeTUI()
    app._show_agent_thoughts = False

    response_chunks = [
        "I will read the file now.\n",
        "```json\n",
        '{"tool_name": "read_file", "path": "test.txt"}\n',
        "```"
    ]
    await mock_ai_client.queue_response(response_chunks)

    async with app.run_test() as pilot:
        await pilot.pause()
        await app._stream_and_handle_tools()
        await pilot.pause()

        chat_log = app.chat_history
        assert "I will read the file now." in chat_log
        assert '{"tool_name": "read_file"' not in chat_log
        assert "```json" not in chat_log

@pytest.mark.asyncio
async def test_slash_command_execution(mock_ai_client):
    """Verifies that / commands execute and show up in history."""
    app = FPrimeTUI()
    app.mode = TUIMode.MISSION_CONTROL # Ensure we are in Mission Control for /build
    mock_res = {"exit_code": 0, "stdout": "Mock Build Success", "stderr": ""}

    # After the command, the app will ask the AI to summarize.
    await mock_ai_client.queue_response(["Build successful."])

    with patch("TUI.app.run_fprime_command", new_callable=AsyncMock) as mock_run, \
         patch("TUI.app.find_fprime_venv", return_value=Path("/dummy/venv")):
        mock_run.return_value = mock_res
        app._show_agent_thoughts = True

        async with app.run_test() as pilot:
            await submit_query(pilot, app, "/build")
            await pilot.wait_for_scheduled_animations()

            chat_log = app.chat_history
            assert "Mock Build Success" in chat_log
            assert "> *Running fprime-util build...*" in chat_log
            assert "Build successful." in chat_log

@pytest.mark.asyncio
async def test_ui_autocomplete_and_apply():
    """Tests that typing a slash command shows autocomplete, and tab applies it."""
    app = FPrimeTUI()
    app.mode = TUIMode.MISSION_CONTROL # Ensure we are in Mission Control for /build
    async with app.run_test() as pilot:
        await pilot.pause()

        # Focus input and press keys
        input_area = app.query_one("#ai-input", TextArea)
        input_area.focus()

        await pilot.press("slash")
        await pilot.press("b")

        # Wait for the Changed event to be processed and OptionList to show
        import asyncio
        await asyncio.sleep(0.1)
        await pilot.pause()

        option_list = app.query_one(OptionList)
        assert option_list.display is True
        assert option_list.option_count > 0
        assert option_list.get_option_at_index(0).id == "/build"

        # Highlight the first option and press tab to apply
        await pilot.press("down")
        await pilot.press("tab")
        await pilot.pause()

        assert input_area.text == "/build "
        assert option_list.display is False

@pytest.mark.asyncio
@patch("TUI.app.execute_replace_in_file", new_callable=AsyncMock)
async def test_ui_hitl_flow(mock_execute, mock_ai_client, tmp_path):
    """Tests the full Human-In-The-Loop flow for file modifications."""
    app = FPrimeTUI()
    app._show_agent_thoughts = True

    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello world")

    tool_call_response = [
        "I will replace the content.\n",
        "```json\n",
        '{"tool_name": "replace_in_file", "path": "' + str(test_file) + '", "old_content": "Hello", "new_content": "Goodbye"}\n',
        "```"
    ]
    confirmation_response = ["Okay, I have updated the file as you requested."]

    await mock_ai_client.queue_response(tool_call_response)
    await mock_ai_client.queue_response(confirmation_response)
    mock_execute.return_value = "File updated successfully."

    async with app.run_test() as pilot:
        await submit_query(pilot, app, "replace hello with goodbye")
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        chat_log = app.chat_history
        assert "Action Required:" in chat_log
        assert "AI wants to modify" in chat_log
        assert "Do you approve? (1: Approve, 2: Decline)" in chat_log

        await submit_query(pilot, app, "1")
        await pilot.wait_for_scheduled_animations()

        mock_execute.assert_called_once_with(str(test_file), "Hello", "Goodbye")

        chat_log = app.chat_history
        assert "User: Approved" in chat_log
        assert "Tool Result:" in chat_log
        assert "File updated successfully." in chat_log
        assert "Okay, I have updated the file" in chat_log

@pytest.mark.asyncio
async def test_ui_at_file_mention_context(mock_ai_client, tmp_path):
    """Tests that using @file adds the file's content to the AI prompt context."""
    app = FPrimeTUI()

    test_file = tmp_path / "test.md"
    file_content = "This is the secret file content."
    test_file.write_text(file_content)
    os.chdir(tmp_path)

    await mock_ai_client.queue_response(["Acknowledged."])

    async with app.run_test() as pilot:
        # User sends a prompt that mentions the file
        prompt = f"Please read this file: @{test_file.name}"
        await submit_query(pilot, app, prompt)

        assert len(mock_ai_client.stream_chat_calls) > 0
        last_call = mock_ai_client.stream_chat_calls[-1]
        system_prompt = last_call['system_prompt']

        assert f"FILE: {test_file.name}" in system_prompt
        assert file_content in system_prompt
