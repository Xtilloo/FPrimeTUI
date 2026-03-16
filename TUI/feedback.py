import json
from datetime import date


def append_good_response(
    question: str,
    answer: str,
    rag_sources: list[str],
    curated_path: str,
    jsonl_path: str,
) -> None:
    """Append a validated Q&A pair to the curated store and fine-tuning dataset."""
    today = date.today().isoformat()

    # Append to curated_qa.md
    entry = (
        f"\n## {question[:80]}\n"
        f"**Verified:** {today} [H]\n"
        f"**Source:** (human-verified)\n\n"
        f"{answer}\n\n---\n"
    )
    with open(curated_path, "a") as f:
        f.write(entry)

    # Append to fine_tuning.jsonl
    record = {
        "question": question,
        "answer": answer,
        "source_files": [],
        "rag_sources": rag_sources,
        "verified_by": "human",
        "date": today,
    }
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(record) + "\n")


def append_bad_response(
    question: str,
    answer: str,
    reason: str,
    diagnosis_path: str,
) -> None:
    """Append a flagged-bad response to the diagnosis log."""
    today = date.today().isoformat()

    entry = (
        f"\n### {question[:80]}\n"
        f"**Flagged:** {today}\n"
        f"**Reason:** {reason or 'No reason given'}\n"
        f"**Response:** {answer[:500]}\n\n"
    )

    # Insert before the end of "User-flagged bad responses" section
    with open(diagnosis_path, "a") as f:
        f.write(entry)
