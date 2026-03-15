# fprime-tui RAG System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fully local, offline RAG knowledge layer to fprime-tui so that qwen3:8b (and similar small models) can answer fprime questions with expert-level accuracy, in a single LLM call per query.

**Architecture:** An offline indexing script fetches fprime sources, chunks them along semantic boundaries, embeds with `nomic-embed-text`, and stores in a local ChromaDB + BM25 index. At query time, hybrid retrieval (dense + keyword) merges results via Reciprocal Rank Fusion, injects the top-3 chunks into the existing context mechanism, and makes a single LLM call. Sources are appended as a muted footnote after the LLM response.

**Tech Stack:** Python, ChromaDB (embedded), rank-bm25, ollama (nomic-embed-text), requests, beautifulsoup4, gitpython

---

## Critical Project Context

### PYTHONPATH and module layout

The `Makefile` runs both the TUI and tests with `PYTHONPATH=./TUI`:

```makefile
TUI:  @PYTHONPATH=./TUI $(PYTHON) TUI/app.py
test: @PYTHONPATH=./TUI $(PYTHON) -m pytest tests/
```

**Consequence:** `rag/` must live inside `TUI/`, not at the project root. An `import rag.retriever` in `app.py` resolves to `TUI/rag/retriever.py`. The project-root `rag/` location in the original plan would silently fail at runtime.

### Existing context injection mechanism

`TUI/fprime_ai_client.py::_get_system_prompt()` already handles external context:

```python
if context:
    prompt += f"\n### CURRENT FILE CONTEXT ###\n{context}\n###########################\n"
```

This is the hook used by `@file` mentions today. RAG context goes through the same path, prepended to `extra_ctx` in `_process_standard_query()` with its own label (`### RELEVANT F' KNOWLEDGE BASE ###`). The system prompt in `_get_system_prompt()` needs one line restored to instruct the model to prioritize the knowledge base (was deleted in branch cleanup).

### Exact integration point

**File:** `TUI/app.py`
**Function:** `_process_standard_query()` (currently line 254)

RAG enrichment is injected here, before `self.ai_client.add_message("user", user_query)`. The existing `extra_ctx` variable (used for `@file` file contents) is extended with the RAG context string.

### Sources rendering

There is no `render_footer()` primitive. After `await self._stream_and_handle_tools(extra_ctx)` returns, call `self._add_to_chat_history()` with the sources footnote — the same method used throughout `app.py` for all chat content.

### Mode guard

RAG enrichment should only run in `MISSION_CONTROL` mode. Academy mode is for teaching and does not benefit from injected technical context.

### `build_prompt()` is NOT used in TUI integration

The RAG `prompt.py` module exists as a standalone utility (useful for CLI/batch use), but the TUI integration does **not** call `build_prompt()` — the existing system prompt in `fprime_ai_client.py` already handles LLM instructions. Only the `answer_context` string from the retriever is injected into `extra_ctx`.

### Test compatibility

Existing TUI tests (`tests/test_app.py`) mock `FPrimeAIClient` via `conftest.py`. The RAG integration is wrapped in a `try/except FileNotFoundError`, so tests continue passing even when no index exists. No changes to `conftest.py` are needed.

---

## File Structure

```
fprime-tui/
├── TUI/
│   ├── app.py                  # Modified: RAG enrichment in _process_standard_query()
│   ├── fprime_ai_client.py     # Modified: restore knowledge-base instruction in system prompt
│   └── rag/
│       ├── __init__.py
│       ├── chunker.py          # Semantic boundary chunking + deduplication
│       ├── retriever.py        # Hybrid BM25 + ChromaDB search + RRF merge
│       ├── prompt.py           # Standalone prompt template (not used by TUI directly)
│       ├── indexer.py          # CLI setup script — run once by user
│       └── db/                 # ChromaDB + BM25 pickle (gitignored)
├── tests/
│   └── rag/
│       ├── __init__.py
│       ├── test_chunker.py
│       ├── test_retriever.py
│       └── test_prompt.py
└── .gitignore                  # Add TUI/rag/db/ and TUI/rag/raw/
```

---

## Chunk 1: Project scaffolding and dependencies

