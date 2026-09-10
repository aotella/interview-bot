import random
from collections import Counter

from backend import weakpoint_store
from backend.question_sourcing import compute_tag_weights, select_target_tag


def test_weighted_sampling_favors_recent_failures_over_long_streak():
    # Tag X: recent failures, streak reset - should dominate selection.
    weakpoint_store.record_outcome("hld", "capacity_estimation", "failure", seen_on="2026-08-01")
    weakpoint_store.record_outcome("hld", "capacity_estimation", "failure", seen_on="2026-08-15")
    weakpoint_store.record_outcome("hld", "capacity_estimation", "failure", seen_on="2026-09-01")

    # Tag Y: long success streak - weight should have decayed toward the floor.
    for i in range(6):
        weakpoint_store.record_outcome(
            "hld", "tradeoffs_stated", "success", seen_on=f"2026-08-{i + 1:02d}"
        )

    rng = random.Random(42)
    picks = Counter(select_target_tag("hld", rng=rng) for _ in range(500))

    assert picks["capacity_estimation"] > picks["tradeoffs_stated"] * 3


def test_weighted_sampling_flips_when_store_is_reversed():
    for i in range(6):
        weakpoint_store.record_outcome(
            "hld", "capacity_estimation", "success", seen_on=f"2026-08-{i + 1:02d}"
        )
    weakpoint_store.record_outcome("hld", "tradeoffs_stated", "failure", seen_on="2026-08-01")
    weakpoint_store.record_outcome("hld", "tradeoffs_stated", "failure", seen_on="2026-08-15")
    weakpoint_store.record_outcome("hld", "tradeoffs_stated", "failure", seen_on="2026-09-01")

    rng = random.Random(42)
    picks = Counter(select_target_tag("hld", rng=rng) for _ in range(500))

    assert picks["tradeoffs_stated"] > picks["capacity_estimation"] * 3


def test_every_tag_keeps_nonzero_weight_even_after_long_streak():
    for i in range(20):
        weakpoint_store.record_outcome(
            "hld", "failure_modes", "success", seen_on=f"2026-01-{(i % 28) + 1:02d}"
        )
    weights = compute_tag_weights("hld")
    assert weights["failure_modes"] > 0
