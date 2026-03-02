import pytest
from TUI.app import FPrimeTUI
from textual.widgets import TextArea

from tests.test_helpers import submit_query

@pytest.mark.asyncio
async def test_reproduce_enter_crash():
    """Reproduces the crash when pressing Enter in the input field."""
    app = FPrimeTUI()
    
    async with app.run_test() as pilot:
        await submit_query(pilot, app, "Hello")
        # Verify it actually triggered the loop and added the message
        assert "User: Hello" in app.chat_history

@pytest.mark.asyncio
async def test_enter_does_nothing_if_empty():
    """Verifies that pressing Enter on empty input does nothing."""
    app = FPrimeTUI()
    async with app.run_test() as pilot:
        await submit_query(pilot, app, "")
        # Should still be the initial message
        assert "> **User:**" not in app.chat_history
