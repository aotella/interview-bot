"""Thin wrapper around the OpenRouter chat-completions API.

Callers never hardcode a model string or API URL - they pass a `role`
(one of the fields on `config.models`) and this module resolves the actual
model ID and does the HTTP call.
"""

from typing import Any

import httpx

from backend import config

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT_SECONDS = 60.0


class OpenRouterError(RuntimeError):
    """Raised for any OpenRouter call failure - auth, rate limit, timeout,
    or a response that doesn't match the expected shape. Callers should
    never see a raw httpx/network traceback."""


def complete(role: str, messages: list[dict[str, Any]], **kwargs: Any) -> str:
    """Send `messages` to the model configured for `role` and return the
    completion text.

    Args:
        role: one of "interviewer", "grader", "question_sourcing" - matches
            a field on `config.models`.
        messages: OpenAI-style chat messages, e.g.
            [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}].
        **kwargs: passed through to the request body (e.g. temperature).
    """
    model = getattr(config.models, role, None)
    if model is None:
        raise OpenRouterError(
            f"Unknown role {role!r}; expected one of "
            f"{[f for f in config.models.__dataclass_fields__]}"
        )

    payload = {"model": model, "messages": messages, **kwargs}
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            _API_URL, json=payload, headers=headers, timeout=_TIMEOUT_SECONDS
        )
    except httpx.TimeoutException as e:
        raise OpenRouterError(f"OpenRouter request timed out after {_TIMEOUT_SECONDS}s") from e
    except httpx.HTTPError as e:
        raise OpenRouterError(f"OpenRouter request failed: {e}") from e

    if response.status_code == 401:
        raise OpenRouterError("OpenRouter auth failed (401) - check OPENROUTER_API_KEY")
    if response.status_code == 429:
        raise OpenRouterError("OpenRouter rate limit hit (429) - retry later")
    if response.status_code >= 400:
        raise OpenRouterError(
            f"OpenRouter request failed with status {response.status_code}: {response.text[:500]}"
        )

    try:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise OpenRouterError(
            f"OpenRouter returned a malformed response: {response.text[:500]}"
        ) from e
