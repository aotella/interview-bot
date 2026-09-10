"""Loads rubric YAML files, reading dimension names from the file rather
than hardcoding HLD/LLD field names anywhere - report generation and
grading both depend on this being the single source of dimension truth."""

from pathlib import Path

import yaml
from pydantic import BaseModel

from backend import config

RUBRICS_DIR = Path(__file__).resolve().parent / "rubrics"

_ROUND_TYPE_TO_RUBRIC_VERSION = {
    "hld": config.rubric_version.hld,
    "lld_deepdive": config.rubric_version.lld_deepdive,
}


class RubricDimension(BaseModel):
    name: str
    description: str
    anchors: dict[int, str]


class Rubric(BaseModel):
    round_type: str
    version: str
    score_range: tuple[int, int]
    dimensions: list[RubricDimension]

    def dimension_names(self) -> list[str]:
        return [d.name for d in self.dimensions]


def load_rubric(round_type: str) -> Rubric:
    if round_type not in _ROUND_TYPE_TO_RUBRIC_VERSION:
        raise ValueError(
            f"Unknown round_type {round_type!r}; expected one of "
            f"{sorted(_ROUND_TYPE_TO_RUBRIC_VERSION)}"
        )
    version = _ROUND_TYPE_TO_RUBRIC_VERSION[round_type]
    path = RUBRICS_DIR / f"{version}.yaml"
    with path.open("r") as f:
        raw = yaml.safe_load(f)
    return Rubric.model_validate(raw)
