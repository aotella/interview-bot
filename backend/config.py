"""Loads env vars and defines the app's reproducibility tuple.

Env vars (paths/secrets, machine-specific) are read once at import time and
fail loudly if missing. Model IDs and prompt/rubric versions are part of the
app's versioned behavior, not per-machine setup, so they're hardcoded here
rather than pulled from the environment.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_REQUIRED_ENV_VARS = (
    "OBSIDIAN_VAULT_PATH",
    "EXCALIDRAW_EXPORT_PATH",
    "OPENROUTER_API_KEY",
)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill in all of: "
            f"{', '.join(_REQUIRED_ENV_VARS)}."
        )
    return value


OBSIDIAN_VAULT_PATH = _require_env("OBSIDIAN_VAULT_PATH")
EXCALIDRAW_EXPORT_PATH = _require_env("EXCALIDRAW_EXPORT_PATH")
OPENROUTER_API_KEY = _require_env("OPENROUTER_API_KEY")

# Base URL of a locally-running SearXNG instance with its JSON API enabled
# (Flagged item 4: resolved as "call SearXNG's own /search?format=json
# directly over HTTP" rather than via a separate MCP server process).
# Optional since it has a sane local default, unlike the three vars above.
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:10999")


@dataclass(frozen=True)
class Models:
    """Model ID is role-specific: the three roles can legitimately run
    different models, so there is no single shared "default model" field."""

    interviewer: str
    grader: str
    question_sourcing: str


@dataclass(frozen=True)
class RubricVersions:
    hld: str
    lld_deepdive: str


models = Models(
    interviewer="anthropic/claude-sonnet-4.6",
    grader="anthropic/claude-sonnet-4.6",
    question_sourcing="anthropic/claude-sonnet-4.6",
)

# Reproducibility tuple: bumped by hand when the corresponding
# prompt/rubric file changes. Kept alongside the model IDs above so a
# session/report can be traced back to exactly what produced it.
rubric_version = RubricVersions(
    hld="hld_v1",
    lld_deepdive="lld_deepdive_v1",
)
interviewer_prompt_version = "v1"
grader_prompt_version = "v1"
question_sourcing_prompt_version = "v1"