### Task 1: Dependencies and .gitignore

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Add RAG dependencies to requirements.txt**

Append to `requirements.txt` under a new `# --- RAG ---` section:

```
# --- RAG ---
chromadb>=0.5.0
rank-bm25>=0.2.2
requests>=2.31.0
beautifulsoup4>=4.12.0
gitpython>=3.1.40
```

- [ ] **Step 2: Add db and raw directories to .gitignore**

Append to `.gitignore`:
```
TUI/rag/db/
TUI/rag/raw/
```

- [ ] **Step 3: Install dependencies**

```bash
./venv/bin/pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt .gitignore
git commit -m "feat(rag): add dependencies and gitignore entries"
```

---

### Task 2: Package init

**Files:**
- Create: `TUI/rag/__init__.py`
- Create: `tests/rag/__init__.py`

- [ ] **Step 1: Create empty init files**

```python
# TUI/rag/__init__.py  (empty)
# tests/rag/__init__.py  (empty)
```

- [ ] **Step 2: Commit**

```bash
git add TUI/rag/__init__.py tests/rag/__init__.py
git commit -m "feat(rag): scaffold package structure"
```

---

## Chunk 2: Chunker

### Task 3: Semantic chunker with deduplication

**Files:**
- Create: `TUI/rag/chunker.py`
- Create: `tests/rag/test_chunker.py`

The chunker splits source text along semantic boundaries and deduplicates by content hash before returning chunks. This prevents identical README content (which appears in both the GitHub repo and docs site) from inflating the index.

- [ ] **Step 1: Write failing tests**

```python
# tests/rag/test_chunker.py
import pytest
from rag.chunker import chunk_markdown, chunk_fpp, chunk_python, deduplicate

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
make test 2>&1 | grep -A 5 "test_chunker"
```

Expected: `ModuleNotFoundError` or similar — chunker doesn't exist yet.

- [ ] **Step 3: Implement chunker**

```python
# TUI/rag/chunker.py
import re
import hashlib

TARGET_TOKENS = 300
CHARS_PER_TOKEN = 4  # rough estimate


def _truncate(text: str, max_chars: int = TARGET_TOKENS * CHARS_PER_TOKEN) -> str:
    return text[:max_chars]


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split markdown on ## headers. Each section becomes one chunk."""
    sections = re.split(r'(?=^#{1,2} )', text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        chunks.append({
            "text": _truncate(section),
            "source_file": source,
            "chunk_type": "markdown",
            "component_name": "",
        })
    return chunks


def chunk_fpp(text: str, source: str) -> list[dict]:
    """Split .fpp files on component/port/command block boundaries."""
    pattern = re.compile(
        r'((?:active\s+|passive\s+|queued\s+)?(?:component|port|command)\s+(\w+)\s*\{[^}]*\})',
        re.DOTALL
    )
    chunks = []
    for match in pattern.finditer(text):
        block = match.group(1).strip()
        name = match.group(2)
        chunks.append({
            "text": _truncate(block),
            "source_file": source,
            "chunk_type": "fpp_block",
            "component_name": name,
        })
    if not chunks:
        # Fallback: treat whole file as one chunk
        chunks.append({
            "text": _truncate(text),
            "source_file": source,
            "chunk_type": "fpp_block",
            "component_name": "",
        })
    return chunks


def chunk_python(text: str, source: str) -> list[dict]:
    """Split Python files at class and top-level function boundaries."""
    pattern = re.compile(r'(?=^(?:class |def )\w)', re.MULTILINE)
    sections = pattern.split(text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        chunks.append({
            "text": _truncate(section),
            "source_file": source,
            "chunk_type": "python",
            "component_name": "",
        })
    return chunks


def deduplicate(chunks: list[dict]) -> list[dict]:
    """Remove chunks with identical text content using SHA-256 hashing."""
    seen = set()
    result = []
    for chunk in chunks:
        h = hashlib.sha256(chunk["text"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            result.append(chunk)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
make test 2>&1 | grep -A 5 "test_chunker"
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/chunker.py tests/rag/test_chunker.py
git commit -m "feat(rag): implement semantic chunker with deduplication"
```

---

## Chunk 3: Retriever

