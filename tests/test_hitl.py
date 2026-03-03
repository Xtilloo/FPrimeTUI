import pytest
import os
from unittest.mock import AsyncMock, patch
from TUI.app import FPrimeTUI
from tests.test_helpers import submit_query

@pytest.mark.asyncio
async def test_hitl_replace_approval(mock_ai_client, tmp_path):
    app = FPrimeTUI()
    app._show_agent_thoughts = True
    test_file = tmp_path / "test.txt"
    test_file.write_text("Old Content")
    
    # AI wants to replace
    await mock_ai_client.queue_response(['```json\n{"tool_name": "replace_in_file", "path": "' + str(test_file) + '", "old_content": "Old", "new_content": "New"}\n```'])
    # After approval, AI summarizes
    await mock_ai_client.queue_response(["Modification complete."])

    async with app.run_test() as pilot:
        await submit_query(pilot, app, "Change Old to New")
        await pilot.pause(0.5)
        
        # Verify it's waiting for approval
        assert app.pending_action is not None
        assert "Action Required" in app.chat_history
        
        # Approve
        await submit_query(pilot, app, "1")
        await pilot.pause(0.5)
        
        assert test_file.read_text() == "New Content"
        assert "Modification complete." in app.chat_history

@pytest.mark.asyncio
async def test_hitl_write_approval(mock_ai_client, tmp_path):
    app = FPrimeTUI()
    app._show_agent_thoughts = True
    test_file = tmp_path / "new.txt"
    
    # AI wants to write
    await mock_ai_client.queue_response(['```json\n{"tool_name": "write_file", "path": "' + str(test_file) + '", "content": "Hello World"}\n```'])
    # After approval, AI summarizes
    await mock_ai_client.queue_response(["File created."])

    async with app.run_test() as pilot:
        await submit_query(pilot, app, "Create new.txt")
        await pilot.pause(0.5)
        
        # Verify it's waiting for approval
        assert app.pending_action is not None
        assert "Action Required" in app.chat_history
        
        # Approve
        await submit_query(pilot, app, "1")
        await pilot.pause(0.5)
        
        assert test_file.read_text() == "Hello World"
        assert "File created." in app.chat_history

@pytest.mark.asyncio
async def test_hitl_decline(mock_ai_client, tmp_path):
    app = FPrimeTUI()
    app._show_agent_thoughts = True
    test_file = tmp_path / "declined.txt"
    
    await mock_ai_client.queue_response(['```json\n{"tool_name": "write_file", "path": "' + str(test_file) + '", "content": "Never"}\n```'])
    await mock_ai_client.queue_response(["I understand you declined."])

    async with app.run_test() as pilot:
        await submit_query(pilot, app, "Create declined.txt")
        await pilot.pause(0.5)
        
        # Decline
        await submit_query(pilot, app, "2")
        await pilot.pause(0.5)
        
        assert not test_file.exists()
        assert "User rejected the edit." in app.chat_history
        assert "I understand you declined." in app.chat_history
