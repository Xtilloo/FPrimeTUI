import os
import pickle
import re

import chromadb
import requests
from rank_bm25 import BM25Okapi

DB_PATH = os.path.join(os.path.dirname(__file__), "db")
BM25_PATH = os.path.join(DB_PATH, "bm25.pkl")
DENSE_K = 10    # dense retrieval candidates
SPARSE_K = 20   # BM25 gets more candidates — it's better at exact fprime terms
FINAL_K = 3     # chunks injected into prompt
RERANK_K = FINAL_K * 5  # RRF pool to re-rank before taking FINAL_K
RRF_K = 60      # standard RRF constant


def tokenize(text: str) -> list[str]:
    """
    Tokenize text for BM25: strip punctuation, lowercase, and expand CamelCase.

    'ActiveComponent' → ['activecomponent', 'active', 'component']
    'active component Foo' → ['active', 'component', 'foo']

    Expanding CamelCase improves recall for fprime identifiers: a query for
    'ActiveComponent' also matches chunks where 'active' and 'component' appear
    separately (e.g. in .fpp syntax: 'active component Foo { ... }').
    """
    tokens: list[str] = []
    for word in text.split():
        clean = re.sub(r"[^\w]", "", word)
        if not clean:
            continue
        tokens.append(clean.lower())
        # Split CamelCase boundaries using original casing
        parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", clean).split()
        if len(parts) > 1:
            tokens.extend([p.lower() for p in parts])
    return tokens


def extract_keywords(query: str) -> list[str]:
    """
    Extract high-signal technical terms from a query for re-ranking.

    Only matches true CamelCase identifiers — words with at least one
    lowercase→uppercase transition (e.g. ActiveComponent, FwCom, RateGroup).
    This excludes sentence-start capitals ('What', 'How') that would
    inflate scores for chunks that happen to contain common English words.

    For each match, both the joined form ('activecomponent') AND the
    space-separated form ('active component') are returned so .fpp chunks
    — which use the two-word keyword syntax 'active component Foo { }' —
    also score as keyword matches.
    """
    result: list[str] = []
    # Require at least one lowercase→uppercase transition: matches ActiveComponent,
    # FwCom, RateGroup — does NOT match What, Fprime, The.
    for word in re.findall(r"\b[A-Z][a-zA-Z0-9]*[a-z][A-Z][a-zA-Z0-9]*\b", query):
        result.append(word.lower())
        parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", word).lower().split()
        if len(parts) > 1:
            result.append(" ".join(parts))  # e.g. "active component"
    result.extend(re.findall(r'"([^"]+)"', query))
    return result


# Source-category boost weights — applied at retrieval time, not stored in index.
# Categories are matched by prefix against the chunk's source_file path.
_SOURCE_CATEGORY_RULES: list[tuple[str, str]] = [
    # Order matters: first match wins. More specific patterns first.
    ("FppTestProject/", "test_projects"),
    ("fprime-tools/", "tools"),
    ("Fw/", "framework_core"),
    ("Os/", "framework_core"),
    ("Svc/Cmd", "framework_core"),
    ("Svc/Health", "framework_core"),
    ("docs/getting-started/", "docs_tutorial"),
    ("docs/how-to/", "docs_tutorial"),
    ("docs/reference/", "docs_reference"),
    ("docs/user-manual/", "docs_reference"),
]

_SOURCE_CATEGORY_BOOSTS: dict[str, float] = {
    "framework_core": 1.3,
    "docs_tutorial": 1.2,
    "docs_reference": 1.15,
    "fpp_spec": 1.25,
    "service_docs": 1.0,
    "test_projects": 0.85,
    "tools": 0.9,
}


def get_source_category(source_file: str) -> str:
    """Map a source_file path to its category. Computed at retrieval time."""
    if source_file.endswith(".fpp"):
        return "fpp_spec"
    for prefix, category in _SOURCE_CATEGORY_RULES:
        if source_file.startswith(prefix):
            return category
    if source_file.startswith("Svc/") and "/docs/" in source_file:
        return "service_docs"
    return "service_docs"  # Unknown paths get neutral boost


def get_source_category_boost(source_file: str) -> float:
    """Return the boost multiplier for a source file's category."""
    category = get_source_category(source_file)
    return _SOURCE_CATEGORY_BOOSTS.get(category, 1.0)


# Content-type boost — matches chunk content_type to query_type.
_CONTENT_TYPE_BOOSTS: dict[str, dict[str, float]] = {
    "code_seeking": {"code": 1.2, "reference": 1.2},
    "concept_seeking": {"concept": 1.2, "tutorial": 1.2},
    "comparison": {"concept": 1.1, "reference": 1.1},
}


def get_content_type_boost(content_type: str, query_type: str) -> float:
    """Return boost multiplier for a content_type given the query_type."""
    boosts = _CONTENT_TYPE_BOOSTS.get(query_type, {})
    return boosts.get(content_type, 1.0)


