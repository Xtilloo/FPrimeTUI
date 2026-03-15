"""
Run once to build the RAG index:
    python -m rag.indexer

Requires ollama running with nomic-embed-text pulled:
    ollama pull nomic-embed-text
"""

import hashlib
import pickle
import shutil
import sys
from pathlib import Path
from typing import Any

import chromadb
import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup
from git import Repo
from rag.chunker import (
    chunk_autocoded_cpp,
    chunk_cpp,
    chunk_fpp,
    chunk_markdown,
    chunk_python,
    deduplicate,
)
from rag.retriever import tokenize
from rank_bm25 import BM25Okapi

DB_PATH = Path(__file__).parent / "db"
RAW_PATH = Path(__file__).parent / "raw"

SOURCES = {
    "github": "https://github.com/nasa/fprime.git",
    "docs": "https://fprime.jpl.nasa.gov",
    "fprime_tools": "https://github.com/fprime-community/fprime-tools.git",
}


def preflight_check() -> None:
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


def fetch_github(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  Using cached {dest.name}")
        return
    print(f"  Cloning {url} ...")
    Repo.clone_from(url, dest, depth=1)


def fetch_docs(base_url: str, dest: Path) -> None:
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


def _is_generated_skip(filename: str) -> bool:
    """Files to skip entirely (generated boilerplate with no RAG value)."""
    return any(pattern in filename for pattern in ("GTestBase", "TesterBase"))


def _is_autocoded(filename: str) -> bool:
    """Autocoded files get API extraction instead of full chunking."""
    return filename.endswith(("Ac.hpp", "Ac.cpp"))


def collect_chunks() -> list[dict[str, Any]]:
    """Walk raw sources and produce all chunks."""
    all_chunks: list[dict[str, Any]] = []

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

    # C++ files from fprime framework
    for ext in (".hpp", ".h", ".cpp"):
        for f in repo_path.rglob(f"*{ext}"):
            # Skip build artifacts
            rel = str(f.relative_to(repo_path))
            if rel.startswith("build") or "/build/" in rel:
                continue
            try:
                name = f.name
                if _is_generated_skip(name):
                    continue
                text = f.read_text(errors="ignore")
                if _is_autocoded(name):
                    all_chunks.extend(chunk_autocoded_cpp(text, source=rel))
                else:
                    all_chunks.extend(chunk_cpp(text, source=rel))
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

    result: list[dict[str, Any]] = deduplicate(all_chunks)
    return result


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Call ollama embed endpoint for a batch of texts."""
    resp = requests.post(
        "http://localhost:11434/api/embed",
        json={"model": "nomic-embed-text", "input": texts},
        timeout=60,
    )
    result: list[list[float]] = resp.json()["embeddings"]
    return result


def build_index(chunks: list[dict[str, Any]], db_path: Path) -> None:
    """Write ChromaDB + BM25 index to db_path."""
    db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_or_create_collection("fprime")

    chunk_map: dict[str, dict[str, Any]] = {}
    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []

    BATCH = 32
    for i, chunk in enumerate(chunks):
        cid = hashlib.sha256(chunk["text"].encode()).hexdigest()[:16]
        chunk_map[cid] = chunk
        ids.append(cid)
        texts.append(chunk["text"])
        metadatas.append({
            "source_file": str(chunk["source_file"]),
            "chunk_type": str(chunk["chunk_type"]),
            "component_name": str(chunk.get("component_name", "")),
            "content_type": str(chunk.get("content_type", "")),
            # NOTE: design spec mentions priority: "high" for FPP spec files, but
            # the retriever handles this via source-category boost (fpp_spec → 1.25x)
            # at query time rather than stored metadata. Deferred to iteration 4.
        })

        if len(ids) == BATCH or i == len(chunks) - 1:
            embs = embed_batch(texts)
            collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embs)  # type: ignore[arg-type]
            print(f"  Indexed {i+1}/{len(chunks)} chunks", end="\r")
            ids, texts, metadatas = [], [], []

    print()

    # BM25
    tokenized = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized)
    all_ids = [hashlib.sha256(c["text"].encode()).hexdigest()[:16] for c in chunks]
    bm25_data = {"bm25": bm25, "ids": all_ids, "chunks": chunk_map}
    with open(db_path / "bm25.pkl", "wb") as f:
        pickle.dump(bm25_data, f)


def main() -> None:
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
