"""Thin wrapper around the OpenRouter chat-completions API.

Callers never hardcode a model string or API URL - they pass a `role`
(one of the fields on `config.models`) and this module resolves the actual
model ID. Real HTTP wiring lands in Phase 3; for now `complete()` raises
NotImplementedError so callers can be written and imported against a stable
interface ahead of time.
"""

from typing import Any


def complete(role: str, messages: list[dict[str, Any]], **kwargs: Any) -> str:
    """Send `messages` to the model configured for `role` and return the
    completion text.

    Args:
        role: one of "interviewer", "grader", "question_sourcing" - matches
            a field on `config.models`.
        messages: OpenAI-style chat messages, e.g.
            [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}].
        **kwargs: passed through to the underlying request (e.g. temperature).
    """
    raise NotImplementedError("OpenRouter HTTP wiring lands in Phase 3")
