# tests/analysis/test_preprocess.py
from preprocess_responses import extract_signals, make_batches

# --- extract_signals ---

def test_gap_explicit():
    entry = {"response": "This is not in my knowledge base.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_gap"] is True


def test_gap_dont_have():
    entry = {"response": "I don't have enough info to answer that.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_gap"] is True


def test_no_gap():
    entry = {"response": "The answer is that components use port arrays.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_gap"] is False


def test_fpp_block_extracted():
    entry = {"response": "Example:\n```fpp\ncomponent Foo {}\n```\nDone.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_fpp"] is True
    assert s["fpp_blocks"] == ["component Foo {}"]


def test_multiple_fpp_blocks():
    entry = {"response": "```fpp\nmodule A {}\n```\n```fpp\nmodule B {}\n```", "status": "ok"}
    s = extract_signals(entry)
    assert len(s["fpp_blocks"]) == 2


def test_no_fpp():
    entry = {"response": "No code blocks here.", "status": "ok"}
    s = extract_signals(entry)
    assert s["has_fpp"] is False
    assert s["fpp_blocks"] == []


def test_tool_call_detected():
    entry = {
        "response": '```json\n{"tool": "read_file", "path": "Fw/Types/Types.hpp"}\n```',
        "status": "ok",
    }
    s = extract_signals(entry)
    assert s["has_tool_call"] is True
    assert len(s["tool_calls"]) == 1
    assert s["tool_calls"][0]["tool"] == "read_file"


def test_json_block_without_tool_key_ignored():
    entry = {"response": '```json\n{"key": "value"}\n```', "status": "ok"}
    s = extract_signals(entry)
    assert s["has_tool_call"] is False
    assert s["tool_calls"] == []


def test_sources_extracted():
    entry = {
        "response": "Answer.\n\n*Sources: Fw/Types/docs/sdd.md · docs/reference/dictionary.md*",
        "status": "ok",
    }
    s = extract_signals(entry)
    assert s["source_count"] == 2
    assert "Fw/Types/docs/sdd.md" in s["sources_cited"]
    assert "docs/reference/dictionary.md" in s["sources_cited"]


def test_no_sources():
    entry = {"response": "Answer with no sources.", "status": "ok"}
    s = extract_signals(entry)
    assert s["source_count"] == 0
    assert s["sources_cited"] == []


def test_timeout_from_status():
    entry = {"response": "", "status": "timeout"}
    s = extract_signals(entry)
    assert s["timeout"] is True


def test_timeout_from_short_response():
    entry = {"response": "Short.", "status": "ok"}
    s = extract_signals(entry)
    assert s["timeout"] is True  # len("Short.") < 50


def test_no_timeout_normal_response():
    entry = {"response": "A" * 100, "status": "ok"}
    s = extract_signals(entry)
    assert s["timeout"] is False


# --- make_batches ---

def test_make_batches_even():
    items = list(range(50))
    batches = make_batches(items, 25)
    assert len(batches) == 2
    assert len(batches[0]) == 25
    assert len(batches[1]) == 25


def test_make_batches_ragged():
    items = list(range(685))
    batches = make_batches(items, 25)
    assert len(batches) == 28  # 27 full + 1 with 10
    assert len(batches[-1]) == 10


def test_make_batches_empty():
    assert make_batches([], 25) == []


def test_make_batches_smaller_than_size():
    items = list(range(10))
    batches = make_batches(items, 25)
    assert len(batches) == 1
    assert len(batches[0]) == 10


def test_gap_no_false_positive_on_component_description():
    """A response that mentions 'no information' in context should not flag as gap."""
    entry = {
        "response": "The component stores no information in persistent memory and operates statelessly.",
        "status": "ok",
    }
    s = extract_signals(entry)
    assert s["has_gap"] is False


def test_extract_signals_missing_response_key():
    """extract_signals handles missing response key gracefully."""
    entry = {"status": "ok"}  # no "response" key
    s = extract_signals(entry)
    assert s["has_gap"] is False
    assert s["has_fpp"] is False
    assert s["timeout"] is True  # len("") < 50
