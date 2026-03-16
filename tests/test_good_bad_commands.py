import json
import os
import pytest
from TUI.app import FPrimeTUI
from tests.test_helpers import submit_query
from command_definitions import TUIMode


@pytest.fixture
def feedback_files(tmp_path):
    """Create temp feedback files."""
    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()
    curated = rag_dir / "curated_qa.md"
    curated.write_text("# Curated F' Knowledge Base\n\n---\n")
    training_dir = tmp_path / "training"
    training_dir.mkdir()
    jsonl = training_dir / "fine_tuning.jsonl"
    jsonl.write_text("")
    diagnosis = training_dir / "diagnosis_log.md"
    diagnosis.write_text("# Diagnosis Log\n\n## Failures\n\n---\n\n## User-flagged bad responses\n")
    return {
        "curated": str(curated),
        "jsonl": str(jsonl),
        "diagnosis": str(diagnosis),
    }


@pytest.mark.asyncio
async def test_good_command_saves_last_exchange(mock_ai_client, feedback_files):
    async with FPrimeTUI().run_test() as pilot:
        app = pilot.app
        app.mode = TUIMode.MISSION_CONTROL
        app._curated_path = feedback_files["curated"]
        app._jsonl_path = feedback_files["jsonl"]
        app._diagnosis_path = feedback_files["diagnosis"]

        # Simulate a Q&A exchange
        await mock_ai_client.queue_response(["Active components have threads."])
        await submit_query(pilot, app, "What is an active component?")
        await pilot.pause()

        # Now run /good
        await mock_ai_client.queue_response([])
        await submit_query(pilot, app, "/good")
        await pilot.pause()

        # Verify curated file was written
        content = open(feedback_files["curated"]).read()
        assert "What is an active component?" in content

        # Verify JSONL was written
        lines = open(feedback_files["jsonl"]).read().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["question"] == "What is an active component?"


@pytest.mark.asyncio
async def test_bad_command_logs_last_exchange(mock_ai_client, feedback_files):
    async with FPrimeTUI().run_test() as pilot:
        app = pilot.app
        app.mode = TUIMode.MISSION_CONTROL
        app._curated_path = feedback_files["curated"]
        app._jsonl_path = feedback_files["jsonl"]
        app._diagnosis_path = feedback_files["diagnosis"]

        # Simulate a Q&A exchange
        await mock_ai_client.queue_response(["A port is a USB connector."])
        await submit_query(pilot, app, "What is a port?")
        await pilot.pause()

        # Now run /bad with reason
        await mock_ai_client.queue_response([])
        await submit_query(pilot, app, "/bad completely wrong")
        await pilot.pause()

        # Verify diagnosis file was written
        content = open(feedback_files["diagnosis"]).read()
        assert "What is a port?" in content
        assert "completely wrong" in content


@pytest.mark.asyncio
async def test_good_command_no_exchange_shows_error(mock_ai_client, feedback_files):
    async with FPrimeTUI().run_test() as pilot:
        app = pilot.app
        app.mode = TUIMode.MISSION_CONTROL
        app._curated_path = feedback_files["curated"]
        app._jsonl_path = feedback_files["jsonl"]
        app._diagnosis_path = feedback_files["diagnosis"]

        # Run /good with no prior exchange
        await mock_ai_client.queue_response([])
        await submit_query(pilot, app, "/good")
        await pilot.pause()

        # Curated file should be unchanged
        content = open(feedback_files["curated"]).read()
        assert content.strip() == "# Curated F' Knowledge Base\n\n---"
