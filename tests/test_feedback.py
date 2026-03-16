import json

import pytest

from TUI.feedback import append_bad_response, append_good_response


@pytest.fixture
def feedback_dir(tmp_path):
    """Create temp directories mimicking the project structure."""
    rag_dir = tmp_path / "TUI" / "rag"
    rag_dir.mkdir(parents=True)
    training_dir = tmp_path / "docs" / "training"
    training_dir.mkdir(parents=True)

    # Create empty templates
    curated = rag_dir / "curated_qa.md"
    curated.write_text("# Curated F' Knowledge Base\n\n---\n")
    jsonl = training_dir / "fine_tuning.jsonl"
    jsonl.write_text("")
    diagnosis = training_dir / "diagnosis_log.md"
    diagnosis.write_text("# Diagnosis Log\n\n## Failures\n\n---\n\n## User-flagged bad responses\n")

    return tmp_path


def test_append_good_response_writes_curated_md(feedback_dir):
    curated_path = feedback_dir / "TUI" / "rag" / "curated_qa.md"
    jsonl_path = feedback_dir / "docs" / "training" / "fine_tuning.jsonl"

    append_good_response(
        question="What is an active component?",
        answer="An active component has its own thread and queue.",
        rag_sources=["Fw/Comp/docs/sdd.md"],
        curated_path=str(curated_path),
        jsonl_path=str(jsonl_path),
    )

    content = curated_path.read_text()
    assert "What is an active component?" in content
    assert "An active component has its own thread and queue." in content
    assert "[H]" in content

    # Check JSONL
    lines = jsonl_path.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["question"] == "What is an active component?"
    assert entry["verified_by"] == "human"
    assert entry["rag_sources"] == ["Fw/Comp/docs/sdd.md"]


def test_append_bad_response_writes_diagnosis_log(feedback_dir):
    diagnosis_path = feedback_dir / "docs" / "training" / "diagnosis_log.md"

    append_bad_response(
        question="What is a port?",
        answer="A port is a USB connector.",
        reason="completely wrong",
        diagnosis_path=str(diagnosis_path),
    )

    content = diagnosis_path.read_text()
    assert "What is a port?" in content
    assert "A port is a USB connector." in content
    assert "completely wrong" in content
    assert "User-flagged bad responses" in content


def test_append_good_response_multiple(feedback_dir):
    curated_path = feedback_dir / "TUI" / "rag" / "curated_qa.md"
    jsonl_path = feedback_dir / "docs" / "training" / "fine_tuning.jsonl"

    for i in range(3):
        append_good_response(
            question=f"Question {i}",
            answer=f"Answer {i}",
            rag_sources=[],
            curated_path=str(curated_path),
            jsonl_path=str(jsonl_path),
        )

    lines = jsonl_path.read_text().strip().split("\n")
    assert len(lines) == 3
