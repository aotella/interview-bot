"""Client for a locally-running SearXNG instance's JSON search API.

Flagged item 4 resolved this as a direct HTTP call to SearXNG's own
`/search?format=json` endpoint rather than a separate MCP server process -
simplest path for a single-backend tool with no other MCP consumers.
"""

from typing import Any, TypedDict

import httpx

from backend import config

_TIMEOUT_SECONDS = 20.0


class SearchResult(TypedDict):
    title: str
    url: str
    snippet: str


class SearXNGError(RuntimeError):
    """Raised for any SearXNG call failure - connection, timeout, or a
    response that doesn't match the expected shape."""


def search(query: str, num_results: int = 5) -> list[SearchResult]:
    try:
        response = httpx.get(
            f"{config.SEARXNG_URL}/search",
            params={"q": query, "format": "json"},
            timeout=_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as e:
        raise SearXNGError(f"SearXNG request timed out after {_TIMEOUT_SECONDS}s") from e
    except httpx.HTTPError as e:
        raise SearXNGError(
            f"SearXNG request failed (is it running at {config.SEARXNG_URL}?): {e}"
        ) from e

    if response.status_code >= 400:
        raise SearXNGError(
            f"SearXNG request failed with status {response.status_code}: {response.text[:500]}"
        )

    try:
        data: dict[str, Any] = response.json()
        raw_results = data["results"]
    except (ValueError, KeyError, TypeError) as e:
        raise SearXNGError(
            f"SearXNG returned a malformed response: {response.text[:500]}"
        ) from e

    results: list[SearchResult] = []
    for item in raw_results[:num_results]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
            )
        )
    return results
