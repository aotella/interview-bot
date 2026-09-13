"""Post-session grader agent. Runs once per session, reads the transcript
fresh from disk (not the interviewer's in-session state), scores against
the rubric loaded from backend/rubrics/{round_type}_{version}.yaml, and
returns structured output whose evidence event_ids are checked against the
real transcript before being accepted.

Diagram handling (Flagged item 6): this module takes pre-loaded
DiagramImage objects - it never touches the filesystem itself, so it stays
testable independent of Phase 5's session engine. Callers are responsible
for capping at 5 diagrams / 5MB each and passing a text note instead for
any diagram that couldn't be loaded (see backend/scripts/dev_grade_transcript.py
for the reference caller).
"""

import json
from pathlib import Path

from backend import rubric_loader, transcript_store
from backend.agent_schemas import DiagramImage, GraderOutput
from backend.structured_llm import StructuredOutputError, complete_structured

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_PROMPT_FILES = {
    "hld": "grader_hld_v1.md",
    "lld_deepdive": "grader_lld_deepdive_v1.md",
}

MAX_DIAGRAMS = 5
MAX_DIAGRAM_BYTES = 5 * 1024 * 1024


class GraderOutputError(RuntimeError):
    """Raised when the grader fails to produce output that both validates
    against the schema and cross-references only real transcript event_ids
    and real rubric dimensions, within the retry budget."""


def _load_prompt(round_type: str) -> str:
    return (PROMPTS_DIR / _PROMPT_FILES[round_type]).read_text()


def _build_user_content(rubric_json: str, transcript_json: str, diagrams: list[DiagramImage]) -> list[dict]:
    content: list[dict] = [
        {"type": "text", "text": f"Rubric:\n{rubric_json}\n\nTranscript:\n{transcript_json}"}
    ]

    accepted, dropped = [], []
    total_bytes = 0
    for d in diagrams:
        size = len(d.data_base64) * 3 // 4  # approx decoded size
        if len(accepted) >= MAX_DIAGRAMS or size > MAX_DIAGRAM_BYTES:
            dropped.append(d)
            continue
        accepted.append(d)
        total_bytes += size

    for d in accepted:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{d.media_type};base64,{d.data_base64}"},
            }
        )
    for d in dropped:
        content.append(
            {
                "type": "text",
                "text": (
                    f"[diagram at {d.path} for checkpoint {d.checkpoint_id} could not "
                    "be included - dropped for exceeding the per-session diagram cap "
                    "or size limit]"
                ),
            }
        )
    return content


def grade_transcript(session_id: str, diagrams: list[DiagramImage] | None = None) -> GraderOutput:
    diagrams = diagrams or []
    events = transcript_store.read_transcript(session_id)
    if not events or events[0].event != "session_start":
        raise ValueError(f"Transcript for session {session_id!r} has no session_start event")

    round_type = events[0].round_type
    rubric = rubric_loader.load_rubric(round_type)
    expected_dimensions = set(rubric.dimension_names())
    valid_event_ids = {e.event_id for e in events}

    def _extra_validate(output: GraderOutput) -> None:
        got_dimensions = {d.dimension for d in output.dimensions}
        if got_dimensions != expected_dimensions:
            raise ValueError(
                f"dimensions {sorted(got_dimensions)} do not match rubric "
                f"dimensions {sorted(expected_dimensions)}"
            )
        for d in output.dimensions:
            if d.score is None:
                if d.evidence:
                    raise ValueError(
                        f"dimension {d.dimension!r} scored null (not applicable) but "
                        f"cites {len(d.evidence)} evidence entries - null means no "
                        "transcript evidence exists for this dimension, so it must "
                        "cite none"
                    )
            else:
                if not (rubric.score_range[0] <= d.score <= rubric.score_range[1]):
                    raise ValueError(
                        f"score {d.score} for dimension {d.dimension!r} is outside "
                        f"rubric score_range {rubric.score_range}"
                    )
                if not d.evidence:
                    raise ValueError(
                        f"dimension {d.dimension!r} has a real score ({d.score}) but "
                        "cites no evidence - a real score requires at least one "
                        "citation, otherwise it should be null instead"
                    )
            for ev in d.evidence:
                if ev.event_id not in valid_event_ids:
                    raise ValueError(
                        f"evidence event_id {ev.event_id!r} does not exist in "
                        f"transcript for session {session_id!r}"
                    )

        # weak_point_outcomes must cover exactly the scored (non-null)
        # dimensions - not just "no null tag leaked in" (Flagged item 7's
        # review pass caught that a one-directional check also misses the
        # mirror bug: a real, scored dimension silently missing from
        # weak_point_outcomes, which undercounts a real weakness the same
        # way a leaked null tag would overcount one).
        scored_tags = {d.dimension for d in output.dimensions if d.score is not None}
        wpo_tags = {wpo.tag for wpo in output.weak_point_outcomes}
        if wpo_tags != scored_tags:
            missing = scored_tags - wpo_tags
            extra = wpo_tags - scored_tags
            raise ValueError(
                f"weak_point_outcomes tags {sorted(wpo_tags)} must exactly match "
                f"scored (non-null) dimensions {sorted(scored_tags)}; "
                f"missing={sorted(missing)} extra={sorted(extra)}"
            )

    system_prompt = _load_prompt(round_type)
    rubric_json = json.dumps(rubric.model_dump(), indent=2)
    transcript_json = json.dumps([e.model_dump() for e in events], indent=2)
    user_content = _build_user_content(rubric_json, transcript_json, diagrams)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        return complete_structured(
            "grader", messages, GraderOutput, extra_validate=_extra_validate
        )
    except StructuredOutputError as e:
        raise GraderOutputError(str(e)) from e
