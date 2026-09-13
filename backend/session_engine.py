"""Owns the full session lifecycle: start -> checkpoint loop -> pause/resume
-> diagram attach -> end -> grade -> weak-point update -> report.

There is no separate in-memory session-state object: the transcript file is
the single source of truth, and the "lightweight running state" the
interviewer needs (round type, question, elapsed time, checkpoints so far,
pause history, diagrams attached) is reconstructed fresh from it on every
checkpoint. For a single-user, one-session-at-a-time tool this is simpler
and safer than keeping a second copy of state that could drift from the
transcript.
"""

import base64
import shutil
from datetime import datetime, timezone
from pathlib import Path

from backend import config, grader_agent, interviewer_agent, question_sourcing, report_generator
from backend import rubric_loader, solver_agent, study_guide_agent, transcript_store, weakpoint_store
from backend.agent_schemas import CheckpointSummary, DiagramImage, PauseRecord, RunningState
from backend.grader_agent import GraderOutputError
from backend.schemas import TranscriptEvent

DIAGRAMS_DIR = Path(__file__).resolve().parent.parent / "data" / "diagrams"
STUDY_GUIDES_DIR = Path(__file__).resolve().parent.parent / "data" / "study_guides"

_MEDIA_TYPES = {"png": "image/png", "svg": "image/svg+xml"}


