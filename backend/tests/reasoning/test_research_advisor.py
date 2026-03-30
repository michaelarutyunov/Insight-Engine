"""Tests for chat/research_advisor.py — ResearchAdvisor, models, SituationalContext."""

from pathlib import Path

import pytest

from chat.research_advisor import (
    ProblemProfile,
    Recommendation,
    ResearchAdvisor,
    SituationalContext,
)
from reasoning.profiles import load_profile

REASONING_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "reasoning_profiles"
DEFAULT_PROFILE_PATH = REASONING_PROFILES_DIR / "default" / "profile.yaml"


class TestSituationalContext:
    """Tests for the SituationalContext model."""

    def test_situational_context_defaults(self):
        """All fields default to None."""
        ctx = SituationalContext()
        assert ctx.available_data is None
        assert ctx.hypothesis_state is None
        assert ctx.time_constraint is None
        assert ctx.epistemic_stance is None
        assert ctx.deliverable_expectation is None

    def test_situational_context_accepts_values(self):
        """All fields accept string values."""
        ctx = SituationalContext(
            available_data="NPS survey with verbatims",
            hypothesis_state="no prior hypothesis",
            time_constraint="weeks",
            epistemic_stance="suspect unknown unknowns",
            deliverable_expectation="board-ready quantified answer",
        )
        assert ctx.available_data == "NPS survey with verbatims"
        assert ctx.hypothesis_state == "no prior hypothesis"
        assert ctx.time_constraint == "weeks"
        assert ctx.epistemic_stance == "suspect unknown unknowns"
        assert ctx.deliverable_expectation == "board-ready quantified answer"


class TestResearchAdvisor:
    """Tests for the ResearchAdvisor class."""

    @pytest.fixture()
    def advisor(self):
        profile = load_profile(DEFAULT_PROFILE_PATH)
        # Use a simple mock registry (empty list of blocks)
        return ResearchAdvisor(block_registry=[], reasoning_profile=profile)

    def test_advisor_instantiation(self, advisor):
        """ResearchAdvisor(registry, profile) works."""
        assert advisor is not None
        assert advisor.profile.name == "Default Research Methodology"

    @pytest.mark.asyncio
    async def test_characterize_returns_problem_profile(self, advisor):
        """characterize_problem returns ProblemProfile with dimensions AND situational_context."""
        result = await advisor.characterize_problem(
            "What drives customer satisfaction?",
            data_context={"available_data": "NPS survey with verbatims"},
        )
        assert isinstance(result, ProblemProfile)
        assert result.research_question == "What drives customer satisfaction?"
        # Both fields must exist as separate fields (not merged)
        assert isinstance(result.dimensions, dict)
        assert len(result.dimensions) > 0
        assert isinstance(result.situational_context, SituationalContext)
        # Situational context should have the available_data from data_context
        assert result.situational_context.available_data == "NPS survey with verbatims"

    @pytest.mark.asyncio
    async def test_characterize_dimensions_are_valid(self, advisor):
        """Dimensions returned by characterize_problem use valid keys and values."""
        from reasoning.dimensions import validate_dimensions

        result = await advisor.characterize_problem("Test question")
        assert validate_dimensions(result.dimensions) is True

    @pytest.mark.asyncio
    async def test_match_returns_list(self, advisor):
        """match_candidates returns a list."""
        profile = await advisor.characterize_problem("Test question")
        result = await advisor.match_candidates(profile)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_recommend_returns_recommendation(self, advisor):
        """recommend returns a Recommendation with selected_method, rationale, etc."""
        profile = await advisor.characterize_problem("Test question")
        candidates = await advisor.match_candidates(profile)
        result = await advisor.recommend(candidates)
        assert isinstance(result, Recommendation)
        assert isinstance(result.selected_method, str)
        assert isinstance(result.rationale, str)

    @pytest.mark.asyncio
    async def test_characterize_no_data_context(self, advisor):
        """characterize_problem works without data_context (defaults to None)."""
        result = await advisor.characterize_problem("What drives loyalty?")
        assert isinstance(result, ProblemProfile)
        assert result.situational_context.available_data is None

    @pytest.mark.asyncio
    async def test_recommend_with_empty_candidates(self, advisor):
        """recommend handles empty candidate list gracefully."""
        result = await advisor.recommend([])
        assert result.selected_method == "none"
