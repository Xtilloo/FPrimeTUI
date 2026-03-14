# tests/rag/test_chunker.py
from rag.chunker import chunk_fpp, chunk_markdown, chunk_python, deduplicate


def test_chunk_markdown_splits_on_headers():
    text = "# Title\nIntro text.\n## Section A\nContent A.\n## Section B\nContent B."
    chunks = chunk_markdown(text, source="test.md")
    assert len(chunks) == 3
    assert chunks[0]["chunk_type"] == "markdown"
    assert "Section A" in chunks[1]["text"]


def test_chunk_markdown_includes_metadata():
    text = "## Overview\nSome content here."
    chunks = chunk_markdown(text, source="docs/overview.md")
    assert chunks[0]["source_file"] == "docs/overview.md"
    assert chunks[0]["chunk_type"] == "markdown"


def test_chunk_fpp_splits_on_component_blocks():
    text = 'component A {\n  port p: Fw.Com\n}\ncomponent B {\n  port q: Fw.Com\n}'
    chunks = chunk_fpp(text, source="Comp.fpp")
    assert len(chunks) == 2
    assert chunks[0]["component_name"] == "A"


def test_chunk_python_splits_on_class_and_function():
    text = "class Foo:\n    def bar(self):\n        pass\n\ndef baz():\n    pass\n"
    chunks = chunk_python(text, source="example.py")
    assert len(chunks) == 2


def test_deduplicate_removes_identical_content():
    chunks = [
        {"text": "hello world", "source_file": "a.md", "chunk_type": "markdown"},
        {"text": "hello world", "source_file": "b.md", "chunk_type": "markdown"},
        {"text": "different",   "source_file": "c.md", "chunk_type": "markdown"},
    ]
    result = deduplicate(chunks)
    assert len(result) == 2
