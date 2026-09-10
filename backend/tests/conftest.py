import os

import pytest

os.environ.setdefault("OBSIDIAN_VAULT_PATH", "/tmp/fake_vault")
os.environ.setdefault("EXCALIDRAW_EXPORT_PATH", "/tmp/fake_excalidraw")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-test")


@pytest.fixture(autouse=True)
def _isolated_data_dirs(tmp_path, monkeypatch):
    """Point every store module at a throwaway data dir for the test."""
    from backend import transcript_store, weakpoint_store

    monkeypatch.setattr(transcript_store, "TRANSCRIPTS_DIR", tmp_path / "transcripts")
    monkeypatch.setattr(weakpoint_store, "WEAKPOINTS_DIR", tmp_path / "weakpoints")
    yield
