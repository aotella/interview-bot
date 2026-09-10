import json

import pytest

from backend.grader_agent import GraderOutputError, grade_transcript
from backend.transcript_store import append_event


def _build_fixture_transcript(session_id: str) -> None:
    append_event(
        session_id,
        "session_start",
        {
            "session_id": session_id,
            "round_type": "hld",
            "question": "Design a rate limiter",
            "question_provenance": {
                "source_urls": ["https://example.com/q1"],
                "discovered_at": "t0",
                "target_level": "SSE",
                "seniority_eval": "ok",
            },
            "timestamp": "t0",
        },
    )
    append_event(
        session_id,
        "candidate_turn",
        {"checkpoint_id": "cp_1", "text": "no capacity estimation done", "input_mode": "typed", "timestamp": "t1"},
    )
    append_event(
        session_id,
        "interviewer_turn",
        {"checkpoint_id": "cp_1", "action": "interject", "text": "you skipped estimation", "timestamp": "t2"},
    )
    append_event(
        session_id,
        "session_end",
        {"wall_clock_seconds": 100, "active_seconds": 100, "paused_seconds": 0, "timestamp": "t3"},
    )


_HLD_DIMENSIONS = [
    "requirements_clarification",
    "capacity_estimation",
    "high_level_design",
    "deep_dive",
    "tradeoffs_stated",
    "failure_modes",
]


def _valid_grader_json(evidence_event_id: str) -> dict:
    return {
        "verdict": "REJECT",
        "dimensions": [
            {
                "dimension": dim,
                "score": 1,
                "evidence": [{"event_id": evidence_event_id, "reason": "example"}],
            }
            for dim in _HLD_DIMENSIONS
        ],
        "weak_point_outcomes": [
            {"tag": "capacity_estimation", "outcome": "failure"},
        ],
    }


def test_grader_accepts_valid_output_with_real_event_ids(monkeypatch):
    session_id = "s_grader_ok"
    _build_fixture_transcript(session_id)

    real_event_id = f"{session_id}_0002"  # the candidate_turn event

    def fake_complete(role, messages, **kwargs):
        assert role == "grader"
        return json.dumps(_valid_grader_json(real_event_id))

    monkeypatch.setattr("backend.structured_llm.complete", fake_complete)

    output = grade_transcript(session_id)

    assert output.verdict == "REJECT"
    assert {d.dimension for d in output.dimensions} == set(_HLD_DIMENSIONS)
    for d in output.dimensions:
        for ev in d.evidence:
            assert ev.event_id == real_event_id


def test_grader_rejects_invented_event_id_and_raises_after_retries(monkeypatch):
    session_id = "s_grader_bad"
    _build_fixture_transcript(session_id)

    def fake_complete(role, messages, **kwargs):
        return json.dumps(_valid_grader_json("s_grader_bad_9999"))  # never appended

    monkeypatch.setattr("backend.structured_llm.complete", fake_complete)

    with pytest.raises(GraderOutputError):
        grade_transcript(session_id)
