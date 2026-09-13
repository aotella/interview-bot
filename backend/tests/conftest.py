import os

import pytest

os.environ.setdefault("EXCALIDRAW_EXPORT_PATH", "/tmp/fake_excalidraw")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-test")


@pytest.fixture(autouse=True)
def _isolated_data_dirs(tmp_path, monkeypatch):
    """Point every store module at a throwaway data dir for the test.

    report_generator.REPORTS_DIR and session_engine.STUDY_GUIDES_DIR must be
    isolated explicitly, not just transcript/weakpoint storage: they're
    module-level paths computed at import time, not read from config, so
    leaving either out lets tests silently write into the real data/
    directory. Because test session_ids are date-based and start counting
    from 1 within each test's empty tmp transcripts dir, they routinely
    collide with real same-day session_ids (e.g. every test's
    second-created session lands on s_<today>-02) and overwrite real data
    with fixture output - this happened for real on 2026-09-12 before this
    fixture covered report_generator.REPORTS_DIR.
    """
    from backend import report_generator, session_engine, transcript_store, weakpoint_store

    monkeypatch.setattr(transcript_store, "TRANSCRIPTS_DIR", tmp_path / "transcripts")
    monkeypatch.setattr(weakpoint_store, "WEAKPOINTS_DIR", tmp_path / "weakpoints")
    monkeypatch.setattr(report_generator, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(session_engine, "STUDY_GUIDES_DIR", tmp_path / "study_guides")
    yield
