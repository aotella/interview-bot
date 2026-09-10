"""Calls OpenRouter for all three model roles with a trivial prompt and
prints each response. Run with: python -m backend.scripts.smoke_openrouter
"""

from backend import config
from backend.openrouter_client import OpenRouterError, complete

PROMPT = "Reply with exactly the word: pong"


def main() -> None:
    for role in ("interviewer", "grader", "question_sourcing"):
        model = getattr(config.models, role)
        print(f"--- role={role} model={model} ---")
        try:
            reply = complete(role, [{"role": "user", "content": PROMPT}])
            print(reply)
        except OpenRouterError as e:
            print(f"FAILED: {e}")


if __name__ == "__main__":
    main()
