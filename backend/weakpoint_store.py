"""Per-round-type weak-point counters, persisted at
`data/weakpoints/{round_type}.json`.

Tag vocabulary (what strings are valid tags) is intentionally not enforced
here - it's treated as an opaque string key. Which vocabulary weak-point
tags actually use (rubric dimension names vs. a separate finer-grained set)
is Flagged item 3 in PLAN.md and is out of scope for this store; it only
guarantees the counter invariant holds for whatever tag it's given.
"""

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

WEAKPOINTS_DIR = Path(__file__).resolve().parent.parent / "data" / "weakpoints"

Outcome = Literal["success", "failure", "neutral"]


class WeakPointCounters(BaseModel):
    opportunities: int = 0
    successes: int = 0
    failures: int = 0
    neutral: int = 0
    success_streak: int = 0
    last_seen: str | None = None

    @model_validator(mode="after")
    def _check_invariant(self) -> "WeakPointCounters":
        if self.opportunities != self.successes + self.failures + self.neutral:
            raise ValueError(
                "weak-point counter invariant violated: "
                f"opportunities ({self.opportunities}) != successes "
                f"({self.successes}) + failures ({self.failures}) + "
                f"neutral ({self.neutral})"
            )
        return self


def _store_path(round_type: str) -> Path:
    return WEAKPOINTS_DIR / f"{round_type}.json"


def load(round_type: str) -> dict[str, WeakPointCounters]:
    path = _store_path(round_type)
    if not path.exists():
        return {}
    with path.open("r") as f:
        raw = json.load(f)
    return {tag: WeakPointCounters.model_validate(counters) for tag, counters in raw.items()}


def save(round_type: str, data: dict[str, WeakPointCounters]) -> None:
    """Write the full store for a round type. Every entry is already a
    validated WeakPointCounters, so the invariant holds for every write
    that goes through this module."""
    path = _store_path(round_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {tag: counters.model_dump() for tag, counters in data.items()}
    with path.open("w") as f:
        json.dump(raw, f, indent=2, sort_keys=True)
        f.write("\n")


def record_outcome(
    round_type: str,
    tag: str,
    outcome: Outcome,
    seen_on: date | str | None = None,
) -> WeakPointCounters:
    """Record one graded opportunity for `tag` and persist the update.

    success_streak resets to 0 on any failure, increments on success, and
    is left unchanged on a neutral outcome. last_seen only updates here,
    since opportunities always increments on a call to this function.
    """
    seen_on = seen_on if seen_on is not None else date.today()
    seen_on_str = seen_on.isoformat() if isinstance(seen_on, date) else seen_on

    data = load(round_type)
    current = data.get(tag, WeakPointCounters())

    updates = {
        "opportunities": current.opportunities + 1,
        "successes": current.successes + (1 if outcome == "success" else 0),
        "failures": current.failures + (1 if outcome == "failure" else 0),
        "neutral": current.neutral + (1 if outcome == "neutral" else 0),
        "success_streak": (
            0 if outcome == "failure"
            else current.success_streak + 1 if outcome == "success"
            else current.success_streak
        ),
        "last_seen": seen_on_str,
    }
    updated = WeakPointCounters.model_validate(updates)

    data[tag] = updated
    save(round_type, data)
    return updated
