"""Direct invocation of the interviewer agent against a hand-crafted
fixture. Run with:
python -m backend.scripts.dev_interviewer_turn --fixture fixtures/turn_ok.json
"""

import argparse
import json

from backend.agent_schemas import RunningState
from backend.interviewer_agent import decide


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()

    with open(args.fixture) as f:
        fixture = json.load(f)

    running_state = RunningState.model_validate(fixture["running_state"])
    decision = decide(running_state, fixture["checkpoint_id"], fixture["candidate_text"])
    print(json.dumps(decision.model_dump(), indent=2))


if __name__ == "__main__":
    main()
