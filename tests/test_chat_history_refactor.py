import pytest
from TUI.app import FPrimeTUI


@pytest.mark.asyncio
async def test_exchange_history_tracks_user_and_assistant(mock_ai_client):
    """exchange_history should record (role, text) tuples for each turn."""
    async with FPrimeTUI().run_test() as pilot:
        app = pilot.app
        assert app.exchange_history == []

        # Simulate a user turn + AI response
        await mock_ai_client.queue_response(["Hello from Mission Control!"])
        from tests.test_helpers import submit_query
        await submit_query(pilot, app, "What is F Prime?")
        await pilot.pause()

        assert len(app.exchange_history) >= 2
        assert app.exchange_history[-2] == ("user", "What is F Prime?")
        assert app.exchange_history[-1][0] == "assistant"
        assert "Hello from Mission Control!" in app.exchange_history[-1][1]


@pytest.mark.asyncio
async def test_exchange_history_cleared_on_clear(mock_ai_client):
    """action_clear_chat should reset exchange_history."""
    async with FPrimeTUI().run_test() as pilot:
        app = pilot.app
        await mock_ai_client.queue_response(["test"])
        from tests.test_helpers import submit_query
        await submit_query(pilot, app, "test query")
        await pilot.pause()

        app.action_clear_chat()
        assert app.exchange_history == []
