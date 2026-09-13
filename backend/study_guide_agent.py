"""Generates a one-time, standalone HTML study guide grounded in a
solver-comparison session's transcript - a teaching document about the
underlying topics (API design, storage, queueing, scale trade-offs, etc.)
for this specific question, not a transcript replay. Generated once per
session and cached to disk by session_engine; this module only knows how
to produce the HTML given inputs, not where to store it.

Unlike the other agents, this one calls openrouter_client.complete
directly rather than structured_llm.complete_structured: the output is a
large free-form HTML document, and forcing that through a JSON schema
would mean escaping an entire HTML document inside a JSON string for no
real benefit - there's no structured field to validate here, just prose.
"""

from pathlib import Path

from backend.openrouter_client import complete

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_PROMPT_FILES = {
    "hld": "study_guide_hld_v1.md",
    "lld_deepdive": "study_guide_lld_deepdive_v1.md",
}


def _load_prompt(round_type: str) -> str:
    return (PROMPTS_DIR / _PROMPT_FILES[round_type]).read_text()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("html"):
            text = text[len("html"):]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _format_transcript(turns: list[dict]) -> str:
    lines = []
    for t in turns:
        label = t["speaker"].upper()
        if t.get("action"):
            label += f" - {t['action']}"
        lines.append(f"[{label}]\n{t['text']}")
    return "\n\n".join(lines)


def build_messages(round_type: str, question: str, turns: list[dict], weak_points: list[str]) -> list[dict]:
    system_prompt = _load_prompt(round_type)
    weak_points_text = ", ".join(weak_points) if weak_points else "none recorded"
    user_content = (
        f"Interview question:\n{question}\n\n"
        f"Reference candidate's conversation (ground the study guide in this, but go well beyond "
        f"it - fill in anything it only touched briefly or skipped):\n{_format_transcript(turns)}\n\n"
        f"Dimensions the human learner personally struggled with on this question - give these "
        f"extra depth: {weak_points_text}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def generate(round_type: str, question: str, turns: list[dict], weak_points: list[str]) -> str:
    messages = build_messages(round_type, question, turns, weak_points)
    raw = complete("study_guide", messages)
    return _strip_fences(raw)
