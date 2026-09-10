"""Append-only JSONL transcript writer.

One file per session at `data/transcripts/{session_id}.jsonl`. The
application-level guarantee is that no code path writes to a transcript
after its `session_end` event has been appended - `append_event` enforces
this by refusing the write, and the file is additionally chmod'd read-only
as a cheap secondary safeguard (not the mechanism itself).

`event_id` is assigned here, not by the caller: it's
`f"{session_id}_{seq:04d}"` where `seq` is a monotonic per-session counter
derived from how many events are already on disk. This guarantees
uniqueness even across multiple events sharing the same `checkpoint_id`
(e.g. a candidate_turn followed by an interviewer_turn at the same
checkpoint).
"""

import json
import os
import stat
from pathlib import Path

from backend.schemas import TranscriptEvent, parse_event

TRANSCRIPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "transcripts"


class TranscriptClosedError(RuntimeError):
    """Raised when an append is attempted on a transcript that already has
    a session_end event."""


def _transcript_path(session_id: str) -> Path:
    return TRANSCRIPTS_DIR / f"{session_id}.jsonl"


def _read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r") as f:
        return [json.loads(line) for line in f if line.strip()]


def is_closed(session_id: str) -> bool:
    """True if this session's transcript already ends with session_end."""
    lines = _read_lines(_transcript_path(session_id))
    return bool(lines) and lines[-1].get("event") == "session_end"


def append_event(session_id: str, event_type: str, fields: dict) -> TranscriptEvent:
    """Validate and append one event to the session's transcript.

    `fields` holds every field for the event type except `event` and
    `event_id`, both of which are assigned here.

    Raises TranscriptClosedError if this session's transcript already has a
    session_end event.
    """
    path = _transcript_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = _read_lines(path)
    if existing and existing[-1].get("event") == "session_end":
        raise TranscriptClosedError(
            f"Transcript for session {session_id!r} is already closed "
            f"(session_end already written); refusing to append {event_type!r}."
        )

    seq = len(existing) + 1
    event_id = f"{session_id}_{seq:04d}"
    raw = {**fields, "event": event_type, "event_id": event_id}
    event = parse_event(raw)

    with path.open("a") as f:
        f.write(event.model_dump_json())
        f.write("\n")

    if event_type == "session_end":
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    return event


def read_transcript(session_id: str) -> list[TranscriptEvent]:
    """Read and parse every event in a session's transcript, in order."""
    return [parse_event(raw) for raw in _read_lines(_transcript_path(session_id))]
