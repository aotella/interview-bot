"""Pydantic models for the transcript event stream.

Every event carries an `event_id`, assigned by the transcript writer at
append time (never by the caller) so it can never collide - see
`transcript_store.py`. Events are discriminated on the `event` field so a
parsed JSONL line round-trips to the right concrete type.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class _BaseEvent(BaseModel):
    event_id: str
    timestamp: str


class QuestionProvenance(BaseModel):
    source_urls: list[str]
    discovered_at: str
    target_level: str
    seniority_eval: str


class SessionStartEvent(_BaseEvent):
    event: Literal["session_start"] = "session_start"
    session_id: str
    round_type: Literal["hld", "lld_deepdive"]
    question: str
    question_provenance: QuestionProvenance
    source_session_id: str | None = None


class CandidateTurnEvent(_BaseEvent):
    event: Literal["candidate_turn"] = "candidate_turn"
    checkpoint_id: str
    text: str
    input_mode: Literal["typed", "voice", "solver"]


class InterviewerTurnEvent(_BaseEvent):
    event: Literal["interviewer_turn"] = "interviewer_turn"
    checkpoint_id: str
    action: Literal["continue", "follow_up", "interject"]
    text: str


class PauseStartEvent(_BaseEvent):
    event: Literal["pause_start"] = "pause_start"


class PauseEndEvent(_BaseEvent):
    event: Literal["pause_end"] = "pause_end"
    duration_seconds: int


class DiagramAttachedEvent(_BaseEvent):
    event: Literal["diagram_attached"] = "diagram_attached"
    checkpoint_id: str
    path: str
    file_type: Literal["png", "svg"]
    volunteered: bool


class SessionEndEvent(_BaseEvent):
    event: Literal["session_end"] = "session_end"
    wall_clock_seconds: int
    active_seconds: int
    paused_seconds: int


TranscriptEvent = Annotated[
    Union[
        SessionStartEvent,
        CandidateTurnEvent,
        InterviewerTurnEvent,
        PauseStartEvent,
        PauseEndEvent,
        DiagramAttachedEvent,
        SessionEndEvent,
    ],
    Field(discriminator="event"),
]

EVENT_TYPES_BY_NAME: dict[str, type[BaseModel]] = {
    "session_start": SessionStartEvent,
    "candidate_turn": CandidateTurnEvent,
    "interviewer_turn": InterviewerTurnEvent,
    "pause_start": PauseStartEvent,
    "pause_end": PauseEndEvent,
    "diagram_attached": DiagramAttachedEvent,
    "session_end": SessionEndEvent,
}


def parse_event(raw: dict) -> TranscriptEvent:
    """Parse a raw JSON object (one JSONL line) into its concrete event type."""
    event_name = raw.get("event")
    model = EVENT_TYPES_BY_NAME.get(event_name)
    if model is None:
        raise ValueError(f"Unknown event type: {event_name!r}")
    return model.model_validate(raw)
