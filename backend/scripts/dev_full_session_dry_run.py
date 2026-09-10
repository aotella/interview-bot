"""Drives one full fake session end-to-end through session_engine, live:
start -> 2-3 checkpoints -> pause/resume -> diagram attach -> end -> grade
-> weak-point update -> report write. Prints the transcript, weak-point
store, and report paths on success.

Run with: python -m backend.scripts.dev_full_session_dry_run --round hld

If EXCALIDRAW_EXPORT_PATH has no PNG/SVG files, writes a placeholder 1x1
PNG there first, so this script doesn't require a real Excalidraw setup
(Phase 8's end-to-end pass is when that needs to be real).
"""

import argparse
import base64
from pathlib import Path

from backend import config, session_engine, weakpoint_store
from backend.transcript_store import _transcript_path

# A minimal valid 1x1 transparent PNG, for dry-run diagram attach only.
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _ensure_placeholder_diagram() -> None:
    export_dir = Path(config.EXCALIDRAW_EXPORT_PATH)
    export_dir.mkdir(parents=True, exist_ok=True)
    if any(p.suffix.lower() in (".png", ".svg") for p in export_dir.glob("*")):
        return
    (export_dir / "dev_dry_run_placeholder.png").write_bytes(_PLACEHOLDER_PNG)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", required=True, choices=["hld", "lld_deepdive"])
    args = parser.parse_args()

    started = session_engine.start_session(args.round)
    session_id = started["session_id"]
    print(f"session_id={session_id}")
    print(f"question={started['question']}")

    turns = [
        ("Let me clarify requirements first: expected QPS, read/write ratio, and latency targets.", "typed"),
        ("Given ~50M requests/day, I'd estimate peak QPS around 5000 and design for 10x that at flash-sale peak.", "typed"),
        ("For the high-level design I'd shard by key hash across a distributed cache in front of the DB.", "typed"),
    ]
    for text, mode in turns:
        result = session_engine.save_checkpoint(session_id, text, mode)
        print(f"checkpoint {result['checkpoint_id']}: {result['action']}")

    session_engine.pause(session_id)
    print("paused")
    session_engine.resume(session_id)
    print("resumed")

    _ensure_placeholder_diagram()
    diagram = session_engine.attach_diagram(session_id, "cp_3")
    print(f"diagram attached: {diagram['path']}")

    outcome = session_engine.end_session(session_id)
    print(f"ended: {outcome}")

    print(f"transcript_path={_transcript_path(session_id)}")
    if outcome.get("graded"):
        print(f"weakpoint_store_path={weakpoint_store._store_path(started['round_type'])}")
        print(f"report_path={outcome['report_path']}")


if __name__ == "__main__":
    main()
