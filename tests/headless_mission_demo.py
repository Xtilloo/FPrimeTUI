import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from TUI.app import FPrimeTUI
from tests.test_helpers import submit_query

@pytest.mark.asyncio
async def test_headless_component_creation(mock_ai_client):
    """
    DEMO: A headless test that verifies the full process of making a component.
    """
    app = FPrimeTUI()
    app._show_agent_thoughts = True
    
    # 1. Setup Mock AI: It will provide a Flight Plan and the correct tool call.
    component_name = "BatteryManager"
    await mock_ai_client.queue_response([
        "### FLIGHT PLAN\n1. Create the component directory and files.\n2. Summarize.",
        "\n```json\n",
        '{"tool_name": "run_fprime_command", "command": "new", "args": "--component ' + component_name + '"}',
        "\n```"
    ])
    
    # AI summary turn
    await mock_ai_client.queue_response(["Component " + component_name + " has been created successfully."])

    # 2. Setup Mock Shell: Pretend the command succeeded
    with patch("TUI.app.run_fprime_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0, "stdout": "Component created!", "stderr": "", "recovery_hint": None}
        
        async with app.run_test() as pilot:
            # 3. Simulate User Input
            print("\n[Headless Pilot]: Submitting query 'Create a component named BatteryManager'...")
            await submit_query(pilot, app, "Create a component named BatteryManager")
            
            # 4. Wait for the autonomous loop to complete
            # We wait for the final AI message to appear in the chat history
            success_reached = False
            for _ in range(50):
                await pilot.pause(0.1)
                if "created successfully" in app.chat_history:
                    success_reached = True
                    break
            
            # 5. Verification
            chat_log = app.chat_history
            print("\n[Headless Pilot]: Chat Log Output:\n" + "="*20 + "\n" + chat_log + "\n" + "="*20)
            
            assert success_reached, "Headless mission timed out or failed to reach completion."
            
            # Check Flight Plan
            assert "FLIGHT PLAN" in chat_log
            
            # Check Shell Command execution
            assert "new --component BatteryManager" in chat_log
            assert "COMPLETE" in chat_log
            
            # Check Final Summary
            assert "created successfully" in chat_log
            
            print("\n[Headless Pilot]: Mission Successful! Component creation verified.")
