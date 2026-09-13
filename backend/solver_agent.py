"""Offline SDE3/senior-persona candidate agent used for solver-comparison
runs (backend.session_engine.run_solver_comparison). Mirrors
interviewer_agent.py's shape, but builds its chat history directly from
transcript events rather than RunningState: RunningState's CheckpointSummary
only stores the interviewer's past *action*, not the follow-up/interject
*text*, which the solver needs to see in order to respond to it. Never
loads or references the rubric - the rubric must stay hidden from any
candidate-facing persona, the same principle interviewer_agent.py follows.
"""

from pathlib import Path

from backend.agent_schemas import SolverResponse
from backend.schemas import TranscriptEvent
from backend.structured_llm import complete_structured

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_PROMPT_FILES = {
    "hld": "solver_hld_v1.md",
    "lld_deepdive": "solver_lld_deepdive_v1.md",
}


def _load_prompt(round_type: str) -> str:
    return (PROMPTS_DIR / _PROMPT_FILES[round_type]).read_text()


def build_messages(round_type: str, question: str, events: list[TranscriptEvent]) -> list[dict]:
    system_prompt = _load_prompt(round_type)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Interview question:\n{question}"},
    ]
    for e in events:
        if e.event == "candidate_turn":
            messages.append({"role": "assistant", "content": e.text})
        elif e.event == "interviewer_turn" and e.action != "continue":
            messages.append({"role": "user", "content": e.text})
    return messages


def respond(round_type: str, question: str, events: list[TranscriptEvent]) -> SolverResponse:
    messages = build_messages(round_type, question, events)
    return complete_structured("solver", messages, SolverResponse)
