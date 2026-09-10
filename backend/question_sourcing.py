"""Sources a mock-interview question for a session start: searches SearXNG,
biases the search toward a weak-point tag sampled by weight, and runs the
seniority filter (via the question_sourcing model role), re-searching on
reject up to a fixed attempt cap.

Weighting rule: weight(tag) = max(0.1, 1 + failures - success_streak).
Recent failures with a reset/low streak push weight up; a long run of
successes decays it back toward the floor of 0.1 (never exactly 0 -
requirements.md calls for weighted, not exclusive, sampling, so every tag
keeps some chance of being picked even after a long success streak).
A tag with no history yet (opportunities == 0) gets the neutral baseline
weight of 1.0.
"""

import json
import random
from pathlib import Path

from backend import rubric_loader, weakpoint_store
from backend.agent_schemas import SeniorityEval, SourcedQuestion
from backend.schemas import QuestionProvenance
from backend.searxng_client import search
from backend.structured_llm import complete_structured

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_FILE = PROMPTS_DIR / "question_sourcing_v1.md"

# Re-search cap: bounded so a persistently-rejecting model can't hang
# session start in an unbounded loop. 5 is generous for a single-user tool
# where a hard failure just means "try starting the session again."
MAX_SEARCH_ATTEMPTS = 5

_TARGET_LEVEL = "SDE3/Senior Software Engineer"

_ROUND_TYPE_LABEL = {
    "hld": "high-level system design",
    "lld_deepdive": "low-level/OO design and project deep-dive",
}


class QuestionSourcingError(RuntimeError):
    """Raised when no question clears the seniority bar within
    MAX_SEARCH_ATTEMPTS attempts."""


def _weight_for(counters: weakpoint_store.WeakPointCounters) -> float:
    return max(0.1, 1 + counters.failures - counters.success_streak)


def compute_tag_weights(round_type: str) -> dict[str, float]:
    rubric = rubric_loader.load_rubric(round_type)
    store = weakpoint_store.load(round_type)
    return {
        tag: _weight_for(store.get(tag, weakpoint_store.WeakPointCounters()))
        for tag in rubric.dimension_names()
    }


def select_target_tag(round_type: str, rng: random.Random | None = None) -> str:
    """Weighted (not exclusive) pick of a weak-point tag to bias this
    session's question toward."""
    rng = rng or random
    weights = compute_tag_weights(round_type)
    if not weights:
        raise QuestionSourcingError(
            f"Cannot select a target tag: rubric for {round_type!r} has no "
            "dimensions yet"
        )
    tags = list(weights.keys())
    return rng.choices(tags, weights=[weights[t] for t in tags], k=1)[0]


def _search_query(round_type: str, target_tag: str, attempt: int) -> str:
    label = _ROUND_TYPE_LABEL[round_type]
    topic = target_tag.replace("_", " ")
    base = f"{label} interview question {topic}"
    return base if attempt == 1 else f"{base} (alternate {attempt})"


def source_question(round_type: str, rng: random.Random | None = None) -> SourcedQuestion:
    target_tag = select_target_tag(round_type, rng=rng)
    system_prompt = PROMPT_FILE.read_text()

    for attempt in range(1, MAX_SEARCH_ATTEMPTS + 1):
        query = _search_query(round_type, target_tag, attempt)
        results = search(query, num_results=5)

        user_content = (
            f"Round type: {round_type}\n"
            f"Target level: {_TARGET_LEVEL}\n"
            f"Target weak-point tag to bias toward: {target_tag}\n\n"
            f"Search results:\n{json.dumps(results, indent=2)}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        result = complete_structured("question_sourcing", messages, SeniorityEval)

        if result.accept:
            return SourcedQuestion(
                question=result.question,
                round_type=round_type,
                target_tag=target_tag,
                provenance=QuestionProvenance(
                    source_urls=result.source_urls,
                    discovered_at=_now_iso(),
                    target_level=_TARGET_LEVEL,
                    seniority_eval=result.seniority_eval,
                ),
            )

    raise QuestionSourcingError(
        f"No question cleared the seniority bar for round_type={round_type!r}, "
        f"target_tag={target_tag!r} after {MAX_SEARCH_ATTEMPTS} attempts"
    )


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
