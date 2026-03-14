import json
import math
import os
import ollama
from pathlib import Path
from typing import List, Dict, Optional

class FPrimeRAG:
    """
    Retrieval-Augmented Generation for F-Prime-TUI.
    Provides semantic search over F' documentation and code.
    """
    INDEX_FILE = Path(__file__).parent / "fprime_index.json"
    EMBEDDING_MODEL = "mxbai-embed-large"

    def __init__(self):
        self.index = []
        self.load_index()
        self.client = ollama.AsyncClient()

    def load_index(self):
        """Loads the pre-computed index from JSON."""
        if self.INDEX_FILE.exists():
            try:
                with open(self.INDEX_FILE, "r") as f:
                    self.index = json.load(f)
            except Exception:
                self.index = []

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two vectors."""
        if not vec_a or not vec_b:
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    async def retrieve(self, query: str, top_k: int = 3) -> str:
        """Retrieves top-K relevant chunks for a given query."""
        if not self.index:
            return ""

        try:
            # Get query embedding
            resp = await self.client.embeddings(model=self.EMBEDDING_MODEL, prompt=query)
            query_embedding = resp['embedding']
        except Exception:
            # If embedding fails (e.g., model not pulled), return empty context
            return ""

        # Score and rank chunks
        scored_chunks = []
        for item in self.index:
            score = self.cosine_similarity(query_embedding, item["embedding"])
            scored_chunks.append((score, item))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored_chunks[:top_k]

        if not top_chunks:
            return ""

        context_str = "\n### RELEVANT F' KNOWLEDGE BASE ###\n"
        for score, item in top_chunks:
            if score < 0.3: # Minimum similarity threshold
                continue
            context_str += f"\nSOURCE: {item['path']}\n"
            context_str += f"---\n{item['content']}\n---\n"
        context_str += "##################################\n"

        return context_str if len(context_str) > 50 else ""
