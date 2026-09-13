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
        # weak_point_outcomes must exactly match every scored (non-null)
        # dimension - one outcome per dimension above, no more, no fewer.
        "weak_point_outcomes": [{"tag": dim, "outcome": "failure"} for dim in _HLD_DIMENSIONS],
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


_LLD_DIMENSIONS = [
    "requirements_clarification",
    "class_and_interface_design",
    "concurrency_and_edge_cases",
    "extensibility_tradeoffs",
    "deep_dive_depth",
    "communication_of_tradeoffs",
]


def _build_fixture_transcript_lld(session_id: str) -> None:
    append_event(
        session_id,
        "session_start",
        {
            "session_id": session_id,
            "round_type": "lld_deepdive",
            "question": "Design a parking lot",
            "question_provenance": {
                "source_urls": ["https://example.com/q2"],
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
        {"checkpoint_id": "cp_1", "text": "no concurrency handling mentioned", "input_mode": "typed", "timestamp": "t1"},
    )
    append_event(
        session_id,
        "interviewer_turn",
        {"checkpoint_id": "cp_1", "action": "interject", "text": "what about concurrent spot reservations?", "timestamp": "t2"},
    )
    append_event(
        session_id,
        "session_end",
        {"wall_clock_seconds": 100, "active_seconds": 100, "paused_seconds": 0, "timestamp": "t3"},
    )


def test_grader_accepts_valid_lld_output_with_real_event_ids(monkeypatch):
    session_id = "s_grader_lld_ok"
    _build_fixture_transcript_lld(session_id)

    real_event_id = f"{session_id}_0002"  # the candidate_turn event

    def fake_complete(role, messages, **kwargs):
        assert role == "grader"
        return json.dumps(
            {
                "verdict": "REJECT",
                "dimensions": [
                    {
                        "dimension": dim,
                        "score": 1,
                        "evidence": [{"event_id": real_event_id, "reason": "example"}],
                    }
                    for dim in _LLD_DIMENSIONS
                ],
                "weak_point_outcomes": [{"tag": dim, "outcome": "failure"} for dim in _LLD_DIMENSIONS],
            }
        )

    monkeypatch.setattr("backend.structured_llm.complete", fake_complete)

    output = grade_transcript(session_id)

    assert output.verdict == "REJECT"
    assert {d.dimension for d in output.dimensions} == set(_LLD_DIMENSIONS)


def _grader_json_with_one_null(real_event_id: str, null_dim: str) -> dict:
    """Every HLD dimension scored 1 except `null_dim`, which is null with
    no evidence - and correspondingly omitted from weak_point_outcomes."""
    dimensions = []
    weak_point_outcomes = []
    for dim in _HLD_DIMENSIONS:
        if dim == null_dim:
            dimensions.append({"dimension": dim, "score": None, "evidence": []})
        else:
            dimensions.append(
                {
                    "dimension": dim,
                    "score": 1,
                    "evidence": [{"event_id": real_event_id, "reason": "example"}],
                }
            )
            weak_point_outcomes.append({"tag": dim, "outcome": "failure"})
    return {"verdict": "REJECT", "dimensions": dimensions, "weak_point_outcomes": weak_point_outcomes}


def test_grader_accepts_null_score_with_no_evidence(monkeypatch):
    session_id = "s_grader_null_ok"
    _build_fixture_transcript(session_id)
    real_event_id = f"{session_id}_0002"

    def fake_complete(role, messages, **kwargs):
        return json.dumps(_grader_json_with_one_null(real_event_id, "deep_dive"))

    monkeypatch.setattr("backend.structured_llm.complete", fake_complete)

    output = grade_transcript(session_id)

    scores = {d.dimension: d.score for d in output.dimensions}
    assert scores["deep_dive"] is None
    assert "deep_dive" not in {wpo.tag for wpo in output.weak_point_outcomes}


def test_grader_rejects_null_score_with_evidence(monkeypatch):
    session_id = "s_grader_null_bad_evidence"
    _build_fixture_transcript(session_id)
    real_event_id = f"{session_id}_0002"

    def fake_complete(role, messages, **kwargs):
        payload = _grader_json_with_one_null(real_event_id, "deep_dive")
        # A null score must cite no evidence - attach some anyway.
        for d in payload["dimensions"]:
            if d["dimension"] == "deep_dive":
                d["evidence"] = [{"event_id": real_event_id, "reason": "shouldn't be here"}]
        return json.dumps(payload)

    monkeypatch.setattr("backend.structured_llm.complete", fake_complete)

    with pytest.raises(GraderOutputError):
        grade_transcript(session_id)


def test_grader_rejects_real_score_with_no_evidence(monkeypatch):
    session_id = "s_grader_real_score_no_evidence"
    _build_fixture_transcript(session_id)
    real_event_id = f"{session_id}_0002"

    def fake_complete(role, messages, **kwargs):
        payload = _valid_grader_json(real_event_id)
        # A real (non-null) score must cite at least one evidence entry.
        for d in payload["dimensions"]:
            if d["dimension"] == "deep_dive":
                d["evidence"] = []
        return json.dumps(payload)

    monkeypatch.setattr("backend.structured_llm.complete", fake_complete)

    with pytest.raises(GraderOutputError):
        grade_transcript(session_id)


def test_grader_rejects_null_tag_leaking_into_weak_point_outcomes(monkeypatch):
    session_id = "s_grader_null_leaks_into_wpo"
    _build_fixture_transcript(session_id)
    real_event_id = f"{session_id}_0002"

    def fake_complete(role, messages, **kwargs):
        payload = _grader_json_with_one_null(real_event_id, "deep_dive")
        # deep_dive is null in `dimensions` but incorrectly given an
        # outcome anyway - the two lists must correspond exactly.
        payload["weak_point_outcomes"].append({"tag": "deep_dive", "outcome": "failure"})
        return json.dumps(payload)

    monkeypatch.setattr("backend.structured_llm.complete", fake_complete)

    with pytest.raises(GraderOutputError):
        grade_transcript(session_id)


def test_grader_rejects_scored_dimension_missing_from_weak_point_outcomes(monkeypatch):
    session_id = "s_grader_scored_missing_from_wpo"
    _build_fixture_transcript(session_id)
    real_event_id = f"{session_id}_0002"

    def fake_complete(role, messages, **kwargs):
        payload = _valid_grader_json(real_event_id)
        # Every dimension has a real score, but one is silently missing
        # from weak_point_outcomes - the mirror-image bug to a leaked null
        # tag: it would undercount a real weakness the same way.
        payload["weak_point_outcomes"] = [
            wpo for wpo in payload["weak_point_outcomes"] if wpo["tag"] != "deep_dive"
        ]
        return json.dumps(payload)

    monkeypatch.setattr("backend.structured_llm.complete", fake_complete)

    with pytest.raises(GraderOutputError):
        grade_transcript(session_id)