### Task 4: Hybrid retriever with RRF

**Files:**
- Create: `TUI/rag/retriever.py`
- Create: `tests/rag/test_retriever.py`

The retriever exposes one public function: `query(text: str) -> dict` returning `{"answer_context": str, "sources": list[str]}`. The TUI imports only this. Internals (ChromaDB, BM25) are fully encapsulated.

- [ ] **Step 1: Write failing tests**

```python
# tests/rag/test_retriever.py
import pytest
from rag.retriever import reciprocal_rank_fusion, format_context

def test_rrf_merges_two_lists():
    dense = ["a", "b", "c"]
    sparse = ["b", "c", "a"]
    result = reciprocal_rank_fusion(dense, sparse)
    # "b" appears at rank 2 and 1 — should score highest
    assert result[0] == "b"

def test_rrf_handles_disjoint_lists():
    dense = ["a", "b"]
    sparse = ["c", "d"]
    result = reciprocal_rank_fusion(dense, sparse)
    assert len(result) == 4

def test_rrf_deduplicates_ids():
    dense = ["a", "a", "b"]
    sparse = ["a", "b"]
    result = reciprocal_rank_fusion(dense, sparse)
    assert result.count("a") == 1

def test_format_context_produces_labeled_blocks():
    chunks = [
        {"text": "Port definitions here.", "source_file": "Fw/Com.fpp", "chunk_type": "fpp_block"},
        {"text": "How to connect.", "source_file": "docs/guide.md", "chunk_type": "markdown"},
    ]
    context = format_context(chunks)
    assert "[SOURCE: Fw/Com.fpp | type: fpp_block]" in context
    assert "Port definitions here." in context
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
make test 2>&1 | grep -A 5 "test_retriever"
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement retriever**

```python
# TUI/rag/retriever.py
import os
import pickle
import chromadb
from rank_bm25 import BM25Okapi

DB_PATH = os.path.join(os.path.dirname(__file__), "db")
BM25_PATH = os.path.join(DB_PATH, "bm25.pkl")
TOP_K = 8
FINAL_K = 3
RRF_K = 60  # standard constant


