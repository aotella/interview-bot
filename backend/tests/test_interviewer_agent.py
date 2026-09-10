from backend.agent_schemas import RunningState
from backend.interviewer_agent import build_messages
from backend.rubric_loader import load_rubric


def test_assembled_messages_never_contain_rubric_dimension_names():
    rubric = load_rubric("hld")
    running_state = RunningState(
        round_type="hld",
        question="Design a rate limiter",
        elapsed_seconds=120,
        checkpoints=[],
        pause_history=[],
        diagrams_attached=[],
    )
    messages = build_messages(running_state, "cp_1", "I'd start with requirements clarification.")
    blob = " ".join(str(m) for m in messages)

    for dim in rubric.dimension_names():
        assert dim not in blob, f"rubric dimension {dim!r} leaked into interviewer messages"