# Query-type classification patterns. Checked in precedence order.
_FILE_EXTENSION_PATTERN = re.compile(r"\b[\w/]+\.\w{1,4}\b")
_COMPARISON_PATTERNS = re.compile(
    r"\b(?:difference|differences|differ|vs\.?|versus|compare|comparing|comparison|between\s+\w+\s+and)\b",
    re.IGNORECASE,
)
_CODE_SEEKING_PATTERNS = re.compile(
    r"\b(?:how\s+to\s+implement|how\s+to\s+write|how\s+to\s+create|how\s+to\s+add|"
    r"example|syntax|code\s+for|write\s+a|implement|show\s+me|snippet)\b",
    re.IGNORECASE,
)
_CONCEPT_SEEKING_PATTERNS = re.compile(
    r"\b(?:what\s+is|what\s+are|explain|describe|overview|purpose\s+of|define)\b",
    re.IGNORECASE,
)


def classify_query(
    text: str, known_entities: set[str]
) -> tuple[str, str]:
    """
    Classify a query into a type using keyword/regex heuristics.

    Returns (query_type, target_entity). target_entity is non-empty only
    for file_specific and component_specific types.

    Precedence: file_specific > component_specific > comparison >
                code_seeking > concept_seeking > general
    """
    text_lower = text.lower()

    # 1. File-specific: check for file extensions or known entity names
    if _FILE_EXTENSION_PATTERN.search(text):
        # Extract potential entity from filename
        for entity in known_entities:
            if entity in text_lower:
                return ("file_specific", entity)
        return ("file_specific", "")

    # 2. Component-specific: CamelCase identifiers that exist in the index
    for word in re.findall(r"\b[A-Z][a-zA-Z0-9]*[a-z][A-Z][a-zA-Z0-9]*\b", text):
        word_lower = word.lower()
        if word_lower in known_entities:
            return ("component_specific", word_lower)

    # Also check for non-CamelCase entity matches (e.g., user writes "Health")
    # Use word boundaries to avoid substring false positives ("os" matching "most")
    for entity in known_entities:
        if len(entity) < 3:
            continue  # Skip short names like "os", "fw" — too many false positives
        if re.search(r"\b" + re.escape(entity) + r"\b", text_lower):
            return ("component_specific", entity)

    # 3. Comparison
    if _COMPARISON_PATTERNS.search(text):
        return ("comparison", "")

    # 4. Code-seeking
    if _CODE_SEEKING_PATTERNS.search(text):
        return ("code_seeking", "")

    # 5. Concept-seeking
    if _CONCEPT_SEEKING_PATTERNS.search(text):
        return ("concept_seeking", "")

    # 6. General
    return ("general", "")


def keyword_score(chunk_text: str, keywords: list[str]) -> float:
    """Return the fraction of keywords present in chunk_text (0.0–1.0)."""
    if not keywords:
        return 0.0
    lower = chunk_text.lower()
    return sum(1 for kw in keywords if kw in lower) / len(keywords)


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


def _embed(text: str) -> list[float]:
    """Embed text using ollama nomic-embed-text (same model used at index time)."""
    resp = requests.post(
        "http://localhost:11434/api/embed",
        json={"model": "nomic-embed-text", "input": [text]},
        timeout=30,
    )
    result: list[float] = resp.json()["embeddings"][0]
    return result


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
    all_chunks: dict[str, dict] = bm25_data["chunks"]
    bm25: BM25Okapi = bm25_data["bm25"]
    chunk_ids: list[str] = bm25_data["ids"]

    # Dense retrieval — embed query with ollama to match index embeddings
    query_embedding = _embed(text)
    dense_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(DENSE_K, collection.count()),
    )
    dense_ids = dense_results["ids"][0]

    # Sparse retrieval — CamelCase-aware tokenization improves recall for
    # fprime identifiers (e.g. 'ActiveComponent' → also matches 'active component').
    # SPARSE_K > DENSE_K because BM25 is more precise for fprime technical terms.
    tokenized = tokenize(text)
    scores = bm25.get_scores(tokenized)
    top_sparse_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:SPARSE_K]
    sparse_ids = [chunk_ids[i] for i in top_sparse_indices]

    # Merge via RRF — keep RERANK_K candidates for keyword re-ranking pass
    merged_ids = reciprocal_rank_fusion(dense_ids, sparse_ids)[:RERANK_K]
    candidates = [all_chunks[cid] for cid in merged_ids if cid in all_chunks]

    # Re-rank: sort candidates by presence of CamelCase identifiers from the
    # query. A chunk about 'ActiveComponent' that literally contains
    # 'activecomponent' or 'active component' scores higher than a chunk about
    # subtopologies that happens to mention 'active' in passing.
    kws = extract_keywords(text)
    if kws:
        candidates.sort(key=lambda c: keyword_score(c["text"], kws), reverse=True)

    top_chunks = candidates[:FINAL_K]

    return {
        "answer_context": format_context(top_chunks),
        "sources": [c["source_file"] for c in top_chunks],
    }
