from backend import config, session_engine
from backend.agent_schemas import (
    Evidence,
    DimensionScore,
    GraderOutput,
    InterviewerDecision,
    SeniorityEval,
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

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    monkeypatch.setattr(config, "EXCALIDRAW_EXPORT_PATH", str(excalidraw_dir))
    monkeypatch.setattr(config, "OBSIDIAN_VAULT_PATH", str(vault_dir))
    monkeypatch.setattr(session_engine, "DIAGRAMS_DIR", tmp_path / "diagrams")
    return vault_dir


def test_full_session_lifecycle(monkeypatch, tmp_path):
    vault_dir = _patch_engine(monkeypatch, tmp_path)

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

    report_path = vault_dir / f"{session_id}.md"
    assert report_path.exists()
    frontmatter_text = report_path.read_text().split("---")[1]
    import yaml

    frontmatter = yaml.safe_load(frontmatter_text)
    assert set(frontmatter["scores"].keys()) == set(_HLD_DIMENSIONS)
    assert frontmatter["verdict"] == "REJECT"


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
