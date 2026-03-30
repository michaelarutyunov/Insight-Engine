"""Dimensional model for method characterization.

Six ordinal dimensions describe the analytical character of Analysis blocks.
Values are validated against fixed allowed sets -- no free-text, no numbers.
"""

from enum import StrEnum

from pydantic import BaseModel, field_validator


class MethodDimension(StrEnum):
    """Names of the six methodological dimensions."""

    EXPLORATORY_CONFIRMATORY = "exploratory_confirmatory"
    ASSUMPTION_WEIGHT = "assumption_weight"
    OUTPUT_INTERPRETABILITY = "output_interpretability"
    SAMPLE_SENSITIVITY = "sample_sensitivity"
    REPRODUCIBILITY = "reproducibility"
    DATA_STRUCTURE_AFFINITY = "data_structure_affinity"


ALLOWED_VALUES: dict[str, set[str]] = {
    "exploratory_confirmatory": {"exploratory", "mixed", "confirmatory"},
    "assumption_weight": {"low", "medium", "high"},
    "output_interpretability": {"low", "medium", "high"},
    "sample_sensitivity": {"low", "medium", "high"},
    "reproducibility": {"low", "medium", "high"},
    "data_structure_affinity": {
        "unstructured_text",
        "categorical",
        "ordinal",
        "numeric_continuous",
        "mixed",
    },
}


class DimensionalProfile(BaseModel):
    """A set of dimensional values for a method or problem.

    All fields are Optional -- partial profiles are allowed (e.g. a problem
    characterization may only populate 3 of 6 dimensions).
    """

    exploratory_confirmatory: str | None = None
    assumption_weight: str | None = None
    output_interpretability: str | None = None
    sample_sensitivity: str | None = None
    reproducibility: str | None = None
    data_structure_affinity: str | None = None

    @field_validator("exploratory_confirmatory")
    @classmethod
    def _validate_exploratory_confirmatory(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_VALUES["exploratory_confirmatory"]:
            raise ValueError(
                f"Invalid value '{v}' for exploratory_confirmatory. "
                f"Allowed: {sorted(ALLOWED_VALUES['exploratory_confirmatory'])}"
            )
        return v

    @field_validator("assumption_weight")
    @classmethod
    def _validate_assumption_weight(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_VALUES["assumption_weight"]:
            raise ValueError(
                f"Invalid value '{v}' for assumption_weight. "
                f"Allowed: {sorted(ALLOWED_VALUES['assumption_weight'])}"
            )
        return v

    @field_validator("output_interpretability")
    @classmethod
    def _validate_output_interpretability(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_VALUES["output_interpretability"]:
            raise ValueError(
                f"Invalid value '{v}' for output_interpretability. "
                f"Allowed: {sorted(ALLOWED_VALUES['output_interpretability'])}"
            )
        return v

    @field_validator("sample_sensitivity")
    @classmethod
    def _validate_sample_sensitivity(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_VALUES["sample_sensitivity"]:
            raise ValueError(
                f"Invalid value '{v}' for sample_sensitivity. "
                f"Allowed: {sorted(ALLOWED_VALUES['sample_sensitivity'])}"
            )
        return v

    @field_validator("reproducibility")
    @classmethod
    def _validate_reproducibility(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_VALUES["reproducibility"]:
            raise ValueError(
                f"Invalid value '{v}' for reproducibility. "
                f"Allowed: {sorted(ALLOWED_VALUES['reproducibility'])}"
            )
        return v

    @field_validator("data_structure_affinity")
    @classmethod
    def _validate_data_structure_affinity(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_VALUES["data_structure_affinity"]:
            raise ValueError(
                f"Invalid value '{v}' for data_structure_affinity. "
                f"Allowed: {sorted(ALLOWED_VALUES['data_structure_affinity'])}"
            )
        return v


def validate_dimensions(dims: dict) -> bool:
    """Return True if all keys and values are valid dimension entries.

    Unknown keys or values outside the allowed set cause a False return.
    Empty dicts are valid (no dimensions asserted).
    """
    for key, value in dims.items():
        if key not in ALLOWED_VALUES:
            return False
        if value not in ALLOWED_VALUES[key]:
            return False
    return True
