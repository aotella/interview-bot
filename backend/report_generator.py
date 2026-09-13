"""Persists a completed session's grader output plus session metadata
(pauses, durations, diagrams, the reproducibility tuple) as the JSON report
record at data/reports/{session_id}.json - the sole persisted report record.
`dimensions` keys are read from the rubric config, never hardcoded, so an
HLD report can never end up with LLD dimensions or vice versa.
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from backend import config, rubric_loader, transcript_store
from backend.agent_schemas import DimensionScore, GraderOutput, WeakPointOutcome

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"


class SessionReportRecord(BaseModel):
    session_id: str
    date: str
    round_type: str
    question: str
    source_session_id: str | None
    verdict: Literal["SELECT", "REJECT"]
    dimensions: list[DimensionScore]
    weak_point_outcomes: list[WeakPointOutcome]
    diagrams: list[str]
    pauses: dict
    durations: dict
    rubric_version: str
    interviewer_prompt_version: str
    grader_prompt_version: str
    question_sourcing_version: str
    solver_prompt_version: str
    models: dict


def generate_report(session_id: str, grader_output: GraderOutput) -> Path:
    events = transcript_store.read_transcript(session_id)
    session_start = next(e for e in events if e.event == "session_start")
    session_end = next(e for e in events if e.event == "session_end")
    round_type = session_start.round_type

    rubric = rubric_loader.load_rubric(round_type)
    expected_dimensions = set(rubric.dimension_names())
    got_dimensions = {d.dimension for d in grader_output.dimensions}
    if got_dimensions != expected_dimensions:
        raise ValueError(
            f"grader_output dimensions {sorted(got_dimensions)} do not match "
            f"rubric dimensions {sorted(expected_dimensions)} for round_type={round_type!r}"
        )

    pause_events = [e for e in events if e.event in ("pause_start", "pause_end")]
    pause_count = sum(1 for e in pause_events if e.event == "pause_start")
    pause_total_seconds = sum(e.duration_seconds for e in events if e.event == "pause_end")

    diagram_filenames = [Path(e.path).name for e in events if e.event == "diagram_attached"]

    rubric_version_by_round = {
        "hld": config.rubric_version.hld,
        "lld_deepdive": config.rubric_version.lld_deepdive,
    }

    record = SessionReportRecord(
        session_id=session_id,
        date=session_start.timestamp[:10],
        round_type=round_type,
        question=session_start.question,
        source_session_id=getattr(session_start, "source_session_id", None),
        verdict=grader_output.verdict,
        dimensions=grader_output.dimensions,
        weak_point_outcomes=grader_output.weak_point_outcomes,
        diagrams=diagram_filenames,
        pauses={"count": pause_count, "total_seconds": pause_total_seconds},
        durations={
            "wall_clock_seconds": session_end.wall_clock_seconds,
            "active_seconds": session_end.active_seconds,
            "paused_seconds": session_end.paused_seconds,
        },
        rubric_version=rubric_version_by_round[round_type],
        interviewer_prompt_version=config.interviewer_prompt_version,
        grader_prompt_version=config.grader_prompt_version,
        question_sourcing_version=config.question_sourcing_prompt_version,
        solver_prompt_version=config.solver_prompt_version,
        models={
            "interviewer": config.models.interviewer,
            "grader": config.models.grader,
            "question_sourcing": config.models.question_sourcing,
            "solver": config.models.solver,
        },
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{session_id}.json"
    report_path.write_text(record.model_dump_json(indent=2))
    return report_path


def read_report_json(session_id: str) -> SessionReportRecord | None:
    """Read back a previously-written session's full report record -
    verdict, per-dimension scores + evidence, weak-point outcomes, plus the
    session metadata (pauses, durations, diagrams, reproducibility tuple)."""
    path = REPORTS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    return SessionReportRecord.model_validate_json(path.read_text())
