from backend.schemas import parse_event
from backend.solver_agent import build_messages


def _event(event_type: str, **fields):
    return parse_event({"event": event_type, "event_id": "e_0001", "timestamp": "t0", **fields})


def test_build_messages_excludes_continue_turns_and_orders_correctly():
    events = [
        _event(
            "session_start",
            session_id="s1",
            round_type="hld",
            question="Design X",
            question_provenance={
                "source_urls": [],
                "discovered_at": "t0",
                "target_level": "SSE",
                "seniority_eval": "ok",
            },
        ),
        _event("candidate_turn", checkpoint_id="cp_1", text="my first answer", input_mode="solver"),
        _event("interviewer_turn", checkpoint_id="cp_1", action="continue", text=""),
        _event("candidate_turn", checkpoint_id="cp_2", text="my second answer", input_mode="solver"),
        _event("interviewer_turn", checkpoint_id="cp_2", action="follow_up", text="go deeper"),
    ]

    messages = build_messages("hld", "Design X", events)

    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "Interview question:\nDesign X"}
    assert messages[2] == {"role": "assistant", "content": "my first answer"}
    assert messages[3] == {"role": "assistant", "content": "my second answer"}
    assert messages[4] == {"role": "user", "content": "go deeper"}
