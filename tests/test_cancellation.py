import pytest
import asyncio
from TUI.app import FPrimeTUI
from textual.events import Key

@pytest.mark.asyncio
async def test_ui_cancel_generation(mock_ai_client):
    """Verifies that Ctrl+C cancels the active AI worker."""
    app = FPrimeTUI()
    app._show_agent_thoughts = True # To see the (Cancelled) message
    
    # Queue a response that will "stream"
    # We add a small sleep in the mock to give us time to cancel
    await mock_ai_client.queue_response(["Chunk 1", "Chunk 2", "Chunk 3"])
    
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#ai-input")
        input_widget = app.query_one("#ai-input")
        await pilot.press(*"Hello")
        
        # Trigger query
        input_widget.on_key(Key("enter", "\r"))
        
        # Give it a tiny bit of time to start
        await asyncio.sleep(0.01)
        
        # Immediately cancel
        app.action_cancel_generation()
        await pilot.pause()
        
        # Verify worker is cancelled (or at least stopped)
        assert app.active_worker.is_cancelled
        
        # Verify cancellation message appears in history
        assert "(Cancelled)" in app.chat_history
        
        # Verify input is re-enabled
        assert not app.query_one("#ai-input").disabled
