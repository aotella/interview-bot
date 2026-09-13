from backend import config, report_generator, session_engine, weakpoint_store
from backend.agent_schemas import (
    Evidence,
    DimensionScore,
    GraderOutput,
    InterviewerDecision,
    SeniorityEval,
    SolverResponse,
    SourcedQuestion,
    WeakPointOutcome,
)
from backend.schemas import QuestionProvenance
from backend.transcript_store import read_transcript

_HLD_DIMENSIONS = [
    "requirements_clarification",
    "capacity_estimation",
    "high_level_design",
    "deep_dive",
    "tradeoffs_stated",
    "failure_modes",
]


def _fake_sourced_question(round_type: str, rng=None) -> SourcedQuestion:
    return SourcedQuestion(
        question="Design a rate limiter",
        round_type=round_type,
        target_tag="capacity_estimation",
        provenance=QuestionProvenance(
            source_urls=["https://example.com"],
            discovered_at="t0",
            target_level="SSE",
            seniority_eval="ok",
        ),
    )


def _fake_decide(running_state, checkpoint_id, candidate_text):
    return InterviewerDecision(action="continue", text="")


def _fake_grade(session_id, diagrams=None):
    events = read_transcript(session_id)
    evidence_id = next(e.event_id for e in events if e.event == "candidate_turn")
    return GraderOutput(
        verdict="REJECT",
        dimensions=[
            DimensionScore(dimension=dim, score=1, evidence=[Evidence(event_id=evidence_id, reason="x")])
            for dim in _HLD_DIMENSIONS
        ],
        weak_point_outcomes=[WeakPointOutcome(tag="capacity_estimation", outcome="failure")],
    )


