"""Tests for ResearchAdvisor — research question to method recommendation."""

from unittest.mock import MagicMock

import anthropic
import pytest

from chat.research_advisor import (
    MethodCandidate,
    ProblemProfile,
    Recommendation,
    ResearchAdvisor,
    SituationalContext,
)
from reasoning.dimensions import ALLOWED_VALUES
from reasoning.profiles import ReasoningProfile


@pytest.fixture
def mock_registry():
    """Mock block registry."""
    return {"blocks": []}


@pytest.fixture
def mock_profile():
    """Mock reasoning profile."""
    return ReasoningProfile(
        name="default",
        version="1.0.0",
        description="Default profile",
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
        practitioner_workflows_dir="reasoning_profiles/default/practitioner_workflows",
    )


@pytest.fixture
def advisor(mock_registry, mock_profile):
    """Create a ResearchAdvisor instance."""
    return ResearchAdvisor(
        block_registry=mock_registry,
        reasoning_profile=mock_profile,
        model="claude-sonnet-4-6",
    )


class TestCharacterizeProblem:
    """Tests for Stage 1: characterize_problem()."""

    @pytest.mark.asyncio
    async def test_full_valid_response(self, advisor, monkeypatch):
        """Test parsing a complete valid LLM response."""
        # Mock the LLM response
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
{
  "dimensions": {
    "exploratory_confirmatory": "exploratory",
    "assumption_weight": "medium",
    "output_interpretability": "high",
    "sample_sensitivity": "low",
    "reproducibility": "medium",
    "data_structure_affinity": "mixed"
  },
  "situational_context": {
    "available_data": "NPS survey with verbatims",
    "hypothesis_state": "no prior hypothesis",
    "time_constraint": "weeks",
    "epistemic_stance": "suspect unknown unknowns",
    "deliverable_expectation": "exploratory landscape"
  },
  "reasoning": "The research question is exploratory in nature, seeking to discover patterns rather than test hypotheses."
}
```"""
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.characterize_problem(
            research_question="What drives customer satisfaction?",
            data_context={"source": "NPS survey", "rows": 1000},
        )

        assert isinstance(result, ProblemProfile)
        assert result.research_question == "What drives customer satisfaction?"
        assert result.dimensions["exploratory_confirmatory"] == "exploratory"
        assert result.dimensions["assumption_weight"] == "medium"
        assert result.dimensions["output_interpretability"] == "high"
        assert result.dimensions["sample_sensitivity"] == "low"
        assert result.dimensions["reproducibility"] == "medium"
        assert result.dimensions["data_structure_affinity"] == "mixed"
        assert result.situational_context.available_data == "NPS survey with verbatims"
        assert result.situational_context.hypothesis_state == "no prior hypothesis"
        assert result.situational_context.time_constraint == "weeks"
        assert "exploratory" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_partial_response_with_nulls(self, advisor, monkeypatch):
        """Test parsing a response with some null situational fields."""
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
{
  "dimensions": {
    "exploratory_confirmatory": "confirmatory",
    "assumption_weight": "high",
    "output_interpretability": "low",
    "sample_sensitivity": "high",
    "reproducibility": "high",
    "data_structure_affinity": "numeric_continuous"
  },
  "situational_context": {
    "available_data": "experimental A/B test results",
    "hypothesis_state": null,
    "time_constraint": null,
    "epistemic_stance": null,
    "deliverable_expectation": "board-ready quantified answer"
  },
  "reasoning": "Confirmatory hypothesis testing requires high reproducibility."
}
```"""
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.characterize_problem(
            research_question="Does feature X increase conversion?",
        )

        assert result.dimensions["exploratory_confirmatory"] == "confirmatory"
        assert result.situational_context.available_data == "experimental A/B test results"
        assert result.situational_context.hypothesis_state is None
        assert result.situational_context.time_constraint is None
        assert result.situational_context.epistemic_stance is None

    @pytest.mark.asyncio
    async def test_invalid_dimension_value_raises_error(self, advisor, monkeypatch):
        """Test that invalid dimension values raise ValueError."""
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
{
  "dimensions": {
    "exploratory_confirmatory": "invalid_value",
    "assumption_weight": "medium",
    "output_interpretability": "high",
    "sample_sensitivity": "low",
    "reproducibility": "medium",
    "data_structure_affinity": "mixed"
  },
  "situational_context": {},
  "reasoning": "test"
}
```"""
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        with pytest.raises(ValueError, match="Invalid dimensions"):
            await advisor.characterize_problem(
                research_question="Test question?",
            )

    @pytest.mark.asyncio
    async def test_missing_dimension_key_raises_error(self, advisor, monkeypatch):
        """Test that missing dimension keys raise ValueError."""
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
{
  "dimensions": {
    "exploratory_confirmatory": "exploratory",
    "assumption_weight": "medium",
    "output_interpretability": "high",
    "sample_sensitivity": "low"
  },
  "situational_context": {},
  "reasoning": "test"
}
```"""
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        with pytest.raises(ValueError, match="Missing dimension keys"):
            await advisor.characterize_problem(
                research_question="Test question?",
            )

    @pytest.mark.asyncio
    async def test_malformed_json_raises_error(self, advisor, monkeypatch):
        """Test that malformed JSON raises ValueError."""
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "This is not valid JSON at all."

        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        with pytest.raises(ValueError, match="not valid JSON"):
            await advisor.characterize_problem(
                research_question="Test question?",
            )

    def test_build_characterize_system_prompt(self, advisor):
        """Test that system prompt includes all required sections."""
        prompt = advisor._build_characterize_system_prompt()

        # Check dimension definitions are present
        for dim_key in ALLOWED_VALUES:
            assert dim_key in prompt
            for value in ALLOWED_VALUES[dim_key]:
                assert value in prompt

        # Check situational context fields
        assert "available_data" in prompt
        assert "hypothesis_state" in prompt
        assert "time_constraint" in prompt
        assert "epistemic_stance" in prompt
        assert "deliverable_expectation" in prompt

        # Check output format
        assert "dimensions" in prompt
        assert "situational_context" in prompt
        assert "reasoning" in prompt

    def test_build_characterize_user_message(self, advisor):
        """Test user message construction."""
        msg = advisor._build_characterize_user_message(
            research_question="What drives satisfaction?",
            data_context={"source": "survey", "rows": 1000},
        )

        assert "What drives satisfaction?" in msg
        assert "source: survey" in msg
        assert "rows: 1000" in msg

    def test_build_characterize_user_message_no_context(self, advisor):
        """Test user message without data context."""
        msg = advisor._build_characterize_user_message(
            research_question="What drives satisfaction?",
            data_context=None,
        )

        assert "What drives satisfaction?" in msg
        assert "Data context:" not in msg


class TestMatchCandidates:
    """Tests for Stage 2: match_candidates()."""

    @pytest.mark.asyncio
    async def test_mechanical_filter_empty_registry(self, advisor):
        """Test that empty registry returns empty candidate list."""
        # Advisor with empty list registry
        advisor.registry = []

        profile = ProblemProfile(
            research_question="Test?",
            dimensions={k: "medium" for k in ALLOWED_VALUES},
            situational_context=SituationalContext(),
            reasoning="test",
        )

        result = await advisor.match_candidates(profile)

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_mechanical_filter_with_mock_blocks(self, advisor, monkeypatch):
        """Test mechanical filter with mock Analysis blocks and LLM ranking."""
        # Mock registry with sample Analysis blocks
        mock_blocks = [
            {
                "block_type": "analysis",
                "block_implementation": "SegmentationKMeans",
                "dimensions": {
                    "exploratory_confirmatory": "exploratory",
                    "assumption_weight": "medium",
                    "output_interpretability": "medium",
                    "sample_sensitivity": "medium",
                    "reproducibility": "high",
                    "data_structure_affinity": "numeric_continuous",
                },
                "description": "K-means clustering for segmentation",
                "methodological_notes": "Use for discovering segments",
            },
            {
                "block_type": "transform",  # Not analysis - should be filtered out
                "block_implementation": "SomeTransform",
                "dimensions": {},
            },
        ]
        advisor.registry = mock_blocks

        profile = ProblemProfile(
            research_question="Test?",
            dimensions={
                "exploratory_confirmatory": "exploratory",
                "assumption_weight": "medium",
                "output_interpretability": "medium",
                "sample_sensitivity": "medium",
                "reproducibility": "medium",  # Adjacent to "high"
                "data_structure_affinity": "numeric_continuous",
            },
            situational_context=SituationalContext(),
            reasoning="test",
        )

        # Mock the LLM response
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
[
  {
    "block_implementation": "SegmentationKMeans",
    "fit_score": 0.85,
    "fit_reasoning": "Good dimensional match for exploratory analysis",
    "tradeoffs": "Requires numeric data and may need preprocessing"
  }
]
```"""
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.match_candidates(profile)

        assert len(result) == 1
        assert result[0].block_implementation == "SegmentationKMeans"
        assert result[0].fit_score == 0.85
        assert "dimensional match" in result[0].fit_reasoning.lower()


class TestRecommend:
    """Tests for Stage 3: recommend()."""

    @pytest.mark.asyncio
    async def test_llm_selects_from_candidates(self, advisor, monkeypatch):
        """Test that LLM selects a method and returns Recommendation."""
        candidates = [
            MethodCandidate(
                block_implementation="segmentation_kmeans",
                block_type="analysis",
                fit_score=0.85,
                fit_reasoning="Good dimensional match",
                tradeoffs="Requires numeric data",
                dimensions={
                    "exploratory_confirmatory": "exploratory",
                    "data_structure_affinity": "numeric_continuous",
                },
            ),
            MethodCandidate(
                block_implementation="segmentation_lca",
                block_type="analysis",
                fit_score=0.75,
                fit_reasoning="Moderate fit",
                tradeoffs="Requires larger sample",
                dimensions={
                    "exploratory_confirmatory": "exploratory",
                    "data_structure_affinity": "categorical",
                },
            ),
        ]

        # Mock the LLM response
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
{
  "selected_method": "segmentation_kmeans",
  "rationale": "K-means is the best fit given the high dimensional compatibility (0.85) and the numeric data structure. It aligns with the exploratory stance and provides interpretable output suitable for the stakeholder's needs.",
  "pipeline_sketch": {
    "nodes": [
      {"type": "source", "implementation": "db_source", "purpose": "Load survey data"},
      {"type": "transform", "implementation": "data_cleaning", "purpose": "Clean and prepare numeric features"},
      {"type": "analysis", "implementation": "segmentation_kmeans", "purpose": "Discover customer segments"},
      {"type": "sink", "implementation": "local_export", "purpose": "Save segment assignments"}
    ],
    "connections": [
      {"from": 0, "to": 1, "data_type": "respondent_collection"},
      {"from": 1, "to": 2, "data_type": "respondent_collection"},
      {"from": 2, "to": 3, "data_type": "segment_profile_set"}
    ]
  }
}
```"""
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.recommend(candidates)

        assert isinstance(result, Recommendation)
        assert result.selected_method == "segmentation_kmeans"
        assert "dimensional compatibility" in result.rationale.lower()
        assert result.pipeline_sketch is not None
        assert "nodes" in result.pipeline_sketch
        assert "connections" in result.pipeline_sketch
        # practitioner_workflow is derived from first part before underscore: "segmentation_kmeans" -> "segmentation"
        assert result.practitioner_workflow == "segmentation.md"

    @pytest.mark.asyncio
    async def test_recommend_with_constraints(self, advisor, monkeypatch):
        """Test that constraints are included in context."""
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

        # Mock the LLM response
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
{
  "selected_method": "method_a",
  "rationale": "Selected given the tight timeline constraint.",
  "pipeline_sketch": {
    "nodes": [{"type": "source", "implementation": "db_source", "purpose": "Load data"}],
    "connections": []
  }
}
```"""
        mock_response.content = [mock_text_block]

        # Track calls with MagicMock
        mock_create = MagicMock(wraps=lambda *args, **kwargs: mock_response)
        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.recommend(
            candidates,
            constraints={"timeline": "1 week", "budget": "limited"},
        )

        assert result.selected_method == "method_a"
        # Verify constraints were included in the call
        assert mock_create.called
        call_kwargs = mock_create.call_args[1]
        user_message = call_kwargs["messages"][0]["content"]
        assert "timeline" in user_message
        assert "1 week" in user_message
        assert "budget" in user_message

    @pytest.mark.asyncio
    async def test_recommend_empty_candidates(self, advisor):
        """Test with empty candidate list."""
        result = await advisor.recommend([])

        assert isinstance(result, Recommendation)
        assert result.selected_method == "none"
        assert "no candidates" in result.rationale.lower()

    @pytest.mark.asyncio
    async def test_recommend_llm_failure_fallback(self, advisor, monkeypatch):
        """Test fallback to top candidate when LLM fails."""
        candidates = [
            MethodCandidate(
                block_implementation="top_choice",
                block_type="analysis",
                fit_score=0.9,
                fit_reasoning="Best match",
                tradeoffs="None",
                dimensions={},
            ),
            MethodCandidate(
                block_implementation="second_choice",
                block_type="analysis",
                fit_score=0.7,
                fit_reasoning="Ok match",
                tradeoffs="Some",
                dimensions={},
            ),
        ]

        # Mock LLM failure
        async def mock_create(*args, **kwargs):
            raise Exception("LLM API error")

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.recommend(candidates)

        assert result.selected_method == "top_choice"
        assert "fallback" in result.rationale.lower()
        assert "0.90" in result.rationale
        # practitioner_workflow is derived from first part before underscore: "top_choice" -> "top"
        assert result.practitioner_workflow == "top.md"

    @pytest.mark.asyncio
    async def test_recommend_invalid_json_fallback(self, advisor, monkeypatch):
        """Test fallback when LLM returns invalid JSON."""
        candidates = [
            MethodCandidate(
                block_implementation="fallback_method",
                block_type="analysis",
                fit_score=0.8,
                fit_reasoning="test",
                tradeoffs="test",
                dimensions={},
            )
        ]

        # Mock invalid JSON response
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "This is not valid JSON at all."
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.recommend(candidates)

        assert result.selected_method == "fallback_method"
        assert "parse error" in result.rationale.lower()

    @pytest.mark.asyncio
    async def test_recommend_invalid_selection_fallback(self, advisor, monkeypatch):
        """Test fallback when LLM selects a method not in candidates."""
        candidates = [
            MethodCandidate(
                block_implementation="valid_method",
                block_type="analysis",
                fit_score=0.8,
                fit_reasoning="test",
                tradeoffs="test",
                dimensions={},
            )
        ]

        # Mock response with invalid selection
        mock_response = MagicMock()
        mock_text_block = MagicMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = """```json
{
  "selected_method": "ghost_method_not_in_list",
  "rationale": "Invalid selection",
  "pipeline_sketch": null
}
```"""
        mock_response.content = [mock_text_block]

        async def mock_create(*args, **kwargs):
            return mock_response

        monkeypatch.setattr(advisor._client.messages, "create", mock_create)

        result = await advisor.recommend(candidates)

        # Should fall back to top valid candidate
        assert result.selected_method == "valid_method"

    def test_build_recommend_system_prompt(self, advisor):
        """Test that system prompt includes required sections."""
        prompt = advisor._build_recommend_system_prompt()

        assert "Selection Criteria" in prompt
        assert "reasoning profile" in prompt
        assert "practitioner workflow" in prompt
        assert "constraints" in prompt
        assert "pipeline_sketch" in prompt
        assert "nodes" in prompt
        assert "connections" in prompt

    def test_build_recommend_user_message(self, advisor):
        """Test user message construction."""
        candidates = [
            MethodCandidate(
                block_implementation="test_method",
                block_type="analysis",
                fit_score=0.8,
                fit_reasoning="Good fit",
                tradeoffs="Some tradeoffs",
                dimensions={"exploratory_confirmatory": "exploratory"},
            )
        ]

        msg = advisor._build_recommend_user_message(candidates, None)

        assert "Select the best method" in msg
        assert "test_method" in msg
        assert "Good fit" in msg
        assert "Reasoning Profile" in msg

    def test_parse_recommend_response_full(self, advisor):
        """Test parsing a complete valid LLM response."""
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

        raw = """```json
{
  "selected_method": "method_a",
  "rationale": "Best choice for this analysis",
  "pipeline_sketch": {
    "nodes": [{"type": "source", "implementation": "db_source", "purpose": "Load"}],
    "connections": []
  }
}
```"""

        result = advisor._parse_recommend_response(raw, candidates)

        assert result.selected_method == "method_a"
        assert "Best choice" in result.rationale
        assert result.pipeline_sketch is not None
        # practitioner_workflow is derived from first part before underscore: "method_a" -> "method"
        assert result.practitioner_workflow == "method.md"

    def test_build_recommend_user_message_includes_workflow(self, advisor, monkeypatch):
        """Test that build_advisor_context is called to include practitioner workflow."""
        candidates = [
            MethodCandidate(
                block_implementation="segmentation_kmeans",
                block_type="analysis",
                fit_score=0.8,
                fit_reasoning="Good fit",
                tradeoffs="Some tradeoffs",
                dimensions={"exploratory_confirmatory": "exploratory"},
            )
        ]

        # Mock build_advisor_context to verify it's called
        # The import is: from chat.context_builder import build_advisor_context

        def mock_build(profile, candidates_dict, base_dir=None):
            # Verify it's called with the right parameters
            assert profile == advisor.profile
            assert len(candidates_dict) == 1
            assert candidates_dict[0]["block_implementation"] == "segmentation_kmeans"
            # Return a simplified response that includes workflow section
            return "# Reasoning Profile\n\n# Method Candidates\n\n# Practitioner Workflow (top candidate)\n\nWorkflow content here"

        # Monkeypatch needs to replace the imported function in the research_advisor module
        import chat.research_advisor

        monkeypatch.setattr(chat.research_advisor, "build_advisor_context", mock_build)

        msg = advisor._build_recommend_user_message(candidates, None)

        # Verify the context is included in the message
        assert "Reasoning Profile" in msg
        assert "Method Candidates" in msg
        assert "Practitioner Workflow" in msg
