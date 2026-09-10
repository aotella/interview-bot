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
from backend import transcript_store, weakpoint_store
from backend.agent_schemas import CheckpointSummary, DiagramImage, PauseRecord, RunningState
from backend.grader_agent import GraderOutputError
from backend.schemas import TranscriptEvent

DIAGRAMS_DIR = Path(__file__).resolve().parent.parent / "data" / "diagrams"

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
            CheckpointSummary(checkpoint_id=e.checkpoint_id, candidate_text=e.text, action=it.action)
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


def start_session(round_type: str) -> dict:
    now = _now()
    sourced = question_sourcing.source_question(round_type)
    session_id = _next_session_id(now)
    transcript_store.append_event(
        session_id,
        "session_start",
        {
            "session_id": session_id,
            "round_type": round_type,
            "question": sourced.question,
            "question_provenance": sourced.provenance.model_dump(),
            "timestamp": now.isoformat(),
        },
    )
    return {"session_id": session_id, "round_type": round_type, "question": sourced.question}


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


def get_session_summary(session_id: str) -> dict:
    """Session summary for the UI: elapsed time, latest interviewer
    decision/text (only when not `continue`), pause state, checkpoint
    count while in progress; verdict/scores once ended and graded. Never
    the full transcript or report - the UI doesn't duplicate Obsidian."""
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
    }

    if ended:
        summary["elapsed_seconds"] = events[-1].active_seconds
        frontmatter = report_generator.read_report_frontmatter(session_id)
        if frontmatter is not None:
            summary["verdict"] = frontmatter.get("verdict")
            summary["scores"] = frontmatter.get("scores")
    else:
        summary["elapsed_seconds"] = _elapsed_seconds(events, _now())

    return summary


def list_sessions() -> list[dict]:
    """Plain chronological session history for the UI's history view -
    session_id, round_type, question, date, status, and verdict (if
    graded). Newest first."""
    summaries = []
    for path in sorted(transcript_store.TRANSCRIPTS_DIR.glob("*.jsonl")):
        session_id = path.stem
        try:
            summary = get_session_summary(session_id)
        except (SessionEngineError, StopIteration):
            continue
        summaries.append(summary)
    summaries.sort(key=lambda s: s["session_id"], reverse=True)
    return summaries
