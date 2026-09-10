"""Pydantic I/O shapes for the three agent roles (question sourcing,
interviewer, grader) - distinct from backend/schemas.py, which covers the
persisted transcript event stream."""

from typing import Literal

from pydantic import BaseModel

from backend.schemas import QuestionProvenance

Outcome = Literal["success", "failure", "neutral"]


# --- Question sourcing -------------------------------------------------


class SeniorityEval(BaseModel):
    accept: bool
    question: str
    seniority_eval: str
    source_urls: list[str]


class SourcedQuestion(BaseModel):
    question: str
    round_type: Literal["hld", "lld_deepdive"]
    target_tag: str
    provenance: QuestionProvenance


# --- Interviewer ---------------------------------------------------------


class CheckpointSummary(BaseModel):
    checkpoint_id: str
    candidate_text: str
    action: Literal["continue", "follow_up", "interject"]


class PauseRecord(BaseModel):
    started_at: str
    duration_seconds: int | None = None


class RunningState(BaseModel):
    round_type: Literal["hld", "lld_deepdive"]
    question: str
    elapsed_seconds: int
    checkpoints: list[CheckpointSummary]
    pause_history: list[PauseRecord]
    diagrams_attached: list[str]


class InterviewerDecision(BaseModel):
    action: Literal["continue", "follow_up", "interject"]
    text: str


# --- Grader ----------------------------------------------------------------


class Evidence(BaseModel):
    event_id: str
    reason: str


class DimensionScore(BaseModel):
    dimension: str
    score: int
    evidence: list[Evidence]


class WeakPointOutcome(BaseModel):
    tag: str
    outcome: Outcome


class GraderOutput(BaseModel):
    verdict: Literal["SELECT", "REJECT"]
    dimensions: list[DimensionScore]
    weak_point_outcomes: list[WeakPointOutcome]


class DiagramImage(BaseModel):
    checkpoint_id: str
    path: str
    media_type: Literal["image/png", "image/svg+xml"]
    data_base64: str
