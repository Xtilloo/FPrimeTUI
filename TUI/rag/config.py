"""RAG tier configuration. Imported by retriever.py."""

from typing import Any

TIERS: dict[int, dict[str, Any]] = {
    1: {"final_k": 5, "label": "lightweight", "target_models": "≤8B"},
    2: {"final_k": 7, "label": "standard", "target_models": "14B–32B"},
    3: {"final_k": 10, "label": "full", "target_models": "70B+"},
}

DEFAULT_TIER: int = 1

RERANK_K: int = 50  # Fixed — large enough for all tiers + query adjustments

KEYWORD_WEIGHT: float = 0.3  # Multiplicative tiebreaker: score *= (1 + kw * weight)
