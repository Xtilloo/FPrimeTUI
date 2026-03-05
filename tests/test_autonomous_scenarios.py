import pytest
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
from TUI.app import FPrimeTUI
from tests.test_helpers import submit_query

# Note: The 'mock_ai_client' fixture is auto-injected by conftest.py
# and automatically patches the app's AI client.

@pytest.mark.asyncio
async def test_scenario_syntax_interception(mock_ai_client):
    """
    Verifies that the CommandGuard catches bad syntax (e.g. generate component)
    even when passed as a list of args, and prevents shell execution.
    """
    app = FPrimeTUI()
    app._show_agent_thoughts = True # Ensure we can see the [SYNTAX ERROR] tag
    
    # 1. Mock the AI to emit the "bad" command using a list for args
    bad_syntax_tool = {
        "tool_name": "run_fprime_command",
        "command": "generate",
        "args": ["component", "GpsComponent"]
    }
    
    import json
    await mock_ai_client.queue_response([json.dumps(bad_syntax_tool)])
    
    # Also queue a correction turn so the AI loop can finish or retry
    await mock_ai_client.queue_response(["I will correct the syntax now."])

    # 2. Patch the shell runner so we can verify it was NOT called
    with patch("TUI.app.run_fprime_command", new_callable=AsyncMock) as mock_run:
        async with app.run_test() as pilot:
            # 3. Submit a query to trigger the ReAct loop
            await submit_query(pilot, app, "Create a GPS component.")
            
            # Wait for the AI to finish "thinking" and the guard to intercept
            await pilot.pause(0.5)
            await pilot.wait_for_scheduled_animations()
            
            # 4. Assert Interception
            chat_log = app.chat_history
            assert "[SYNTAX ERROR]" in chat_log.upper()
            assert "Did you mean fprime-util new --component?" in chat_log
            
            # 5. Assert the shell command was NEVER executed
            mock_run.assert_not_called()

@pytest.mark.asyncio
async def test_scenario_recovery_hierarchy(mock_ai_client, tmp_path):
    """
    Verifies that the system advances through recovery tiers (Help -> Docs)
    when commands fail consecutively.
    """
    # Create build directory so CommandGuard doesn't block it
    (tmp_path / "build-fprime-automatic-native").mkdir()
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        app = FPrimeTUI()
        app._show_agent_thoughts = True
        
        # 1. Mock the AI sequence: 
        # Turn 1: AI tries build (which we will fail)
        # Turn 2: AI follows Tier 1 directive and runs --help
        # Turn 3: AI follows Tier 2 directive and runs grep_docs
        await mock_ai_client.queue_response(['{"tool_name": "run_fprime_command", "command": "build"}'])
        await mock_ai_client.queue_response(['{"tool_name": "run_fprime_command", "command": "build", "args": "--help"}'])
        await mock_ai_client.queue_response(['{"tool_name": "grep_docs", "query": "build"}'])
        await mock_ai_client.queue_response(['Recovery sequence complete.'])

        # 2. Patch the shell runner to fail BOTH calls to trigger escalation
        with patch("TUI.app.run_fprime_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                {"exit_code": 1, "stdout": "", "stderr": "Build Error", "recovery_hint": None}, # Turn 1
                {"exit_code": 1, "stdout": "", "stderr": "Help Error", "recovery_hint": None}  # Turn 2
            ]
            
            async with app.run_test() as pilot:
                await submit_query(pilot, app, "Build the project.")
                
                # Wait for Turn 1 (failure) and Turn 2 (--help execution)
                for _ in range(30):
                    await pilot.pause(0.1)
                    if "grep_docs" in app.chat_history:
                        break
                
                # 3. Assert Hierarchy Progress
                chat_log = app.chat_history
                print(f"DEBUG CHAT LOG: {chat_log}")
                
                ai_history = app.ai_handler.client.chat_history
                user_msgs = [m["content"] for m in ai_history if m["role"] == "user"]
                
                print(f"DEBUG AI HISTORY: {ai_history}")
                
                # Look for Tier 1 instruction after 1st failure
                assert any("You MUST now run a simplified diagnostic command" in m for m in user_msgs)
                # Look for Tier 2 instruction after 2nd failure
                assert any("You MUST now use 'grep_docs'" in m for m in user_msgs)
                
                # Verify the AI actually followed the tiers
                assistant_msgs = [m["content"] for m in ai_history if m["role"] == "assistant"]
                assert any('"command": "build"' in m for m in assistant_msgs)
                assert any('"args": "--help"' in m for m in assistant_msgs)
                assert any('"tool_name": "grep_docs"' in m for m in assistant_msgs)
    finally:
        os.chdir(original_cwd)

@pytest.mark.asyncio
async def test_scenario_bootstrap_context(mock_ai_client):
    """
    Verifies that the TUI silently probes the environment on startup
    and injects the context into the AI's history.
    """
    app = FPrimeTUI()
    
    # 1. Mock the environment discovery tools
    with patch("TUI.app.find_fprime_venv", return_value=Path("/dummy/venv")), \
         patch("TUI.app.run_fprime_command", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = {"stdout": "Mock Info", "stderr": "", "exit_code": 0}
        
        # 2. Run the app test
        async with app.run_test() as pilot:
            # Wait for the background worker _probe_environment to finish
            await pilot.pause(0.5)
            
            ai_history = app.ai_handler.client.chat_history
            
            # Verify the first message is the system probe
            assert len(ai_history) > 0
            bootstrap_msg = ai_history[0]
            assert bootstrap_msg["role"] == "system"
            assert "Environment probe complete" in bootstrap_msg["content"]
            assert "Project root:" in bootstrap_msg["content"]
