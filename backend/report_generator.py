"""Renders a completed session's grader output + transcript into a Markdown
report written into OBSIDIAN_VAULT_PATH. `scores` frontmatter keys are read
from the rubric config, never hardcoded, so an HLD report can never end up
with LLD dimensions or vice versa.
"""

from pathlib import Path

import yaml

from backend import config, rubric_loader, transcript_store
from backend.agent_schemas import GraderOutput


def _weak_point_phrases(grader_output: GraderOutput) -> list[str]:
    """Kebab-case rendering of each failed tag, derived mechanically from
    the tag name - not the narrative phrasing in the design doc's
    illustrative example (e.g. "skipped-capacity-estimation"), which reads
    as free-form prose rather than a literal spec. See Flagged item 3's
    resolution in PLAN.md: weak-point tags are exactly the rubric
    dimension names, and this field is a human-readable rendering derived
    from tag + outcome, not a separately stored value."""
    return [o.tag.replace("_", "-") for o in grader_output.weak_point_outcomes if o.outcome == "failure"]


def generate_report(session_id: str, grader_output: GraderOutput) -> Path:
    events = transcript_store.read_transcript(session_id)
    session_start = next(e for e in events if e.event == "session_start")
    session_end = next(e for e in events if e.event == "session_end")
    round_type = session_start.round_type

    rubric = rubric_loader.load_rubric(round_type)
    expected_dimensions = set(rubric.dimension_names())
    scores = {d.dimension: d.score for d in grader_output.dimensions}
    if set(scores.keys()) != expected_dimensions:
        raise ValueError(
            f"grader_output dimensions {sorted(scores.keys())} do not match "
            f"rubric dimensions {sorted(expected_dimensions)} for round_type={round_type!r}"
        )

    pause_events = [e for e in events if e.event in ("pause_start", "pause_end")]
    pause_count = sum(1 for e in pause_events if e.event == "pause_start")
    pause_total_seconds = sum(e.duration_seconds for e in events if e.event == "pause_end")

    diagram_links = [f"[[{Path(e.path).name}]]" for e in events if e.event == "diagram_attached"]

    rubric_version_by_round = {
        "hld": config.rubric_version.hld,
        "lld_deepdive": config.rubric_version.lld_deepdive,
    }

    frontmatter = {
        "session_id": session_id,
        "date": session_start.timestamp[:10],
        "round_type": round_type,
        "question": session_start.question,
        "verdict": grader_output.verdict,
        "scores": scores,
        "weak_points": _weak_point_phrases(grader_output),
        "diagrams": diagram_links,
        "pauses": {"count": pause_count, "total_seconds": pause_total_seconds},
        "durations": {
            "wall_clock_seconds": session_end.wall_clock_seconds,
            "active_seconds": session_end.active_seconds,
            "paused_seconds": session_end.paused_seconds,
        },
        "rubric_version": rubric_version_by_round[round_type],
        "interviewer_prompt_version": config.interviewer_prompt_version,
        "grader_prompt_version": config.grader_prompt_version,
        "question_sourcing_version": config.question_sourcing_prompt_version,
        "models": {
            "interviewer": config.models.interviewer,
            "grader": config.models.grader,
            "question_sourcing": config.models.question_sourcing,
        },
    }

    body_lines = [f"# {session_start.question}", ""]
    for dim in grader_output.dimensions:
        body_lines.append(f"## {dim.dimension} - {dim.score}/{rubric.score_range[1]}")
        for ev in dim.evidence:
            body_lines.append(f"- ({ev.event_id}) {ev.reason}")
        body_lines.append("")

    content = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n" + "\n".join(body_lines)

    vault_path = Path(config.OBSIDIAN_VAULT_PATH)
    vault_path.mkdir(parents=True, exist_ok=True)
    report_path = vault_path / f"{session_id}.md"
    report_path.write_text(content)
    return report_path


def read_report_frontmatter(session_id: str) -> dict | None:
    """Read back a previously-written report's YAML frontmatter (verdict,
    scores, etc.) - the API layer uses this rather than duplicating
    grader-output storage, since the report is already the persisted
    structured record of a completed grading."""
    report_path = Path(config.OBSIDIAN_VAULT_PATH) / f"{session_id}.md"
    if not report_path.exists():
        return None
    parts = report_path.read_text().split("---", 2)
    if len(parts) < 3:
        return None
    return yaml.safe_load(parts[1])
