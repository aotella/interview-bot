from fastapi.testclient import TestClient

from backend.app import app
from backend.session_engine import SessionEngineError

client = TestClient(app)


def test_invalid_round_type_returns_422():
    resp = client.post("/sessions", json={"round_type": "not_a_real_round"})
    assert resp.status_code == 422


def test_start_session_routes_to_session_engine(monkeypatch):
    monkeypatch.setattr(
        "backend.session_engine.start_session",
        lambda round_type: {"session_id": "s_fake-01", "round_type": round_type, "question": "Q"},
    )
    resp = client.post("/sessions", json={"round_type": "hld"})
    assert resp.status_code == 200
    assert resp.json() == {"session_id": "s_fake-01", "round_type": "hld", "question": "Q"}


def test_unknown_session_returns_404(monkeypatch):
    def _raise(session_id):
        raise SessionEngineError(f"No session found with id {session_id!r}")

    monkeypatch.setattr("backend.session_engine.get_session_summary", _raise)
    resp = client.get("/sessions/does_not_exist")
    assert resp.status_code == 404


def test_session_engine_error_on_action_route_returns_400(monkeypatch):
    def _raise(session_id):
        raise SessionEngineError("already paused")

    monkeypatch.setattr("backend.session_engine.pause", _raise)
    resp = client.post("/sessions/s_fake-01/pause")
    assert resp.status_code == 400


def test_get_report_routes_to_session_engine(monkeypatch):
    canned = {"session_id": "s_fake-01", "verdict": "REJECT", "dimensions": []}
    monkeypatch.setattr("backend.session_engine.get_session_report", lambda session_id: canned)
    resp = client.get("/sessions/s_fake-01/report")
    assert resp.status_code == 200
    assert resp.json() == canned


def test_get_report_unknown_session_returns_404(monkeypatch):
    def _raise(session_id):
        raise SessionEngineError(f"No session found with id {session_id!r}")

    monkeypatch.setattr("backend.session_engine.get_session_report", _raise)
    resp = client.get("/sessions/does_not_exist/report")
    assert resp.status_code == 404


def test_get_transcript_routes_to_session_engine(monkeypatch):
    canned = {"session_id": "s_fake-01", "round_type": "hld", "question": "Q", "turns": []}
    monkeypatch.setattr("backend.session_engine.get_session_transcript", lambda session_id: canned)
    resp = client.get("/sessions/s_fake-01/transcript")
    assert resp.status_code == 200
    assert resp.json() == canned


def test_study_guide_exists_routes_to_session_engine(monkeypatch):
    monkeypatch.setattr("backend.session_engine.study_guide_exists", lambda session_id: True)
    resp = client.get("/sessions/s_fake-01/study-guide/exists")
    assert resp.status_code == 200
    assert resp.json() == {"exists": True}


def test_get_study_guide_returns_html(monkeypatch):
    monkeypatch.setattr("backend.session_engine.get_study_guide", lambda session_id: "<html>hi</html>")
    resp = client.get("/sessions/s_fake-01/study-guide")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == "<html>hi</html>"


def test_get_study_guide_missing_returns_404(monkeypatch):
    monkeypatch.setattr("backend.session_engine.get_study_guide", lambda session_id: None)
    resp = client.get("/sessions/s_fake-01/study-guide")
    assert resp.status_code == 404


def test_create_study_guide_routes_to_session_engine(monkeypatch):
    canned = {"session_id": "s_fake-01", "path": "/tmp/x.html"}
    monkeypatch.setattr("backend.session_engine.generate_study_guide", lambda session_id: canned)
    resp = client.post("/sessions/s_fake-01/study-guide")
    assert resp.status_code == 200
    assert resp.json() == canned


def test_get_weakpoints_routes_to_session_engine(monkeypatch):
    monkeypatch.setattr("backend.session_engine.get_weakpoints", lambda round_type: {})
    resp = client.get("/weakpoints/hld")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_solver_comparison_routes_to_session_engine(monkeypatch):
    canned = {"session_id": "s_fake-02", "graded": True, "verdict": "SELECT", "source_session_id": "s_fake-01"}
    monkeypatch.setattr("backend.session_engine.run_solver_comparison", lambda session_id: canned)
    resp = client.post("/sessions/s_fake-01/solver-comparison")
    assert resp.status_code == 200
    assert resp.json() == canned