def _patch_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(session_engine.question_sourcing, "source_question", _fake_sourced_question)
    monkeypatch.setattr(session_engine.interviewer_agent, "decide", _fake_decide)
    monkeypatch.setattr(session_engine.grader_agent, "grade_transcript", _fake_grade)

    excalidraw_dir = tmp_path / "excalidraw"
    excalidraw_dir.mkdir()
    (excalidraw_dir / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n fake")

    monkeypatch.setattr(config, "EXCALIDRAW_EXPORT_PATH", str(excalidraw_dir))
    monkeypatch.setattr(session_engine, "DIAGRAMS_DIR", tmp_path / "diagrams")


def test_full_session_lifecycle(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)

    started = session_engine.start_session("hld")
    session_id = started["session_id"]

    session_engine.save_checkpoint(session_id, "first answer", "typed")
    session_engine.save_checkpoint(session_id, "second answer", "typed")

    session_engine.pause(session_id)
    session_engine.resume(session_id)

    session_engine.attach_diagram(session_id, "cp_2")

    outcome = session_engine.end_session(session_id)

    assert outcome["graded"] is True
    assert outcome["verdict"] == "REJECT"

    events = read_transcript(session_id)
    assert events[-1].event == "session_end"
    assert events[-1].active_seconds + events[-1].paused_seconds == events[-1].wall_clock_seconds

    record = report_generator.read_report_json(session_id)
    assert record is not None
    assert record.verdict == "REJECT"
    assert {d.dimension for d in record.dimensions} == set(_HLD_DIMENSIONS)
    assert record.rubric_version == config.rubric_version.hld
    assert (
        record.durations["wall_clock_seconds"]
        == record.durations["active_seconds"] + record.durations["paused_seconds"]
    )


def test_running_state_carries_past_interviewer_text(monkeypatch, tmp_path):
    """The interviewer's own prompt tells it to check past checkpoints for a
    posed-but-unanswered follow_up/interject before deciding `continue` - so
    the running state it's given must actually carry that text, not just the
    past action."""
    _patch_engine(monkeypatch, tmp_path)

    decisions = iter([
        InterviewerDecision(action="follow_up", text="what about the backup provider?"),
        InterviewerDecision(action="continue", text=""),
    ])
    captured_states = []

    def _fake_decide(running_state, checkpoint_id, candidate_text):
        captured_states.append(running_state)
        return next(decisions)

    monkeypatch.setattr(session_engine.interviewer_agent, "decide", _fake_decide)

    started = session_engine.start_session("hld")
    session_id = started["session_id"]
    session_engine.save_checkpoint(session_id, "first answer", "typed")
    session_engine.save_checkpoint(session_id, "second answer", "typed")

    second_call_state = captured_states[1]
    assert len(second_call_state.checkpoints) == 1
    assert second_call_state.checkpoints[0].action == "follow_up"
    assert second_call_state.checkpoints[0].interviewer_text == "what about the backup provider?"


def test_transcript_immutable_after_end_session(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)

    started = session_engine.start_session("hld")
    session_id = started["session_id"]
    session_engine.save_checkpoint(session_id, "answer", "typed")
    session_engine.end_session(session_id)

    try:
        session_engine.save_checkpoint(session_id, "too late", "typed")
        assert False, "expected SessionEngineError"
    except session_engine.SessionEngineError:
        pass


def test_get_session_report_returns_full_grader_output(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)

    started = session_engine.start_session("hld")
    session_id = started["session_id"]
    session_engine.save_checkpoint(session_id, "first answer", "typed")
    session_engine.end_session(session_id)

    report = session_engine.get_session_report(session_id)

    assert report["session_id"] == session_id
    assert report["verdict"] == "REJECT"
    assert {d["dimension"] for d in report["dimensions"]} == set(_HLD_DIMENSIONS)
    events = read_transcript(session_id)
    real_event_id = next(e.event_id for e in events if e.event == "candidate_turn")
    for d in report["dimensions"]:
        for ev in d["evidence"]:
            assert ev["event_id"] == real_event_id
    assert report["source_session_id"] is None


def test_get_session_transcript_returns_ordered_turns(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)

    started = session_engine.start_session("hld")
    session_id = started["session_id"]
    session_engine.save_checkpoint(session_id, "first answer", "typed")
    session_engine.save_checkpoint(session_id, "second answer", "typed")

    transcript = session_engine.get_session_transcript(session_id)

    assert transcript["session_id"] == session_id
    assert transcript["question"] == "Design a rate limiter"
    # _fake_decide always returns action="continue", which carries no
    # visible text and is skipped - so only the two candidate turns show up.
    assert transcript["turns"] == [
        {"speaker": "candidate", "action": None, "text": "first answer"},
        {"speaker": "candidate", "action": None, "text": "second answer"},
    ]


def test_generate_and_get_study_guide(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)

    def _fake_generate(round_type, question, turns, weak_points):
        return f"<html><body>{question} / weak={weak_points}</body></html>"

    monkeypatch.setattr(session_engine.study_guide_agent, "generate", _fake_generate)

    started = session_engine.start_session("hld")
    session_id = started["session_id"]
    session_engine.save_checkpoint(session_id, "first answer", "typed")
    session_engine.end_session(session_id)

    assert session_engine.get_study_guide(session_id) is None

    result = session_engine.generate_study_guide(session_id)
    assert result["session_id"] == session_id

    html = session_engine.get_study_guide(session_id)
    assert "Design a rate limiter" in html
    assert "weak=[]" in html


def test_generate_study_guide_passes_source_weak_points(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)

    captured = {}

    def _fake_generate(round_type, question, turns, weak_points):
        captured["weak_points"] = weak_points
        return "<html></html>"

    monkeypatch.setattr(session_engine.study_guide_agent, "generate", _fake_generate)
    monkeypatch.setattr(session_engine.solver_agent, "respond", lambda *a, **k: SolverResponse(text="answer", done=True))

    started = session_engine.start_session("hld")
    source_session_id = started["session_id"]
    session_engine.save_checkpoint(source_session_id, "first answer", "typed")
    session_engine.end_session(source_session_id)  # weak_point_outcomes: capacity_estimation=failure

    solver_result = session_engine.run_solver_comparison(source_session_id)
    session_engine.generate_study_guide(solver_result["session_id"])

    assert captured["weak_points"] == ["capacity_estimation"]


def test_get_session_report_before_end_raises(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)

    started = session_engine.start_session("hld")
    session_id = started["session_id"]
    session_engine.save_checkpoint(session_id, "first answer", "typed")

    try:
        session_engine.get_session_report(session_id)
        assert False, "expected SessionEngineError"
    except session_engine.SessionEngineError:
        pass


def test_get_weakpoints_computes_success_rate(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)

    weakpoint_store.record_outcome("hld", "capacity_estimation", "success")
    weakpoint_store.record_outcome("hld", "capacity_estimation", "failure")

    result = session_engine.get_weakpoints("hld")

    assert result["capacity_estimation"]["opportunities"] == 2
    assert result["capacity_estimation"]["success_rate"] == 0.5


def test_get_weakpoints_empty_round_type(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)
    assert session_engine.get_weakpoints("hld") == {}


def _fake_solver_respond_done(round_type, question, events):
    return SolverResponse(text="a strong senior-level answer", done=True)


def test_run_solver_comparison_skips_weakpoints(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)
    monkeypatch.setattr(session_engine.solver_agent, "respond", _fake_solver_respond_done)

    started = session_engine.start_session("hld")
    source_session_id = started["session_id"]
    session_engine.save_checkpoint(source_session_id, "first answer", "typed")
    session_engine.end_session(source_session_id)

    before = weakpoint_store.load("hld")
    result = session_engine.run_solver_comparison(source_session_id)
    after = weakpoint_store.load("hld")

    assert result["graded"] is True
    assert after == before


def test_run_solver_comparison_records_source_session_id(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)
    monkeypatch.setattr(session_engine.solver_agent, "respond", _fake_solver_respond_done)

    started = session_engine.start_session("hld")
    source_session_id = started["session_id"]
    session_engine.save_checkpoint(source_session_id, "first answer", "typed")
    session_engine.end_session(source_session_id)

    result = session_engine.run_solver_comparison(source_session_id)
    new_session_id = result["session_id"]

    assert result["source_session_id"] == source_session_id
    summary = session_engine.get_session_summary(new_session_id)
    assert summary["source_session_id"] == source_session_id

    sessions = {s["session_id"]: s for s in session_engine.list_sessions()}
    assert sessions[source_session_id]["solver_session_id"] == new_session_id


def test_run_solver_comparison_respects_turn_cap(monkeypatch, tmp_path):
    _patch_engine(monkeypatch, tmp_path)
    monkeypatch.setattr(session_engine, "MAX_SOLVER_TURNS", 2)

    def _never_done(round_type, question, events):
        return SolverResponse(text="still going", done=False)

    monkeypatch.setattr(session_engine.solver_agent, "respond", _never_done)

    started = session_engine.start_session("hld")
    source_session_id = started["session_id"]
    session_engine.save_checkpoint(source_session_id, "first answer", "typed")
    session_engine.end_session(source_session_id)

    result = session_engine.run_solver_comparison(source_session_id)

    assert result["graded"] is True
    new_events = read_transcript(result["session_id"])
    assert sum(1 for e in new_events if e.event == "candidate_turn") == 2


def test_run_solver_comparison_answers_late_follow_up(monkeypatch, tmp_path):
    """A solver turn can claim done=True before it has seen the
    interviewer's reaction to it. If that reaction is a follow_up/interject,
    the loop must keep going so the solver actually answers it, rather than
    ending the session on the solver's stale self-assessment."""
    _patch_engine(monkeypatch, tmp_path)
    monkeypatch.setattr(session_engine.solver_agent, "respond", _fake_solver_respond_done)

    started = session_engine.start_session("hld")
    source_session_id = started["session_id"]
    session_engine.save_checkpoint(source_session_id, "first answer", "typed")
    session_engine.end_session(source_session_id)

    decisions = iter([
        InterviewerDecision(action="follow_up", text="what about the backup provider?"),
        InterviewerDecision(action="continue", text=""),
    ])
    monkeypatch.setattr(
        session_engine.interviewer_agent, "decide",
        lambda running_state, checkpoint_id, candidate_text: next(decisions),
    )

    result = session_engine.run_solver_comparison(source_session_id)

    assert result["graded"] is True
    new_events = read_transcript(result["session_id"])
    assert sum(1 for e in new_events if e.event == "candidate_turn") == 2
    follow_ups = [e for e in new_events if e.event == "interviewer_turn" and e.action == "follow_up"]
    assert len(follow_ups) == 1
