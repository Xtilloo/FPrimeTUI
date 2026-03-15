from rag.config import DEFAULT_TIER, KEYWORD_WEIGHT, RERANK_K, TIERS


def test_tiers_has_three_levels():
    assert set(TIERS.keys()) == {1, 2, 3}


def test_each_tier_has_final_k():
    for tier in TIERS.values():
        assert "final_k" in tier
        assert isinstance(tier["final_k"], int)
        assert tier["final_k"] > 0


def test_tier_final_k_increases_with_level():
    assert TIERS[1]["final_k"] < TIERS[2]["final_k"] < TIERS[3]["final_k"]


def test_default_tier_is_valid():
    assert DEFAULT_TIER in TIERS


def test_rerank_k_is_large_enough():
    max_final_k = max(t["final_k"] for t in TIERS.values())
    # Must accommodate max tier + comparison adjustment (+2)
    assert RERANK_K >= max_final_k + 2


def test_keyword_weight_is_positive():
    assert 0 < KEYWORD_WEIGHT <= 1.0
