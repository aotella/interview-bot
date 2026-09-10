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
