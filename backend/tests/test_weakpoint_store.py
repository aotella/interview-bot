import pytest
from pydantic import ValidationError

from backend.weakpoint_store import WeakPointCounters, load, record_outcome


def test_invariant_enforced_on_construction():
    with pytest.raises(ValidationError):
        WeakPointCounters(opportunities=5, successes=1, failures=1, neutral=1)


def test_record_outcome_updates_counters_and_streak():
    record_outcome("hld", "capacity_estimation", "failure", seen_on="2026-09-01")
    record_outcome("hld", "capacity_estimation", "success", seen_on="2026-09-05")
    updated = record_outcome("hld", "capacity_estimation", "success", seen_on="2026-09-08")

    assert updated.opportunities == 3
    assert updated.successes == 2
    assert updated.failures == 1
    assert updated.neutral == 0
    assert updated.success_streak == 2  # reset by the failure, then two successes
    assert updated.last_seen == "2026-09-08"

    persisted = load("hld")["capacity_estimation"]
    assert persisted == updated


def test_failure_resets_streak():
    record_outcome("hld", "tradeoff_articulation", "success", seen_on="2026-09-01")
    record_outcome("hld", "tradeoff_articulation", "success", seen_on="2026-09-02")
    after_failure = record_outcome("hld", "tradeoff_articulation", "failure", seen_on="2026-09-03")

    assert after_failure.success_streak == 0
    assert after_failure.opportunities == 3
    assert after_failure.successes == 2
    assert after_failure.failures == 1


def test_neutral_outcome_leaves_streak_unchanged():
    record_outcome("hld", "failure_modes", "success", seen_on="2026-09-01")
    after_neutral = record_outcome("hld", "failure_modes", "neutral", seen_on="2026-09-02")

    assert after_neutral.success_streak == 1
    assert after_neutral.opportunities == 2
    assert after_neutral.neutral == 1