def reciprocal_rank_fusion(dense_ids: list[str], sparse_ids: list[str]) -> list[str]:
    """Merge two ranked lists using Reciprocal Rank Fusion. Returns deduplicated ranked IDs."""
    scores: dict[str, float] = {}
    for rank, doc_id in enumerate(dense_ids):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (RRF_K + rank + 1)
    for rank, doc_id in enumerate(sparse_ids):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (RRF_K + rank + 1)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into labeled context blocks for the prompt."""
    blocks = []
    for chunk in chunks:
        header = f"[SOURCE: {chunk['source_file']} | type: {chunk['chunk_type']}]"
        blocks.append(f"{header}\n{chunk['text']}")
    return "\n\n".join(blocks)


def _load_index():
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection("fprime")
    with open(BM25_PATH, "rb") as f:
        bm25_data = pickle.load(f)
    return collection, bm25_data


def query(text: str) -> dict:
    """
    Public interface for the TUI.
    Returns {"answer_context": str, "sources": list[str]}
    Raises FileNotFoundError if index has not been built yet.
    """
    if not os.path.exists(BM25_PATH):
        raise FileNotFoundError(
            "RAG index not found. Run: python -m rag.indexer"
        )

    collection, bm25_data = _load_index()
    all_chunks: dict[str, dict] = bm25_data["chunks"]   # id -> chunk dict
    bm25: BM25Okapi = bm25_data["bm25"]
    chunk_ids: list[str] = bm25_data["ids"]

    # Dense retrieval
    dense_results = collection.query(
        query_texts=[text],
        n_results=min(TOP_K, collection.count()),
    )
    dense_ids = dense_results["ids"][0]

    # Sparse retrieval (BM25)
    tokenized = text.lower().split()
    scores = bm25.get_scores(tokenized)
    top_sparse_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:TOP_K]
    sparse_ids = [chunk_ids[i] for i in top_sparse_indices]

    # Merge via RRF, take top FINAL_K
    merged_ids = reciprocal_rank_fusion(dense_ids, sparse_ids)[:FINAL_K]

    # Fetch full chunk data
    top_chunks = [all_chunks[cid] for cid in merged_ids if cid in all_chunks]

    return {
        "answer_context": format_context(top_chunks),
        "sources": [c["source_file"] for c in top_chunks],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
make test 2>&1 | grep -A 5 "test_retriever"
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/retriever.py tests/rag/test_retriever.py
git commit -m "feat(rag): implement hybrid retriever with RRF merge"
```

---

## Chunk 4: Prompt builder

### Task 5: Prompt assembly (standalone utility)

**Files:**
- Create: `TUI/rag/prompt.py`
- Create: `tests/rag/test_prompt.py`

> **Note:** This module is a standalone utility for CLI/batch use. The TUI integration does NOT call `build_prompt()` — it injects RAG context directly into `extra_ctx` (see Task 7). `build_prompt()` exists for scripts and future non-TUI consumers of the retriever.

- [ ] **Step 1: Write failing tests**

```python
# tests/rag/test_prompt.py
from rag.prompt import build_prompt

def test_build_prompt_includes_context_and_query():
    context = "[SOURCE: Fw/Com.fpp | type: fpp_block]\nPort stuff."
    prompt = build_prompt(context=context, query="What is a port?")
    assert "What is a port?" in prompt
    assert "Fw/Com.fpp" in prompt

def test_build_prompt_includes_system_instruction():
    prompt = build_prompt(context="ctx", query="q")
    assert "fprime expert" in prompt.lower()
    assert "ONLY the context" in prompt

def test_build_prompt_empty_context_still_valid():
    prompt = build_prompt(context="", query="What is fprime?")
    assert "What is fprime?" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
make test 2>&1 | grep -A 5 "test_prompt"
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement prompt builder**

```python
# TUI/rag/prompt.py

SYSTEM = (
    "You are an fprime expert assistant. "
    "Answer using ONLY the context below. "
    "Cite sources by filename in your answer. "
    "If the context does not contain enough information to answer, say so clearly."
)


def build_prompt(context: str, query: str) -> str:
    """Assemble the full prompt string for the LLM."""
    return f"{SYSTEM}\n\n{context}\n\nQuestion: {query}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
make test 2>&1 | grep -A 5 "test_prompt"
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add TUI/rag/prompt.py tests/rag/test_prompt.py
git commit -m "feat(rag): implement standalone prompt builder"
```

---

## Chunk 5: Indexer

### Task 6: One-time indexing script

**Files:**
- Create: `TUI/rag/indexer.py`

The indexer is a CLI script, not imported by the TUI. It writes to `TUI/rag/db_tmp/`, then atomically swaps to `TUI/rag/db/` on success, and deletes `db_tmp/` on failure. This prevents a corrupt half-built index.

- [ ] **Step 1: Implement indexer**

```python
# TUI/rag/indexer.py
"""
Run once to build the RAG index:
    python -m rag.indexer

Requires ollama running with nomic-embed-text pulled:
    ollama pull nomic-embed-text
"""

import os
import sys
import shutil
import pickle
import hashlib
import requests
from pathlib import Path
from git import Repo
from bs4 import BeautifulSoup
import chromadb
from rank_bm25 import BM25Okapi

from rag.chunker import chunk_markdown, chunk_fpp, chunk_python, deduplicate

DB_PATH = Path(__file__).parent / "db"
RAW_PATH = Path(__file__).parent / "raw"

SOURCES = {
    "github": "https://github.com/nasa/fprime.git",
    "docs": "https://fprime.jpl.nasa.gov",
    "fprime_tools": "https://github.com/fprime-community/fprime-tools.git",
}


def preflight_check():
    """Verify ollama is running and nomic-embed-text is available."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        if not any("nomic-embed-text" in m for m in models):
            print("ERROR: nomic-embed-text not found. Run: ollama pull nomic-embed-text")
            sys.exit(1)
    except requests.ConnectionError:
        print("ERROR: ollama not running. Start it with: ollama serve")
        sys.exit(1)
    print("✓ ollama ready with nomic-embed-text")


