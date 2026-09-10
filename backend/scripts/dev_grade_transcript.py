"""Direct invocation of the grader agent against an existing transcript.
Run with: python -m backend.scripts.dev_grade_transcript --session s_2026-09-10-01

Loads any diagrams referenced by the transcript's diagram_attached events
from data/diagrams/{session_id}/ and passes their bytes to the grader -
see Flagged item 6 in PLAN.md for the batching/cap/fallback rules.
"""

import argparse
import base64
import json
from pathlib import Path

from backend.agent_schemas import DiagramImage
from backend.grader_agent import GraderOutputError, grade_transcript
from backend.transcript_store import read_transcript

DIAGRAMS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "diagrams"

_MEDIA_TYPES = {"png": "image/png", "svg": "image/svg+xml"}


def _load_diagrams(session_id: str) -> list[DiagramImage]:
    diagrams = []
    for event in read_transcript(session_id):
        if event.event != "diagram_attached":
            continue
        path = Path(event.path)
        if not path.is_absolute():
            path = DIAGRAMS_DIR / session_id / path.name
        if not path.exists():
            print(f"WARNING: diagram file missing, skipping: {path}")
            continue
        data_base64 = base64.b64encode(path.read_bytes()).decode("ascii")
        diagrams.append(
            DiagramImage(
                checkpoint_id=event.checkpoint_id,
                path=str(path),
                media_type=_MEDIA_TYPES[event.file_type],
                data_base64=data_base64,
            )
        )
    return diagrams


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    args = parser.parse_args()

    diagrams = _load_diagrams(args.session)
    try:
        output = grade_transcript(args.session, diagrams=diagrams)
    except GraderOutputError as e:
        print(f"FAILED: {e}")
        raise SystemExit(1)

    print(json.dumps(output.model_dump(), indent=2))


if __name__ == "__main__":
    main()
