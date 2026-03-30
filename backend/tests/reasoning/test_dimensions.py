"""Tests for reasoning/dimensions.py — validate_dimensions, DimensionalProfile."""

import pytest
from pydantic import ValidationError

from reasoning.dimensions import ALLOWED_VALUES, DimensionalProfile, validate_dimensions


class TestValidateDimensions:
    """Tests for the validate_dimensions() free-function validator."""

    def test_valid_dimensions_pass(self):
        """All 6 dimensions with correct values pass validation."""
        dims = {
            "exploratory_confirmatory": "exploratory",
            "assumption_weight": "medium",
            "output_interpretability": "high",
            "sample_sensitivity": "low",
            "reproducibility": "high",
            "data_structure_affinity": "numeric_continuous",
        }
        assert validate_dimensions(dims) is True

    def test_invalid_key_fails(self):
        """Key not in ALLOWED_VALUES causes False return."""
        dims = {"not_a_real_dimension": "exploratory"}
        assert validate_dimensions(dims) is False

    def test_invalid_value_fails(self):
        """Known key but value not in the allowed set causes False return."""
        dims = {"exploratory_confirmatory": "very_exploratory"}
        assert validate_dimensions(dims) is False

    def test_empty_dict_passes(self):
        """Empty dict is valid — no dimensions asserted."""
        assert validate_dimensions({}) is True

    def test_partial_valid_passes(self):
        """Subset of dimensions (e.g. only 2) is still valid."""
        dims = {
            "assumption_weight": "low",
            "reproducibility": "medium",
        }
        assert validate_dimensions(dims) is True


class TestDimensionalProfile:
    """Tests for the DimensionalProfile Pydantic model."""

    def test_dimensional_profile_validates(self):
        """DimensionalProfile accepts all valid values."""
        profile = DimensionalProfile(
            exploratory_confirmatory="confirmatory",
            assumption_weight="high",
            output_interpretability="low",
            sample_sensitivity="medium",
            reproducibility="low",
            data_structure_affinity="categorical",
        )
        assert profile.exploratory_confirmatory == "confirmatory"
        assert profile.data_structure_affinity == "categorical"

    def test_dimensional_profile_rejects_invalid(self):
        """DimensionalProfile raises ValidationError on a bad value."""
        with pytest.raises(ValidationError):
            DimensionalProfile(
                exploratory_confirmatory="not_a_valid_value",
            )

    def test_dimensional_profile_defaults_to_none(self):
        """All fields default to None (partial profiles allowed)."""
        profile = DimensionalProfile()
        assert profile.exploratory_confirmatory is None
        assert profile.assumption_weight is None
        assert profile.output_interpretability is None
        assert profile.sample_sensitivity is None
        assert profile.reproducibility is None
        assert profile.data_structure_affinity is None

    def test_dimensional_profile_allows_partial(self):
        """Only some fields populated, rest None."""
        profile = DimensionalProfile(
            exploratory_confirmatory="mixed",
            sample_sensitivity="high",
        )
        assert profile.exploratory_confirmatory == "mixed"
        assert profile.sample_sensitivity == "high"
        assert profile.assumption_weight is None

    def test_all_allowed_values_pass(self):
        """Every single allowed value for each dimension is accepted."""
        for dim_key, allowed_set in ALLOWED_VALUES.items():
            for value in allowed_set:
                profile = DimensionalProfile(**{dim_key: value})
                assert getattr(profile, dim_key) == value
