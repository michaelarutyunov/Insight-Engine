"""Reasoning profile loading and management.

Profiles are YAML files stored under ``reasoning_profiles/{name}/profile.yaml``.
Each profile defines dimension weights, methodological preferences, and the
location of practitioner workflow documents.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class ProfilePreferences(BaseModel):
    """Methodological preferences that guide Stage 3 selection."""

    default_stance: str
    transparency_threshold: str
    prefer_established: bool


class ReasoningProfile(BaseModel):
    """A loaded and validated reasoning profile."""

    name: str
    version: str
    description: str
    dimension_weights: dict[str, float]
    preferences: ProfilePreferences
    practitioner_workflows_dir: str

    @field_validator("dimension_weights")
    @classmethod
    def _coerce_weights_to_float(cls, v: dict[str, float]) -> dict[str, float]:
        """YAML parses ``1`` as int; coerce all values to float."""
        coerced: dict[str, float] = {}
        for key, value in v.items():
            coerced[key] = float(value)
        return coerced


def load_profile(path: Path) -> ReasoningProfile:
    """Read a YAML profile file and return a validated ReasoningProfile.

    Raises FileNotFoundError if the file does not exist.
    Raises pydantic.ValidationError if the YAML structure is invalid.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ReasoningProfile.model_validate(raw)


def list_profiles(base_dir: Path) -> list[str]:
    """Return directory names under *base_dir* that contain a profile.yaml.

    Each subdirectory that has a ``profile.yaml`` file is considered a valid
    profile.  Returns an empty list if *base_dir* does not exist.
    """
    if not base_dir.is_dir():
        return []

    profiles: list[str] = []
    for child in sorted(base_dir.iterdir()):
        if child.is_dir() and (child / "profile.yaml").is_file():
            profiles.append(child.name)
    return profiles
