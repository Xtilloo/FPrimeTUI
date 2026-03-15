from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.test_helpers import submit_query
from TUI.app import FPrimeTUI


def read_golden_file(path: str) -> str:
    """Helper to read a golden file, normalizing newlines."""
    with open(path) as f:
        return f.read().replace("\r\n", "\n")

@pytest.mark.asyncio
@patch("TUI.app.execute_replace_in_file", new_callable=AsyncMock)
async def test_hitl_golden_output(mock_execute, mock_ai_client, tmp_path):
    """
    Tests the full HITL flow against a static "golden file" to catch UI/text regressions.
    """
    app = FPrimeTUI()
    app._show_agent_thoughts = False

    # Setup a dummy file in a temporary directory
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello") # The old content

    # The mock AI will request to replace content in the file
    tool_call_response = [
        "I will replace the content.",
        "```json\n",
        '{"tool_name": "replace_in_file", "path": "' + str(test_file) + '", "old_content": "Hello", "new_content": "Goodbye"}\n',
        "```"
    ]
    # The mock AI will then confirm the action after user approval
    confirmation_response = ["Okay, I have updated the file as you requested."]

    await mock_ai_client.queue_response(tool_call_response)
    await mock_ai_client.queue_response(confirmation_response)
    mock_execute.return_value = "File updated successfully."

    # The starting `chat_history` in the app has a trailing newline, which we want to match.
    app.chat_history = ""
    async with app.run_test() as pilot:
        await pilot.pause()
        # Re-mount initial message to match golden expectations (includes Mission Control: header)
        await app._mount_ai_turn("# Mission Control Online\nAwaiting command. Use `@file` or `/command`.")

        # 1. User makes a request

        await submit_query(pilot, app, "replace hello with goodbye")
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        # 2. User approves the HITL prompt
        await pilot.pause(0.1) # Extra buffer for state change
        await submit_query(pilot, app, "1")

        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

        # 3. Get the final state of the chat log
        final_chat_log = app.chat_history

        # 4. Read the golden file
        golden_path = Path(__file__).parent / "golden_files" / "hitl_success.md"
        golden_content = read_golden_file(str(golden_path))

        # DEBUG
        print(f"DEBUG: FINAL_CHAT_LOG (repr): {repr(final_chat_log)}")
        print(f"DEBUG: GOLDEN_CONTENT  (repr): {repr(golden_content)}")

        # 5. Compare the final output to the golden file
        # We strip trailing whitespace from both to avoid minor differences.
        assert final_chat_log.strip() == golden_content.strip()
