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


def _load_index() -> tuple:
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