def fetch_github(url: str, dest: Path):
    if dest.exists():
        print(f"  Using cached {dest.name}")
        return
    print(f"  Cloning {url} ...")
    Repo.clone_from(url, dest, depth=1)


def fetch_docs(base_url: str, dest: Path):
    """Scrape docs site pages to markdown-like text files."""
    dest.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(base_url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n")
        (dest / "index.md").write_text(text)
        print(f"  Fetched {base_url}")
    except Exception as e:
        print(f"  WARN: Could not fetch docs: {e}")


def collect_chunks() -> list[dict]:
    """Walk raw sources and produce all chunks."""
    all_chunks = []

    # fprime GitHub repo
    repo_path = RAW_PATH / "fprime"
    for ext, fn in [(".md", chunk_markdown), (".fpp", chunk_fpp), (".py", chunk_python)]:
        for f in repo_path.rglob(f"*{ext}"):
            try:
                text = f.read_text(errors="ignore")
                rel = str(f.relative_to(repo_path))
                all_chunks.extend(fn(text, source=rel))
            except Exception:
                pass

    # docs site
    docs_path = RAW_PATH / "docs"
    for f in docs_path.rglob("*.md"):
        text = f.read_text(errors="ignore")
        all_chunks.extend(chunk_markdown(text, source=f"docs/{f.name}"))

    # fprime-tools
    tools_path = RAW_PATH / "fprime-tools"
    for ext, fn in [(".md", chunk_markdown), (".py", chunk_python)]:
        for f in tools_path.rglob(f"*{ext}"):
            try:
                text = f.read_text(errors="ignore")
                rel = f"fprime-tools/{f.relative_to(tools_path)}"
                all_chunks.extend(fn(text, source=rel))
            except Exception:
                pass

    return deduplicate(all_chunks)


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Call ollama embed endpoint for a batch of texts."""
    resp = requests.post(
        "http://localhost:11434/api/embed",
        json={"model": "nomic-embed-text", "input": texts},
        timeout=60,
    )
    return resp.json()["embeddings"]


def build_index(chunks: list[dict], db_path: Path):
    """Write ChromaDB + BM25 index to db_path."""
    db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection("fprime")

    chunk_map = {}
    ids, texts, metadatas = [], [], []

    BATCH = 32
    for i, chunk in enumerate(chunks):
        cid = hashlib.sha256(chunk["text"].encode()).hexdigest()[:16]
        chunk_map[cid] = chunk
        ids.append(cid)
        texts.append(chunk["text"])
        metadatas.append({
            "source_file": chunk["source_file"],
            "chunk_type": chunk["chunk_type"],
            "component_name": chunk.get("component_name", ""),
        })

        if len(ids) == BATCH or i == len(chunks) - 1:
            embs = embed_batch(texts)
            collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embs)
            print(f"  Indexed {i+1}/{len(chunks)} chunks", end="\r")
            ids, texts, metadatas = [], [], []

    print()

    # BM25
    tokenized = [c["text"].lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized)
    all_ids = [hashlib.sha256(c["text"].encode()).hexdigest()[:16] for c in chunks]
    bm25_data = {"bm25": bm25, "ids": all_ids, "chunks": chunk_map}
    with open(db_path / "bm25.pkl", "wb") as f:
        pickle.dump(bm25_data, f)


def main():
    print("fprime-tui RAG Indexer")
    print("======================")

    preflight_check()

    RAW_PATH.mkdir(parents=True, exist_ok=True)
    print("\n[1/3] Fetching sources...")
    fetch_github(SOURCES["github"], RAW_PATH / "fprime")
    fetch_github(SOURCES["fprime_tools"], RAW_PATH / "fprime-tools")
    fetch_docs(SOURCES["docs"], RAW_PATH / "docs")

    print("\n[2/3] Chunking and deduplicating...")
    chunks = collect_chunks()
    print(f"  {len(chunks)} unique chunks ready")

    print("\n[3/3] Embedding and indexing...")
    tmp_path = DB_PATH.parent / "db_tmp"
    try:
        build_index(chunks, tmp_path)
        if DB_PATH.exists():
            shutil.rmtree(DB_PATH)
        tmp_path.rename(DB_PATH)
        print(f"\n✓ Index built at {DB_PATH}")
    except Exception as e:
        shutil.rmtree(tmp_path, ignore_errors=True)
        print(f"\nERROR: Indexing failed and was rolled back: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test the indexer (manual — requires ollama)**

```bash
ollama pull nomic-embed-text
PYTHONPATH=./TUI ./venv/bin/python -m rag.indexer
```

Expected: progress output, no errors, `TUI/rag/db/` directory created with ChromaDB files and `bm25.pkl`.

- [ ] **Step 3: Verify index is not committed**

```bash
git status
```

Expected: `TUI/rag/db/` and `TUI/rag/raw/` do NOT appear as untracked files.

- [ ] **Step 4: Commit**

```bash
git add TUI/rag/indexer.py
git commit -m "feat(rag): implement one-time indexing script with atomic write"
```

---

## Chunk 6: TUI integration

### Task 7: Wire retriever into _process_standard_query()

**Files:**
- Modify: `TUI/app.py`
- Modify: `TUI/fprime_ai_client.py`

#### Part A: Restore knowledge-base instruction in system prompt

In `TUI/fprime_ai_client.py::_get_system_prompt()`, the MISSION_CONTROL personality block originally referenced the RAG knowledge base. This line was removed in branch cleanup and must be restored.

Find in the MISSION_CONTROL personality block:
```python
"You are Mission Control, an autonomous, Senior Principal Flight Software Engineer at NASA JPL specializing in the F' (F Prime) framework. You assist developers directly within their terminal.\n\n"
"You have access to the user's local file system and build environment through specific Tools.\n\n"
```

Change to:
```python
"You are Mission Control, an autonomous, Senior Principal Flight Software Engineer at NASA JPL specializing in the F' (F Prime) framework. You assist developers directly within their terminal.\n\n"
"You are an absolute expert in F'. If provided with a '### RELEVANT F' KNOWLEDGE BASE ###' section, treat it as the authoritative source for F' architecture, standards, and code structure.\n\n"
"You have access to the user's local file system and build environment through specific Tools.\n\n"
```

#### Part B: Inject RAG context in _process_standard_query()

In `TUI/app.py::_process_standard_query()`, the current function body is:

```python
async def _process_standard_query(self, user_query: str):
    self.tool_call_depth = 0
    if not self.query_history or self.query_history[-1] != user_query:
        self.query_history.append(user_query)
    self.history_index = -1
    self._prepare_for_generation()
    await self._mount_user_turn(user_query)

    # 1. Get Manual File Mentions
    mentions = re.findall(r"@([\w./-]+)", user_query)
    extra_ctx = ""
    for filename in mentions:
        file_path = Path(filename)
        if file_path.exists() and file_path.is_file():
            try:
                extra_ctx += f"\nFILE: {filename}\n---\n{file_path.read_text()}\n---\n"
            except Exception:
                pass
    self.ai_client.add_message("user", user_query)
    await self._stream_and_handle_tools(extra_ctx)
```

Replace with:

```python
async def _process_standard_query(self, user_query: str):
    self.tool_call_depth = 0
    if not self.query_history or self.query_history[-1] != user_query:
        self.query_history.append(user_query)
    self.history_index = -1
    self._prepare_for_generation()
    await self._mount_user_turn(user_query)

    # 1. Get Manual File Mentions
    mentions = re.findall(r"@([\w./-]+)", user_query)
    extra_ctx = ""
    for filename in mentions:
        file_path = Path(filename)
        if file_path.exists() and file_path.is_file():
            try:
                extra_ctx += f"\nFILE: {filename}\n---\n{file_path.read_text()}\n---\n"
            except Exception:
                pass

    # 2. RAG enrichment (Mission Control mode only)
    rag_sources: list[str] = []
    if self.mode == TUIMode.MISSION_CONTROL:
        try:
            import asyncio
            from rag.retriever import query as rag_query
            rag_result = await asyncio.to_thread(rag_query, user_query)
            if rag_result["answer_context"]:
                extra_ctx += f"\n\n### RELEVANT F' KNOWLEDGE BASE ###\n{rag_result['answer_context']}\n###################################\n"
                rag_sources = rag_result["sources"]
        except FileNotFoundError:
            pass  # Index not built yet — proceed with plain LLM call

    self.ai_client.add_message("user", user_query)
    await self._stream_and_handle_tools(extra_ctx)

    # 3. Append sources footnote after AI response completes
    if rag_sources:
        source_lines = " · ".join(rag_sources)
        self._add_to_chat_history(f"\n\n*Sources: {source_lines}*\n")
```

- [ ] **Step 1: Apply Part A — restore knowledge-base instruction in `fprime_ai_client.py`**

- [ ] **Step 2: Apply Part B — inject RAG in `_process_standard_query()` in `app.py`**

- [ ] **Step 3: Run existing test suite to check for regressions**

```bash
make test
```

Expected: all pre-existing tests PASS. The `FileNotFoundError` try/except in step 2 ensures tests pass when no index exists.

- [ ] **Step 4: Manual integration test (requires index built from Task 6)**

Start the TUI and ask: `"What is an ActiveComponent in fprime?"`

Expected: answer followed by `*Sources: <filename> · <filename>*`.

- [ ] **Step 5: Commit**

```bash
git add TUI/app.py TUI/fprime_ai_client.py
git commit -m "feat(rag): wire RAG retriever into TUI Mission Control chat handler"
```

---

## Chunk 7: Full test suite

### Task 8: Run all tests

- [ ] **Step 1: Run RAG-specific tests**

```bash
PYTHONPATH=./TUI ./venv/bin/python -m pytest tests/rag/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run full suite — verify no regressions**

```bash
make test
```

Expected: all pre-existing tests PASS (lint + pytest).

- [ ] **Step 3: Update AGENT_MAP.md**

Add the new RAG module to the map. See the "New: RAG Layer" section to add under Core Architecture.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat(rag): complete RAG system — all tests passing"
```

---

## AGENT_MAP.md additions

Add the following section to `AGENT_MAP.md` after "### 2. The Voice":

```markdown
### 2.5 The Knowledge Layer: `TUI/rag/`
- **Role**: Offline retrieval-augmented generation for F' domain knowledge.
- **Key Files**:
    - `chunker.py`: Splits `.md`, `.fpp`, and `.py` source files into semantic chunks with SHA-256 deduplication.
    - `retriever.py`: Hybrid BM25 + ChromaDB dense search, merged via Reciprocal Rank Fusion. Public interface: `query(text) -> {answer_context, sources}`.
    - `indexer.py`: One-time CLI script (`python -m rag.indexer`) that clones fprime repos, embeds via `nomic-embed-text`, and writes `TUI/rag/db/`.
    - `prompt.py`: Standalone prompt builder for CLI/batch use (not used by TUI directly).
- **Integration Point**: `app.py::_process_standard_query()` — RAG context is injected into `extra_ctx` before the Ollama call, Mission Control mode only.
- **Index location**: `TUI/rag/db/` (gitignored). Must be built by user before RAG activates.
```

---

## Configuration reference

| Variable | Location | Default | Notes |
|---|---|---|---|
| `TOP_K` | `TUI/rag/retriever.py` | 8 | Candidates per retrieval method |
| `FINAL_K` | `TUI/rag/retriever.py` | 3 | Chunks injected into prompt |
| `TARGET_TOKENS` | `TUI/rag/chunker.py` | 300 | Target chunk size |
| `BATCH` | `TUI/rag/indexer.py` | 32 | Embedding batch size |
| `RRF_K` | `TUI/rag/retriever.py` | 60 | RRF constant (standard value) |

Increase `FINAL_K` to 5 on machines with more RAM/VRAM. Decrease `TARGET_TOKENS` to 200 if the model loses focus mid-answer.

---

## Future additions (out of scope for this plan)

- Query rewriting — an extra LLM call to expand user queries into fprime vocabulary before retrieval
- Per-component metadata filtering — filter by `component_name` before vector search for `/explain ActiveComponentBase`
- Index versioning — track fprime version in index metadata, warn user when repo has updated
- Sitemap-driven docs crawl — replace single-page fetch with full docs site crawl
- Academy mode RAG — lightweight "concept explanation" index for Academy mode (separate from code-heavy Mission Control index)
