"""Direct invocation of question sourcing against live SearXNG + OpenRouter.
Run with: python -m backend.scripts.dev_question_sourcing --round hld
"""

import argparse
import json

from backend.question_sourcing import QuestionSourcingError, source_question


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", required=True, choices=["hld", "lld_deepdive"])
    args = parser.parse_args()

    try:
        sourced = source_question(args.round)
    except QuestionSourcingError as e:
        print(f"FAILED: {e}")
        raise SystemExit(1)

    print(json.dumps(sourced.model_dump(), indent=2))


if __name__ == "__main__":
    main()
