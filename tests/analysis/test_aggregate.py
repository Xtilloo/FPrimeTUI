# tests/analysis/test_aggregate.py
import json
import pytest
from pathlib import Path
from aggregate_analysis import load_results, enrich_entries


def test_load_results_merges_two_batches(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    batch1 = [{"id": "1", "verdict": "PASS", "reason": "correct"}]
    batch2 = [{"id": "2", "verdict": "FAIL", "reason": "wrong"}]
    (results_dir / "accuracy_001.json").write_text(json.dumps(batch1))
    (results_dir / "accuracy_002.json").write_text(json.dumps(batch2))

    results = load_results("accuracy", results_dir)

    assert results["1"] == {"verdict": "PASS", "reason": "correct"}
    assert results["2"] == {"verdict": "FAIL", "reason": "wrong"}


def test_load_results_returns_empty_when_no_files(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    assert load_results("accuracy", results_dir) == {}


def test_load_results_ignores_other_concerns(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "gap_001.json").write_text(
        json.dumps([{"id": "5", "missing_topic": "Foo", "gap_type": "explicit"}])
    )
    results = load_results("accuracy", results_dir)
    assert results == {}

    gap_results = load_results("gap", results_dir)
    assert "5" in gap_results


def test_enrich_entries_merges_all_agents():
    entries = [
        {"id": "1", "category": "Architecture", "question": "Q?", "expected": "E",
         "response": "R", "status": "ok", "timestamp": "2026-03-17T00:00:00"}
    ]
    signals_map = {"1": {"has_gap": False, "has_fpp": False, "has_tool_call": False,
                          "timeout": False, "source_count": 0}}
    accuracy = {"1": {"verdict": "PASS", "reason": "correct"}}

    enriched = enrich_entries(entries, signals_map, accuracy, {}, {}, {}, {})

    assert len(enriched) == 1
    assert enriched[0]["accuracy"] == {"verdict": "PASS", "reason": "correct"}
    assert enriched[0]["gap"] is None
    assert enriched[0]["fpp"] is None
    assert enriched[0]["sources"] is None
    assert enriched[0]["commands"] is None
    assert enriched[0]["signals"]["has_gap"] is False


def test_enrich_entries_all_present_even_if_no_verdict():
    """All entries appear in output, even those not processed by an agent."""
    entries = [
        {"id": str(i), "category": "Modeling", "question": "Q?", "expected": "E",
         "response": "R" * 100, "status": "ok", "timestamp": "2026-03-17T00:00:00"}
        for i in range(1, 4)
    ]
    signals_map = {str(i): {"has_gap": False, "has_fpp": False, "has_tool_call": False,
                             "timeout": False, "source_count": 0} for i in range(1, 4)}
    accuracy = {"2": {"verdict": "PARTIAL", "reason": "incomplete"}}

    enriched = enrich_entries(entries, signals_map, accuracy, {}, {}, {}, {})

    assert len(enriched) == 3
    assert enriched[0]["accuracy"] is None
    assert enriched[1]["accuracy"] == {"verdict": "PARTIAL", "reason": "incomplete"}
    assert enriched[2]["accuracy"] is None
