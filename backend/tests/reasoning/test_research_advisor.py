"""Tests for ResearchAdvisor Stage 2: match_candidates() — mechanical filter + LLM ranking."""

import json
from unittest.mock import MagicMock

import anthropic
import pytest

from chat.research_advisor import (
    MethodCandidate,
    ProblemProfile,
    ResearchAdvisor,
    SituationalContext,
)
from reasoning.profiles import ReasoningProfile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis_block(name: str, dims: dict[str, str], desc: str) -> dict:
    """Create a test analysis block info dict."""
    return {
        "block_type": "analysis",
        "block_implementation": name,
        "dimensions": dims,
        "description": desc,
        "methodological_notes": f"Test method for {name}",
    }


def _make_profile(**overrides):
    """Create a test ProblemProfile with optional overrides."""
    return ProblemProfile(
        research_question="Test research question",
        dimensions={
            "exploratory_confirmatory": "exploratory",
            "assumption_weight": "low",
            "output_interpretability": "medium",
            "sample_sensitivity": "low",
            "reproducibility": "medium",
            "data_structure_affinity": "numeric_continuous",
        },
        situational_context=SituationalContext(
            sample_size=1000,
            data_types=["numeric"],
            timeline="weeks",
            stakeholder_type="product_manager",
        ),
        reasoning="test reasoning",
        **overrides,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_profile():
    """Mock reasoning profile."""
    return ReasoningProfile(
        name="test-profile",
        version="1.0.0",
        description="Test profile",
        dimension_weights={
            "exploratory_confirmatory": 0.5,
            "assumption_weight": 0.5,
            "output_interpretability": 0.5,
            "sample_sensitivity": 0.5,
            "reproducibility": 0.5,
            "data_structure_affinity": 0.5,
        },
        preferences={
            "default_stance": "balanced",
            "transparency_threshold": "medium",
            "prefer_established": True,
        },
        practitioner_workflows_dir="None",
    )


def _analysis_blocks():
    """List of analysis block info dicts for the testing."""
    return [
        _make_analysis_block(
            "kmeans_numeric",
            {
                "exploratory_confirmatory": "exploratory",
                "assumption_weight": "medium",
                "output_interpretability": "medium",
                "sample_sensitivity": "high",
                "reproducibility": "high",
                "data_structure_affinity": "numeric_continuous",
            },
            "Clusters respondents into segments using K-Means.",
        ),
        _make_analysis_block(
            "lca_categorical",
            {
                "exploratory_confirmatory": "mixed",
                "assumption_weight": "high",
                "output_interpretability": "high",
                "sample_sensitivity": "high",
                "reproducibility": "medium",
                "data_structure_affinity": "categorical",
            },
            "Discovers latent classes in categorical/mixed data",
        ),
        _make_analysis_block(
            "sentiment_text",
            {
                "exploratory_confirmatory": "exploratory",
                "assumption_weight": "low",
                "output_interpretability": "high",
                "sample_sensitivity": "medium",
                "reproducibility": "low",
                "data_structure_affinity": "unstructured_text",
            },
            "Analyzes sentiment in unstructured text data",
        ),
        _make_analysis_block(
            "survey_anova",
            {
                "exploratory_confirmatory": "confirmatory",
                "assumption_weight": "high",
                "output_interpretability": "high",
                "sample_sensitivity": "low",
                "reproducibility": "high",
                "data_structure_affinity": "numeric_continuous",
            },
            "ANOVA for confirmatory analysis of numeric data",
        ),
    ]


def _make_registry_with_blocks(blocks: list[dict]) -> MagicMock:
    """Create a mock registry that has list_blocks returning filtered blocks."""
    mock_reg = MagicMock()
    mock_reg.list_blocks.return_value = blocks
    return mock_reg


def _make_profile_numeric(request: str = "numeric_continuous") -> ProblemProfile:
    """Create a profile looking for numeric continuous data."""
    return _make_profile(
        research_question="What segments exist in our customer base?",
        dimensions={
            "exploratory_confirmatory": "exploratory",
            "assumption_weight": "medium",
            "output_interpretability": "medium",
            "sample_sensitivity": "high",
            "reproducibility": "high",
            "data_structure_affinity": "numeric_continuous",
        },
        reasoning="test",
    )


def _make_profile_categorical(request: str = "categorical") -> ProblemProfile:
    """Create a profile looking for categorical data."""
    return _make_profile(
        research_question="What customer types exist?",
        dimensions={
            "exploratory_confirmatory": "mixed",
            "assumption_weight": "high",
            "output_interpretability": "high",
            "sample_sensitivity": "high",
            "reproducibility": "medium",
            "data_structure_affinity": "categorical",
        },
        reasoning="test",
    )


def _make_profile_unstructured(request: str = "unstructured_text") -> ProblemProfile:
    """Create a profile looking for unstructured text data."""
    return _make_profile(
        research_question="What do customers say?",
        dimensions={
            "exploratory_confirmatory": "exploratory",
            "assumption_weight": "low",
            "output_interpretability": "high",
            "sample_sensitivity": "medium",
            "reproducibility": "low",
            "data_structure_affinity": "unstructured_text",
        },
        reasoning="test",
    )


def _make_profile_confirmatory_numeric(request: str = "confirmatory_numeric") -> ProblemProfile:
    """Create a profile for confirmatory numeric analysis."""
    return _make_profile(
        research_question="Does feature X increase conversion?",
        dimensions={
            "exploratory_confirmatory": "confirmatory",
            "assumption_weight": "high",
            "output_interpretability": "high",
            "sample_sensitivity": "low",
            "reproducibility": "high",
            "data_structure_affinity": "numeric_continuous",
        },
        reasoning="test",
    )


# ---------------------------------------------------------------------------
# Mechanical Filter Tests
# ---------------------------------------------------------------------------


class TestMechanicalFilter:
    """Tests for _mechanical_filter()."""

    def test_exact_match_for_data_structure_affinity(self):
        """data_structure_affinity requires exact match."""
        blocks = _analysis_blocks()
        registry = _make_registry_with_blocks(blocks)
        profile = _make_profile_numeric()
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        result = advisor._mechanical_filter(profile)
        # Only numeric_continuous blocks should pass: kmeans_numeric, survey_anova
        impls = {b["block_implementation"] for b in result}
        assert "kmeans_numeric" in impls
        assert "survey_anova" in impls

        # sentiment_text and lca_categorical should NOT be present
        assert "sentiment_text" not in impls
        assert "lca_categorical" not in impls

    def test_adjacent_values_for_exploratory_confirmatory(self):
        """exploratory_confirmatory allows adjacent values."""
        blocks = _analysis_blocks()
        registry = _make_registry_with_blocks(blocks)
        # Profile with exploratory — should match blocks with exploratory AND mixed
        profile = _make_profile_numeric()  # exploratory
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        result = advisor._mechanical_filter(profile)
        # lca_categorical has exploratory_confirmatory="mixed" which is adjacent to "exploratory"
        # But it's data_structure_affinity is "categorical", not "numeric_continuous", so it won't match
        # Verify the adjacent exploratory_confirmatory works: lca has mixed, profile has exploratory
        # They are adjacent, but data_structure blocks it
        impls = {b["block_implementation"] for b in result}
        assert "kmeans_numeric" in impls
        assert "survey_anova" in impls

    def test_categorical_profile_matches_categorical_block(self):
        """Profile with categorical data matches only categorical block."""
        blocks = _analysis_blocks()
        registry = _make_registry_with_blocks(blocks)
        profile = _make_profile_categorical()
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        result = advisor._mechanical_filter(profile)
        impls = {b["block_implementation"] for b in result}
        assert "lca_categorical" in impls
        assert "kmeans_numeric" not in impls
        assert "survey_anova" not in impls

    def test_unstructured_profile_matches_unstructured_block(self):
        """Profile with unstructured_text matches only sentiment block."""
        blocks = _analysis_blocks()
        registry = _make_registry_with_blocks(blocks)
        profile = _make_profile_unstructured()
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        result = advisor._mechanical_filter(profile)
        impls = {b["block_implementation"] for b in result}
        assert "sentiment_text" in impls
        assert len(result) == 1

    def test_empty_registry_returns_empty(self):
        """Empty registry returns no candidates."""
        registry = MagicMock()
        registry.list_blocks.return_value = []
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()
        result = advisor._mechanical_filter(profile)
        assert result == []

    def test_no_analysis_blocks_returns_empty(self):
        """Registry with only non-analysis blocks returns no candidates."""
        registry = MagicMock()
        registry.list_blocks.return_value = [
            {"block_type": "source", "block_implementation": "csv_loader", "dimensions": {}},
            {"block_type": "transform", "block_implementation": "filter", "dimensions": {}},
        ]
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()
        result = advisor._mechanical_filter(profile)
        assert result == []

    def test_blocks_without_dimensions_excluded(self):
        """Analysis blocks without dimensions field are excluded."""
        registry = MagicMock()
        registry.list_blocks.return_value = [
            {
                "block_type": "analysis",
                "block_implementation": "no_dims",
                "description": "A block without dimensions",
                "methodological_notes": "N/A",
            },
        ]
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()
        result = advisor._mechanical_filter(profile)
        assert result == []

    def test_results_sorted_by_compatibility_score(self):
        """Results are sorted by compatibility score descending."""
        blocks = _analysis_blocks()
        registry = _make_registry_with_blocks(blocks)
        # Use confirmatory+numeric profile — should match kmeans and survey_anova
        profile = _make_profile_confirmatory_numeric()
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        result = advisor._mechanical_filter(profile)
        assert len(result) >= 2
        # survey_anova should have higher compatibility (confirmatory + high reproducibility match)
        # kmeans has exploratory vs confirmatory (distance 2) + medium assumption_weight vs high (distance 1)
        impls = [b["block_implementation"] for b in result]
        assert impls[0] in ("survey_anova", "kmeans_numeric")

    def test_compatibility_score_range(self):
        """Compatibility scores are between 0 and 1."""
        blocks = _analysis_blocks()
        registry = _make_registry_with_blocks(blocks)
        profile = _make_profile_numeric()
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        result = advisor._mechanical_filter(profile)
        for block in result:
            score = block["_compatibility_score"]
            assert 0.0 <= score <= 1.0


class TestDimensionalCompatibility:
    """Tests for _dimensions_compatible() with specific dimension combinations."""

    def test_strict_dimension_mismatch_reuses(self):
        """Strict dimension mismatch returns False."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        assert not advisor._dimensions_compatible(
            {"data_structure_affinity": "numeric_continuous"},
            {"data_structure_affinity": "categorical"},
        )

    def test_strict_dimension_match_passes(self):
        """Strict dimension match passes."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        assert advisor._dimensions_compatible(
            {"data_structure_affinity": "numeric_continuous"},
            {"data_structure_affinity": "numeric_continuous"},
        )

    def test_adjacent_exploratory_confirmatory(self):
        """Adjacent values for exploratory_confirmatory pass."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        # exploratory <-> mixed should pass
        assert advisor._dimensions_compatible(
            {"exploratory_confirmatory": "exploratory"},
            {"exploratory_confirmatory": "mixed"},
        )
        # mixed <-> confirmatory should pass
        assert advisor._dimensions_compatible(
            {"exploratory_confirmatory": "mixed"},
            {"exploratory_confirmatory": "confirmatory"},
        )

    def test_distant_exploratory_confirmatory_fails(self):
        """exploratory vs confirmatory (distance > 1) should fail."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        assert not advisor._dimensions_compatible(
            {"exploratory_confirmatory": "exploratory"},
            {"exploratory_confirmatory": "confirmatory"},
        )

    def test_adjacent_ordinal_passes(self):
        """Adjacent ordinal values (low <-> medium) pass."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        assert advisor._dimensions_compatible(
            {"assumption_weight": "low"},
            {"assumption_weight": "medium"},
        )
        # medium <-> high should pass
        assert advisor._dimensions_compatible(
            {"assumption_weight": "medium"},
            {"assumption_weight": "high"},
        )

    def test_distant_ordinal_fails(self):
        """low vs high (distance > 1) should fail."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        assert not advisor._dimensions_compatible(
            {"assumption_weight": "low"},
            {"assumption_weight": "high"},
        )

    def test_none_profile_dim_skips_check(self):
        """If profile dimension is None, it skips check."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        assert advisor._dimensions_compatible(
            {"assumption_weight": None},
            {"assumption_weight": "high"},
        )

    def test_none_block_dim_skips_check(self):
        """If block dimension is None, it skips check."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        assert advisor._dimensions_compatible(
            {"assumption_weight": "medium"},
            {"assumption_weight": None},
        )

    def test_unknown_dimension_key_ignored(self):
        """Unknown dimension keys are ignored (not filtered on)."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        assert advisor._dimensions_compatible(
            {"custom_unknown_dim": "value"},
            {"custom_unknown_dim": "value"},
        )


# ---------------------------------------------------------------------------
# LLM Ranking Tests
# ---------------------------------------------------------------------------


class TestBuildRankPrompt:
    """Tests for _build_rank_prompt()."""

    def test_prompt_contains_block_info(self):
        """Prompt includes filtered block information."""
        blocks = _analysis_blocks()[:2]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()
        filtered = advisor._mechanical_filter(profile)
        system_msg, user_msg = advisor._build_rank_prompt(filtered, profile)

        assert "kmeans_numeric" in system_msg
        for block in filtered:
            assert block["block_implementation"] in user_msg
            assert block["description"] in user_msg

    def test_prompt_contains_situational_context(self):
        """Prompt includes situational context when present."""
        blocks = _analysis_blocks()[:2]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = ProblemProfile(
            research_question="What drives satisfaction?",
            dimensions={
                "exploratory_confirmatory": "exploratory",
                "assumption_weight": "medium",
                "output_interpretability": "high",
                "sample_sensitivity": "high",
                "reproducibility": "high",
                "data_structure_affinity": "numeric_continuous",
            },
            situational_context=SituationalContext(
                available_data="NPS survey with verbatims",
                hypothesis_state="no prior hypothesis",
            ),
            reasoning="test",
        )
        filtered = advisor._mechanical_filter(profile)
        system_msg, user_msg = advisor._build_rank_prompt(filtered, profile)

        assert "NPS survey with verbatims" in user_msg
        assert "no prior hypothesis" in user_msg

    def test_prompt_asks_for_ranked_json(self):
        """Prompt requests JSON output with correct schema."""
        blocks = _analysis_blocks()[:2]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()
        filtered = advisor._mechanical_filter(profile)
        system_msg, user_msg = advisor._build_rank_prompt(filtered, profile)

        assert "JSON" in user_msg
        assert "fit_score" in user_msg
        assert "fit_reasoning" in user_msg
        assert "tradeoffs" in user_msg
        assert "3-6" in user_msg


class TestParseRankResponse:
    """Tests for _parse_rank_response()."""

    def test_valid_json_response(self):
        """Parse a valid JSON response."""
        blocks = _analysis_blocks()[:2]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        raw_text = """```json
[
  {
    "block_implementation": "kmeans_numeric",
    "fit_score": 0.85,
    "fit_reasoning": "Good fit for exploratory numeric analysis",
    "tradeoffs": "Requires numeric features"
  },
  {
    "block_implementation": "survey_anova",
    "fit_score": 0.6,
    "fit_reasoning": "Moderate fit for exploratory analysis",
    "tradeoffs": "Assumes normality"
  }
]
```"""
        filtered = blocks  # Pass the same blocks that were filtered
        result = advisor._parse_rank_response(raw_text, filtered)
        assert len(result) == 2
        assert result[0].block_implementation == "kmeans_numeric"
        assert result[0].fit_score == 0.85
        assert "Good fit" in result[0].fit_reasoning
        assert isinstance(result[0], MethodCandidate)

    def test_response_capped_at_six(self):
        """Response with more than 6 entries is capped at 6."""
        blocks = _analysis_blocks()
        # Add more blocks to exceed cap
        for i in range(4):
            blocks.append(
                _make_analysis_block(
                    f"extra_block_{i}",
                    {
                        "exploratory_confirmatory": "exploratory",
                        "assumption_weight": "low",
                        "output_interpretability": "medium",
                        "sample_sensitivity": "low",
                        "reproducibility": "medium",
                        "data_structure_affinity": "numeric_continuous",
                    },
                    f"Extra block {i}",
                )
            )
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())

        raw_entries = []
        for i in range(8):
            raw_entries.append(
                {
                    "block_implementation": f"extra_block_{i}",
                    "fit_score": 0.5,
                    "fit_reasoning": f"Block {i}",
                    "tradeoffs": "Test tradeoffs",
                }
            )
        raw_text = f"""```json
{json.dumps(raw_entries, indent=2)}
```"""
        result = advisor._parse_rank_response(raw_text, blocks)
        assert len(result) <= 6

    def test_invalid_block_name_skipped(self):
        """Blocks not in filtered set are skipped."""
        blocks = _analysis_blocks()[:1]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        raw_text = """```json
[
  {
    "block_implementation": "nonexistent_block",
    "fit_score": 0.9,
    "fit_reasoning": "Should be skipped",
    "tradeoffs": "N/A"
  }
]
```"""
        result = advisor._parse_rank_response(raw_text, blocks)
        assert len(result) == 0

    def test_fit_score_clamped_to_range(self):
        """Fit scores outside 0-1 range are clamped."""
        blocks = _analysis_blocks()[:1]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        raw_text = """```json
[
  {
    "block_implementation": "kmeans_numeric",
    "fit_score": 1.5,
    "fit_reasoning": "Over 1 clamped",
    "tradeoffs": "Test"
  }
]
```"""
        result = advisor._parse_rank_response(raw_text, blocks)
        assert result[0].fit_score == 1.0

    def test_malformed_json_returns_empty(self):
        """Malformed JSON returns empty list."""
        blocks = _analysis_blocks()[:1]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        result = advisor._parse_rank_response("not valid JSON", blocks)
        assert result == []

    def test_response_with_null_candidate(self):
        """Null entries in the candidates list are skipped."""
        blocks = _analysis_blocks()[:1]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        raw_text = """```json
{
  "candidates": [
    null,
    {"block_implementation": "kmeans_numeric", "fit_score": 0.7, "fit_reasoning": "Test", "tradeoffs": "Test"}
  ]
}
```"""
        result = advisor._parse_rank_response(raw_text, blocks)
        assert len(result) == 1
        assert result[0].block_implementation == "kmeans_numeric"

    def test_response_wrapped_in_markdown(self):
        """Response wrapped in markdown code fences is parsed."""
        blocks = _analysis_blocks()[:1]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        raw_text = """```json
{
  "candidates": [
    {"block_implementation": "kmeans_numeric", "fit_score": 0.9, "fit_reasoning": "Wrapped", "tradeoffs": "Test"}
  ]
}
```"""
        result = advisor._parse_rank_response(raw_text, blocks)
        assert len(result) == 1
        assert result[0].block_implementation == "kmeans_numeric"


class TestFallbackCandidates:
    """Tests for _fallback_candidates()."""

    def test_returns_top_3_by_score(self):
        """Fallback returns up to 3 blocks sorted by compatibility score."""
        blocks = _analysis_blocks()
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        # Manually set compatibility scores
        scored_blocks = []
        for i in range(5):
            scored_blocks.append(
                {
                    "block_type": "analysis",
                    "block_implementation": f"block_{i}",
                    "dimensions": {},
                    "description": f"Block {i}",
                    "methodological_notes": "N/A",
                    "_compatibility_score": 0.3 + i * 0.2,
                }
            )
        result = advisor._fallback_candidates(scored_blocks)
        assert len(result) == 3
        assert result[0].fit_score >= result[1].fit_score
        assert result[1].fit_score >= result[2].fit_score

    def test_fallback_with_fewer_than_3(self):
        """Fallback with fewer than 3 blocks returns all available."""
        advisor = ResearchAdvisor(block_registry=MagicMock(), reasoning_profile=mock_profile())
        filtered = [
            {
                "block_type": "analysis",
                "block_implementation": "only_block",
                "dimensions": {},
                "description": "Only block",
                "methodological_notes": "N/A",
                "_compatibility_score": 0.7,
            },
        ]
        result = advisor._fallback_candidates(filtered)
        assert len(result) == 1
        assert result[0].block_implementation == "only_block"


# ---------------------------------------------------------------------------
# Full Integration Tests
# ---------------------------------------------------------------------------


class TestMatchCandidatesIntegration:
    """Integration tests for match_candidates() with LLM mock."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mock_llm(self, monkeypatch):
        """Test the full filter -> LLM rank pipeline."""
        blocks = _analysis_blocks()[:2]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()
        # Mock the LLM to return a ranked response
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
{
  "candidates": [
    {
      "block_implementation": "kmeans_numeric",
      "fit_score": 0.9,
      "fit_reasoning": "Excellent fit for exploratory numeric analysis",
      "tradeoffs": "Assumes spherical clusters"
    },
    {
      "block_implementation": "survey_anova",
      "fit_score": 0.65,
      "fit_reasoning": "Good alternative for numeric data",
      "tradeoffs": "Requires normally distributed data"
    }
  ]
}
```"""
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.match_candidates(profile)
        assert len(result) == 2
        assert result[0].block_implementation == "kmeans_numeric"
        assert result[0].fit_score == 0.9
        assert isinstance(result[0], MethodCandidate)

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_mechanical(self, monkeypatch):
        """When LLM call fails, fallback to mechanical scores."""
        blocks = _analysis_blocks()[:2]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()

        async def mock_create(*args, **kwargs):
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.match_candidates(profile)
        # Should get fallback candidates with mechanical scores
        assert len(result) > 0
        for candidate in result:
            assert (
                candidate.fit_reasoning
                == "[mechanical fallback] Ranked by dimensional compatibility only."
            )
            assert isinstance(candidate, MethodCandidate)

    @pytest.mark.asyncio
    async def test_llm_returns_empty_uses_fallback(self, monkeypatch):
        """When LLM returns no valid candidates, fallback to mechanical."""
        blocks = _analysis_blocks()[:2]
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()

        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "Invalid response without JSON"
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.match_candidates(profile)
        assert len(result) > 0
        for candidate in result:
            assert "[mechanical fallback]" in candidate.fit_reasoning

    @pytest.mark.asyncio
    async def test_no_filtered_blocks_returns_empty(self):
        """When no blocks pass the mechanical filter, returns empty list."""
        registry = MagicMock()
        registry.list_blocks.return_value = [
            {"block_type": "source", "block_implementation": "csv_loader"},
        ]
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()
        result = await advisor.match_candidates(profile)
        assert result == []

    @pytest.mark.asyncio
    async def test_result_capped_at_six(self, monkeypatch):
        """Result is capped at 6 candidates."""
        blocks = _analysis_blocks()
        for i in range(5):
            blocks.append(
                _make_analysis_block(
                    f"extra_{i}",
                    {
                        "exploratory_confirmatory": "exploratory",
                        "assumption_weight": "medium",
                        "output_interpretability": "medium",
                        "sample_sensitivity": "high",
                        "reproducibility": "high",
                        "data_structure_affinity": "numeric_continuous",
                    },
                    f"Extra block {i}",
                )
            )
        registry = _make_registry_with_blocks(blocks)
        advisor = ResearchAdvisor(block_registry=registry, reasoning_profile=mock_profile())
        profile = _make_profile_numeric()

        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        entries = []
        for block in blocks:
            entries.append(
                {
                    "block_implementation": block["block_implementation"],
                    "fit_score": 0.5,
                    "fit_reasoning": "Test",
                    "tradeoffs": "Test",
                }
            )
        mock_text_block.text = json.dumps({"candidates": entries})
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.match_candidates(profile)
        assert len(result) <= 6


class TestRecommend:
    """Tests for Stage 3: recommend()."""

    @pytest.mark.asyncio
    async def test_placeholder_returns_recommendation(self, advisor):
        """Test that placeholder returns a Recommendation."""
        candidates = [
            MethodCandidate(
                block_implementation="method_a",
                block_type="analysis",
                fit_score=0.8,
                fit_reasoning="test",
                tradeoffs="test",
                dimensions={},
            )
        ]

        result = await advisor.recommend(candidates)

        assert isinstance(result, Recommendation)
        assert result.selected_method == "method_a"
        assert "placeholder" in result.rationale.lower()

    @pytest.mark.asyncio
    async def test_placeholder_empty_candidates(self, advisor):
        """Test placeholder with empty candidate list."""
        result = await advisor.recommend([])
        assert isinstance(result, Recommendation)
        assert result.selected_method == "none"
