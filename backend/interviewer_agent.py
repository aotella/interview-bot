"""Live interviewer agent: one call per checkpoint, deciding
continue|follow_up|interject from the lightweight running state plus the
newest candidate turn. Never loads or references the rubric - the rubric
must stay hidden from the session-facing interviewer persona."""

import json
from pathlib import Path

from backend.agent_schemas import InterviewerDecision, RunningState
from backend.structured_llm import complete_structured

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_PROMPT_FILES = {
    "hld": "interviewer_hld_v1.md",
    "lld_deepdive": "interviewer_lld_deepdive_v1.md",
}


def _load_prompt(round_type: str) -> str:
    return (PROMPTS_DIR / _PROMPT_FILES[round_type]).read_text()


def build_messages(running_state: RunningState, checkpoint_id: str, candidate_text: str) -> list[dict]:
    system_prompt = _load_prompt(running_state.round_type)
    state_json = json.dumps(running_state.model_dump(), indent=2)
    user_content = (
        f"Running state:\n{state_json}\n\n"
        f"New candidate turn (checkpoint_id={checkpoint_id}):\n{candidate_text}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def decide(running_state: RunningState, checkpoint_id: str, candidate_text: str) -> InterviewerDecision:
    messages = build_messages(running_state, checkpoint_id, candidate_text)
    return complete_structured("interviewer", messages, InterviewerDecision)
