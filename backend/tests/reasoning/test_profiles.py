"""Tests for reasoning/profiles.py — load_profile, list_profiles, ReasoningProfile."""

from pathlib import Path

import pytest

from reasoning.profiles import ReasoningProfile, list_profiles, load_profile

REASONING_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "reasoning_profiles"
DEFAULT_PROFILE_PATH = REASONING_PROFILES_DIR / "default" / "profile.yaml"


class TestLoadProfile:
    """Tests for load_profile()."""

    def test_default_profile_loads(self):
        """The default profile YAML loads and validates successfully."""
        profile = load_profile(DEFAULT_PROFILE_PATH)
        assert isinstance(profile, ReasoningProfile)
        assert profile.name == "Default Research Methodology"

    def test_default_profile_has_float_weights(self):
        """All dimension_weights values are float type (YAML int coercion)."""
        profile = load_profile(DEFAULT_PROFILE_PATH)
        for key, value in profile.dimension_weights.items():
            assert isinstance(value, float), f"{key} is {type(value).__name__}, expected float"

    def test_default_profile_has_preferences(self):
        """Preferences sub-object is loaded correctly."""
        profile = load_profile(DEFAULT_PROFILE_PATH)
        assert profile.preferences.default_stance == "exploratory"
        assert profile.preferences.transparency_threshold == "medium"
        assert profile.preferences.prefer_established is True

    def test_default_profile_has_workflows_dir(self):
        """practitioner_workflows_dir is set."""
        profile = load_profile(DEFAULT_PROFILE_PATH)
        assert profile.practitioner_workflows_dir == "practitioner_workflows"

    def test_invalid_profile_raises(self):
        """load_profile on a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_profile(Path("/nonexistent/path/profile.yaml"))


class TestListProfiles:
    """Tests for list_profiles()."""

    def test_list_profiles_returns_default(self):
        """list_profiles finds the default profile."""
        profiles = list_profiles(REASONING_PROFILES_DIR)
        assert "default" in profiles

    def test_list_profiles_nonexistent_dir(self):
        """list_profiles returns empty list for a non-existent directory."""
        profiles = list_profiles(Path("/nonexistent/dir"))
        assert profiles == []

    def test_list_profiles_returns_sorted(self):
        """Results are sorted alphabetically."""
        profiles = list_profiles(REASONING_PROFILES_DIR)
        assert profiles == sorted(profiles)