class SessionEngineError(RuntimeError):
    """Raised for lifecycle-ordering violations (e.g. resuming a session
    that isn't paused) or missing preconditions (e.g. no exported diagram
    file found)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _next_session_id(now: datetime) -> str:
    date_str = now.strftime("%Y-%m-%d")
    existing = sorted(transcript_store.TRANSCRIPTS_DIR.glob(f"s_{date_str}-*.jsonl"))
    return f"s_{date_str}-{len(existing) + 1:02d}"


def _is_currently_paused(events: list[TranscriptEvent]) -> bool:
    open_pause = None
    for e in events:
        if e.event == "pause_start":
            open_pause = e
        elif e.event == "pause_end":
            open_pause = None
    return open_pause is not None


def _elapsed_seconds(events: list[TranscriptEvent], now: datetime) -> int:
    start_ts = None
    paused_total = 0.0
    open_pause_ts = None
    for e in events:
        if e.event == "session_start":
            start_ts = _parse_ts(e.timestamp)
        elif e.event == "pause_start":
            open_pause_ts = _parse_ts(e.timestamp)
        elif e.event == "pause_end":
            paused_total += e.duration_seconds
            open_pause_ts = None
    if start_ts is None:
        raise SessionEngineError("No session_start event found")

    wall = (now - start_ts).total_seconds()
    if open_pause_ts is not None:
        wall -= (now - open_pause_ts).total_seconds()
    return max(0, int(wall - paused_total))


def _build_running_state(events: list[TranscriptEvent], now: datetime) -> RunningState:
    session_start = next(e for e in events if e.event == "session_start")

    interviewer_by_checkpoint = {
        e.checkpoint_id: e for e in events if e.event == "interviewer_turn"
    }
    checkpoints = []
    for e in events:
        if e.event != "candidate_turn":
            continue
        it = interviewer_by_checkpoint.get(e.checkpoint_id)
        if it is None:
            continue  # in-flight checkpoint, interviewer hasn't decided yet
        checkpoints.append(
            CheckpointSummary(
                checkpoint_id=e.checkpoint_id,
                candidate_text=e.text,
                action=it.action,
                interviewer_text=it.text if it.action != "continue" else None,
            )
        )

    pause_history = []
    open_pause = None
    for e in events:
        if e.event == "pause_start":
            open_pause = PauseRecord(started_at=e.timestamp, duration_seconds=None)
        elif e.event == "pause_end" and open_pause is not None:
            open_pause.duration_seconds = e.duration_seconds
            pause_history.append(open_pause)
            open_pause = None
    if open_pause is not None:
        pause_history.append(open_pause)

    diagrams_attached = [e.checkpoint_id for e in events if e.event == "diagram_attached"]

    return RunningState(
        round_type=session_start.round_type,
        question=session_start.question,
        elapsed_seconds=_elapsed_seconds(events, now),
        checkpoints=checkpoints,
        pause_history=pause_history,
        diagrams_attached=diagrams_attached,
    )


def _start_session_core(
    round_type: str, question: str, provenance, source_session_id: str | None = None
) -> dict:
    now = _now()
    session_id = _next_session_id(now)
    fields = {
        "session_id": session_id,
        "round_type": round_type,
        "question": question,
        "question_provenance": provenance.model_dump() if hasattr(provenance, "model_dump") else provenance,
        "timestamp": now.isoformat(),
    }
    if source_session_id is not None:
        fields["source_session_id"] = source_session_id
    transcript_store.append_event(session_id, "session_start", fields)
    return {"session_id": session_id, "round_type": round_type, "question": question}


def start_session(round_type: str) -> dict:
    sourced = question_sourcing.source_question(round_type)
    return _start_session_core(round_type, sourced.question, sourced.provenance)


def save_checkpoint(session_id: str, text: str, input_mode: str) -> dict:
    if transcript_store.is_closed(session_id):
        raise SessionEngineError(f"Session {session_id!r} has already ended")

    events_before = transcript_store.read_transcript(session_id)
    if _is_currently_paused(events_before):
        raise SessionEngineError(f"Session {session_id!r} is paused; resume before checkpointing")

    checkpoint_id = f"cp_{sum(1 for e in events_before if e.event == 'candidate_turn') + 1}"
    running_state = _build_running_state(events_before, _now())

    transcript_store.append_event(
        session_id,
        "candidate_turn",
        {"checkpoint_id": checkpoint_id, "text": text, "input_mode": input_mode, "timestamp": _now().isoformat()},
    )

    decision = interviewer_agent.decide(running_state, checkpoint_id, text)

    transcript_store.append_event(
        session_id,
        "interviewer_turn",
        {
            "checkpoint_id": checkpoint_id,
            "action": decision.action,
            "text": decision.text,
            "timestamp": _now().isoformat(),
        },
    )
    return {"checkpoint_id": checkpoint_id, "action": decision.action, "text": decision.text}


def pause(session_id: str) -> dict:
    events = transcript_store.read_transcript(session_id)
    if _is_currently_paused(events):
        raise SessionEngineError(f"Session {session_id!r} is already paused")
    now = _now()
    transcript_store.append_event(session_id, "pause_start", {"timestamp": now.isoformat()})
    return {"paused": True, "timestamp": now.isoformat()}


def resume(session_id: str) -> dict:
    events = transcript_store.read_transcript(session_id)
    if not _is_currently_paused(events):
        raise SessionEngineError(f"Session {session_id!r} is not paused")
    pause_start_event = next(e for e in reversed(events) if e.event == "pause_start")
    now = _now()
    duration_seconds = max(0, int((now - _parse_ts(pause_start_event.timestamp)).total_seconds()))
    transcript_store.append_event(
        session_id, "pause_end", {"duration_seconds": duration_seconds, "timestamp": now.isoformat()}
    )
    return {"paused": False, "duration_seconds": duration_seconds}


def attach_diagram(session_id: str, checkpoint_id: str, volunteered: bool = True) -> dict:
    export_dir = Path(config.EXCALIDRAW_EXPORT_PATH)
    candidates = [p for p in export_dir.glob("*") if p.is_file() and p.suffix.lower() in (".png", ".svg")]
    if not candidates:
        raise SessionEngineError(f"No PNG/SVG files found in {export_dir}")
    latest = max(candidates, key=lambda p: p.stat().st_mtime)

    dest_dir = DIAGRAMS_DIR / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / latest.name
    shutil.copyfile(latest, dest)

    file_type = "png" if latest.suffix.lower() == ".png" else "svg"
    transcript_store.append_event(
        session_id,
        "diagram_attached",
        {
            "checkpoint_id": checkpoint_id,
            "path": str(dest),
            "file_type": file_type,
            "volunteered": volunteered,
            "timestamp": _now().isoformat(),
        },
    )
    return {"path": str(dest), "file_type": file_type}


def _load_diagram_images(events: list[TranscriptEvent]) -> list[DiagramImage]:
    images = []
    for e in events:
        if e.event != "diagram_attached":
            continue
        path = Path(e.path)
        if not path.exists():
            continue
        data_base64 = base64.b64encode(path.read_bytes()).decode("ascii")
        images.append(
            DiagramImage(
                checkpoint_id=e.checkpoint_id,
                path=str(path),
                media_type=_MEDIA_TYPES[e.file_type],
                data_base64=data_base64,
            )
        )
    return images


def end_session(session_id: str) -> dict:
    events = transcript_store.read_transcript(session_id)
    if _is_currently_paused(events):
        raise SessionEngineError(f"Session {session_id!r} is paused; resume before ending")

    now = _now()
    session_start = next(e for e in events if e.event == "session_start")
    start_ts = _parse_ts(session_start.timestamp)
    wall_clock_seconds = max(0, int((now - start_ts).total_seconds()))
    paused_seconds = sum(e.duration_seconds for e in events if e.event == "pause_end")
    active_seconds = wall_clock_seconds - paused_seconds

    transcript_store.append_event(
        session_id,
        "session_end",
        {
            "wall_clock_seconds": wall_clock_seconds,
            "active_seconds": active_seconds,
            "paused_seconds": paused_seconds,
            "timestamp": now.isoformat(),
        },
    )

    full_events = transcript_store.read_transcript(session_id)
    diagrams = _load_diagram_images(full_events)

    try:
        grader_output = grader_agent.grade_transcript(session_id, diagrams=diagrams)
    except GraderOutputError as e:
        return {"session_id": session_id, "graded": False, "error": str(e)}

    # Solver-originated sessions are graded identically but excluded from
    # the weak-point tracker - that tracker measures the human's own
    # performance, and "this session has a source" is exactly the fact
    # that identifies a solver run (see run_solver_comparison).
    is_solver_run = getattr(session_start, "source_session_id", None) is not None
    if not is_solver_run:
        for outcome in grader_output.weak_point_outcomes:
            weakpoint_store.record_outcome(
                session_start.round_type, outcome.tag, outcome.outcome, seen_on=now.date()
            )

    report_path = report_generator.generate_report(session_id, grader_output)

    return {
        "session_id": session_id,
        "graded": True,
        "verdict": grader_output.verdict,
        "report_path": str(report_path),
    }


def get_session_report(session_id: str) -> dict:
    """Full graded report for the UI: verdict, per-dimension scores +
    evidence, weak-point outcomes. Only callable once the session has ended
    and graded successfully - the JSON sidecar report_generator wrote
    alongside the Markdown is the source of truth here, not the transcript
    (which never carries the grader's structured output)."""
    events = transcript_store.read_transcript(session_id)
    if not events:
        raise SessionEngineError(f"No session found with id {session_id!r}")
    if events[-1].event != "session_end":
        raise SessionEngineError(f"Session {session_id!r} has not ended yet")

    session_start = next(e for e in events if e.event == "session_start")
    grader_output = report_generator.read_report_json(session_id)
    if grader_output is None:
        raise SessionEngineError(f"No report found for session {session_id!r}")

    rubric = rubric_loader.load_rubric(session_start.round_type)
    return {
        "session_id": session_id,
        "round_type": session_start.round_type,
        "question": session_start.question,
        "verdict": grader_output.verdict,
        "score_range": list(rubric.score_range),
        "dimensions": [d.model_dump() for d in grader_output.dimensions],
        "weak_point_outcomes": [o.model_dump() for o in grader_output.weak_point_outcomes],
        "source_session_id": getattr(session_start, "source_session_id", None),
    }


def get_session_transcript(session_id: str) -> dict:
    """The session's conversation as ordered, readable turns - for the UI's
    'reference answer' view (mainly meant for a solver-comparison session,
    so the human can actually read the reference candidate's answers, not
    just its critique). `continue` decisions are skipped since they carry
    no visible text (same convention as solver_agent.build_messages)."""
    events = transcript_store.read_transcript(session_id)
    if not events:
        raise SessionEngineError(f"No session found with id {session_id!r}")

    session_start = next(e for e in events if e.event == "session_start")
    turns = []
    for e in events:
        if e.event == "candidate_turn":
            turns.append({"speaker": "candidate", "action": None, "text": e.text})
        elif e.event == "interviewer_turn" and e.action != "continue":
            turns.append({"speaker": "interviewer", "action": e.action, "text": e.text})

    return {
        "session_id": session_id,
        "round_type": session_start.round_type,
        "question": session_start.question,
        "turns": turns,
    }


def study_guide_exists(session_id: str) -> bool:
    return (STUDY_GUIDES_DIR / f"{session_id}.html").exists()


def get_study_guide(session_id: str) -> str | None:
    """The cached study-guide HTML for this session, or None if it hasn't
    been generated yet. Read-only file lookup - no LLM call."""
    path = STUDY_GUIDES_DIR / f"{session_id}.html"
    if not path.exists():
        return None
    return path.read_text()


def generate_study_guide(session_id: str) -> dict:
    """Generates (and caches to disk) a one-time HTML study guide grounded
    in this session's transcript - meant to be called on a solver-comparison
    session, so the teaching material is grounded in a strong reference
    answer. If the session has a source_session_id (i.e. it IS a solver
    run) and that source's own report exists, its failed dimensions are
    passed through so the guide can weight those topics more heavily.
    Always regenerates and overwrites any existing cached copy."""
    events = transcript_store.read_transcript(session_id)
    if not events:
        raise SessionEngineError(f"No session found with id {session_id!r}")

    session_start = next(e for e in events if e.event == "session_start")
    transcript = get_session_transcript(session_id)

    weak_points: list[str] = []
    source_session_id = getattr(session_start, "source_session_id", None)
    if source_session_id is not None:
        source_report = report_generator.read_report_json(source_session_id)
        if source_report is not None:
            weak_points = [o.tag for o in source_report.weak_point_outcomes if o.outcome == "failure"]

    html = study_guide_agent.generate(
        session_start.round_type, session_start.question, transcript["turns"], weak_points
    )

    STUDY_GUIDES_DIR.mkdir(parents=True, exist_ok=True)
    path = STUDY_GUIDES_DIR / f"{session_id}.html"
    path.write_text(html)
    return {"session_id": session_id, "path": str(path)}


def get_weakpoints(round_type: str) -> dict:
    """Per-dimension weak-point counters for the UI, plus a derived
    success_rate (successes / opportunities, None if opportunities == 0)
    since the raw counters alone force the UI to redo that arithmetic."""
    counters = weakpoint_store.load(round_type)
    return {
        tag: {
            **c.model_dump(),
            "success_rate": (c.successes / c.opportunities) if c.opportunities else None,
        }
        for tag, c in counters.items()
    }


def get_session_summary(session_id: str) -> dict:
    """Session summary for the UI: elapsed time, latest interviewer
    decision/text (only when not `continue`), pause state, checkpoint
    count while in progress; verdict/scores once ended and graded. The full
    report (per-dimension evidence) is available via get_session_report."""
    events = transcript_store.read_transcript(session_id)
    if not events:
        raise SessionEngineError(f"No session found with id {session_id!r}")

    session_start = next(e for e in events if e.event == "session_start")
    ended = events[-1].event == "session_end"
    checkpoint_count = sum(1 for e in events if e.event == "candidate_turn")

    last_interviewer_turn = next(
        (e for e in reversed(events) if e.event == "interviewer_turn"), None
    )
    latest_action = last_interviewer_turn.action if last_interviewer_turn else None
    latest_text = (
        last_interviewer_turn.text
        if last_interviewer_turn and last_interviewer_turn.action != "continue"
        else None
    )

    summary = {
        "session_id": session_id,
        "round_type": session_start.round_type,
        "question": session_start.question,
        "status": "ended" if ended else "in_progress",
        "checkpoint_count": checkpoint_count,
        "paused": _is_currently_paused(events),
        "latest_interviewer_action": latest_action,
        "latest_interviewer_text": latest_text,
        "source_session_id": getattr(session_start, "source_session_id", None),
    }

    if ended:
        summary["elapsed_seconds"] = events[-1].active_seconds
        record = report_generator.read_report_json(session_id)
        if record is not None:
            summary["verdict"] = record.verdict
            summary["scores"] = {d.dimension: d.score for d in record.dimensions}
    else:
        summary["elapsed_seconds"] = _elapsed_seconds(events, _now())

    return summary


def list_sessions() -> list[dict]:
    """Plain chronological session history for the UI's history view -
    session_id, round_type, question, date, status, and verdict (if
    graded). Newest first. Each summary also carries solver_session_id,
    the reverse link to a solver-comparison run derived from it (if any),
    so the UI can offer it without a separate lookup."""
    summaries = []
    for path in sorted(transcript_store.TRANSCRIPTS_DIR.glob("*.jsonl")):
        session_id = path.stem
        try:
            summary = get_session_summary(session_id)
        except (SessionEngineError, StopIteration):
            continue
        summaries.append(summary)

    by_source = {s["source_session_id"]: s["session_id"] for s in summaries if s.get("source_session_id")}
    for s in summaries:
        s["solver_session_id"] = by_source.get(s["session_id"])

    summaries.sort(key=lambda s: s["session_id"], reverse=True)
    return summaries


MAX_SOLVER_TURNS = 25  # flat cap: bounds a runaway solver regardless of the
                        # source session's own length; 25 comfortably covers
                        # any realistic interview round without risking an
                        # unbounded batch call.


def run_solver_comparison(source_session_id: str) -> dict:
    """Runs an offline SDE3/senior-persona candidate against the same live
    interviewer, for the same question the human was asked, producing a
    second graded session linked back via source_session_id. Blocking -
    this is a local single-user tool, so a synchronous batch call (many
    sequential LLM turns) is acceptable."""
    source_events = transcript_store.read_transcript(source_session_id)
    if not source_events:
        raise SessionEngineError(f"No session found with id {source_session_id!r}")
    session_start = next(e for e in source_events if e.event == "session_start")

    new_session = _start_session_core(
        session_start.round_type,
        session_start.question,
        session_start.question_provenance,
        source_session_id=source_session_id,
    )
    session_id = new_session["session_id"]

    for _ in range(MAX_SOLVER_TURNS):
        events = transcript_store.read_transcript(session_id)
        reply = solver_agent.respond(session_start.round_type, session_start.question, events)
        decision = save_checkpoint(session_id, reply.text, "solver")
        # reply.done reflects the solver's own sense of completeness, decided
        # before it has seen the interviewer's reaction to this very turn -
        # if the interviewer just raised a follow-up/interjection, that takes
        # priority and the solver must address it next turn regardless of
        # what it predicted about itself.
        if reply.done and decision["action"] == "continue":
            break

    result = end_session(session_id)
    result["source_session_id"] = source_session_id
    return result
