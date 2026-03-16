import pytest

from tests.test_helpers import submit_query
from TUI.app import FPrimeTUI


@pytest.mark.asyncio
async def test_exchange_history_tracks_user_and_assistant(mock_ai_client):
    """exchange_history should record (role, text) tuples for each turn."""
    app = FPrimeTUI()
    async with app.run_test() as pilot:
        assert app.exchange_history == []

        # Simulate a user turn + AI response
        await mock_ai_client.queue_response(["Hello from Mission Control!"])
        await submit_query(pilot, app, "What is F Prime?")
        await pilot.pause()

        assert len(app.exchange_history) >= 2
        assert app.exchange_history[-2] == ("user", "What is F Prime?")
        assert app.exchange_history[-1][0] == "assistant"
        assert "Hello from Mission Control!" in app.exchange_history[-1][1]


@pytest.mark.asyncio
async def test_exchange_history_cleared_on_clear(mock_ai_client):
    """action_clear_chat should reset exchange_history."""
    app = FPrimeTUI()
    async with app.run_test() as pilot:
        await mock_ai_client.queue_response(["test"])
        await submit_query(pilot, app, "test query")
        await pilot.pause()

        app.action_clear_chat()
        assert app.exchange_history == []
