"""Structured-output enforcement for OpenRouter calls (Flagged item 5,
resolved as parse-and-retry rather than a provider-specific JSON-schema/
tool-calling mode, to keep this provider-agnostic across whatever model
config.models.<role> points at).

The model is instructed to reply with exactly one JSON object. The reply is
parsed and validated against a pydantic schema (plus an optional extra
semantic check, e.g. "every evidence event_id must exist in this
transcript"); on failure, the invalid output and the validation error are
fed back to the model for another attempt, up to `max_attempts` total.
Exhausting attempts raises StructuredOutputError - never a silent fallback
to unstructured text.
"""

import json
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

from backend.openrouter_client import complete

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    """Raised when the model fails to produce valid structured output
    within the retry budget."""


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip()


def complete_structured(
    role: str,
    messages: list[dict[str, Any]],
    schema: type[T],
    extra_validate: Callable[[T], None] | None = None,
    max_attempts: int = 3,
    **kwargs: Any,
) -> T:
    """Call `role`, parsing/validating the reply as `schema`.

    `extra_validate` may raise ValueError to trigger a retry for a
    semantic check the schema alone can't express (e.g. cross-referencing
    the transcript).
    """
    conversation = list(messages)
    last_error: Exception | None = None

    for _ in range(max_attempts):
        raw_text = complete(role, conversation, **kwargs)
        try:
            data = json.loads(_extract_json(raw_text))
            parsed = schema.model_validate(data)
            if extra_validate is not None:
                extra_validate(parsed)
            return parsed
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_error = e
            conversation = messages + [
                {"role": "assistant", "content": raw_text},
                {
                    "role": "user",
                    "content": (
                        f"That response was invalid: {e}. Reply again with ONLY a "
                        "single JSON object matching the required schema - no "
                        "prose, no markdown fences."
                    ),
                },
            ]

    raise StructuredOutputError(
        f"Failed to get valid structured output from role={role!r} after "
        f"{max_attempts} attempts: {last_error}"
    )
