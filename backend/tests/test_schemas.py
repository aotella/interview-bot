import pytest

from backend import transcript_store as ts
from backend.transcript_store import TranscriptClosedError, append_event, read_transcript


def _start_session(session_id: str):
    return append_event(
        session_id,
        "session_start",
        {
            "session_id": session_id,
            "round_type": "hld",
            "question": "Design a rate limiter",
            "question_provenance": {
                "source_urls": ["https://example.com/q1"],
                "discovered_at": "2026-09-10T10:00:00Z",
                "target_level": "SSE",
                "seniority_eval": "requires scale tradeoffs",
            },
            "timestamp": "2026-09-10T10:00:00Z",
        },
    )


def test_event_round_trip():
    session_id = "s_test_roundtrip"
    _start_session(session_id)
    append_event(
        session_id,
        "candidate_turn",
        {
            "checkpoint_id": "cp_1",
            "text": "I'd start with requirements clarification.",
            "input_mode": "typed",
            "timestamp": "2026-09-10T10:01:00Z",
        },
    )
    append_event(
        session_id,
        "interviewer_turn",
        {
            "checkpoint_id": "cp_1",
            "action": "continue",
            "text": "",
            "timestamp": "2026-09-10T10:01:05Z",
        },
    )

    events = read_transcript(session_id)
    assert [e.event for e in events] == ["session_start", "candidate_turn", "interviewer_turn"]
    assert events[0].event_id == f"{session_id}_0001"
    assert events[1].event_id == f"{session_id}_0002"
    assert events[2].event_id == f"{session_id}_0003"


def test_event_ids_unique_across_same_checkpoint():
    session_id = "s_test_same_checkpoint"
    _start_session(session_id)
    e1 = append_event(
        session_id,
        "candidate_turn",
        {"checkpoint_id": "cp_1", "text": "first pass", "input_mode": "typed", "timestamp": "t1"},
    )
    e2 = append_event(
        session_id,
        "interviewer_turn",
        {"checkpoint_id": "cp_1", "action": "follow_up", "text": "why?", "timestamp": "t2"},
    )
    # A user edits/re-answers at the same checkpoint.
    e3 = append_event(
        session_id,
        "candidate_turn",
        {"checkpoint_id": "cp_1", "text": "revised answer", "input_mode": "typed", "timestamp": "t3"},
    )

    ids = [e1.event_id, e2.event_id, e3.event_id]
    assert len(ids) == len(set(ids))
    seqs = [int(i.rsplit("_", 1)[1]) for i in ids]
    assert seqs == sorted(seqs)


def test_append_rejected_after_session_end():
    session_id = "s_test_closed"
    _start_session(session_id)
    append_event(
        session_id,
        "session_end",
        {
            "wall_clock_seconds": 100,
            "active_seconds": 100,
            "paused_seconds": 0,
            "timestamp": "t_end",
        },
    )

    path = ts._transcript_path(session_id)
    line_count_before = len(path.read_text().splitlines())

    with pytest.raises(TranscriptClosedError):
        append_event(
            session_id,
            "candidate_turn",
            {"checkpoint_id": "cp_99", "text": "too late", "input_mode": "typed", "timestamp": "t_late"},
        )

    assert len(path.read_text().splitlines()) == line_count_before
