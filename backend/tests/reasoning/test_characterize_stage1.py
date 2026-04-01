"""Tests for ResearchAdvisor Stage 1: characterize_problem() LLM implementation.

Uses mocked AsyncAnthropic to verify:
- Prompt construction (system prompt includes dimension definitions)
- Response parsing into ProblemProfile with validated dimensions
- SituationalContext populated from LLM inference
- Graceful error handling for malformed responses
- Model configurability
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.research_advisor import (
    _DEFAULT_MODEL,
    ProblemProfile,
    ResearchAdvisor,
    SituationalContext,
)
from reasoning.dimensions import ALLOWED_VALUES
from reasoning.profiles import ProfilePreferences, ReasoningProfile

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_PROFILE = ReasoningProfile(
    name="Test Profile",
    version="1.0",
    description="Profile for unit tests",
    dimension_weights={
        "exploratory_confirmatory": 1.0,
        "assumption_weight": 0.8,
        "output_interpretability": 1.0,
        "sample_sensitivity": 0.9,
        "reproducibility": 0.7,
        "data_structure_affinity": 1.0,
    },
    preferences=ProfilePreferences(
        default_stance="exploratory",
        transparency_threshold="medium",
        prefer_established=True,
    ),
    practitioner_workflows_dir="practitioner_workflows",
)


def _make_advisor(*, model: str = _DEFAULT_MODEL) -> ResearchAdvisor:
    """Create a ResearchAdvisor with a mock block registry."""
    return ResearchAdvisor(
        block_registry=MagicMock(),
        reasoning_profile=_SAMPLE_PROFILE,
        model=model,
    )


def _valid_llm_json() -> dict:
    """Return a valid LLM response payload matching the expected schema."""
    return {
        "dimensions": {
            "exploratory_confirmatory": "exploratory",
            "assumption_weight": "low",
            "output_interpretability": "medium",
            "sample_sensitivity": "low",
            "reproducibility": "medium",
            "data_structure_affinity": "mixed",
        },
        "situational_context": {
            "available_data": "NPS survey with verbatims",
            "hypothesis_state": "no prior hypothesis",
            "time_constraint": "weeks",
            "epistemic_stance": "suspect unknown unknowns",
            "deliverable_expectation": "exploratory landscape",
        },
        "reasoning": "The question is exploratory in nature, seeking to discover "
        "unknown patterns in survey data.",
    }


def _mock_llm_response(payload: dict) -> MagicMock:
    """Build a mock Anthropic response with the given JSON payload as text."""
    text_block = MagicMock()
    text_block.text = json.dumps(payload)
    text_block.type = "text"

    response = MagicMock()
    response.content = [text_block]
    return response


# ---------------------------------------------------------------------------
# System prompt construction
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    """Tests for _build_characterize_system_prompt()."""

    def test_includes_all_dimension_keys(self) -> None:
        advisor = _make_advisor()
        prompt = advisor._build_characterize_system_prompt()
        for dim_key in ALLOWED_VALUES:
            assert dim_key in prompt, f"Missing dimension: {dim_key}"

    def test_includes_all_allowed_values(self) -> None:
        advisor = _make_advisor()
        prompt = advisor._build_characterize_system_prompt()
        for dim_key, allowed in ALLOWED_VALUES.items():
            for value in allowed:
                assert value in prompt, f"Missing value {value} for {dim_key}"

    def test_includes_situational_context_fields(self) -> None:
        advisor = _make_advisor()
        prompt = advisor._build_characterize_system_prompt()
        assert "available_data" in prompt
        assert "hypothesis_state" in prompt
        assert "time_constraint" in prompt
        assert "epistemic_stance" in prompt
        assert "deliverable_expectation" in prompt

    def test_includes_json_format_instruction(self) -> None:
        advisor = _make_advisor()
        prompt = advisor._build_characterize_system_prompt()
        assert "```json" in prompt
        assert "dimensions" in prompt
        assert "situational_context" in prompt
        assert "reasoning" in prompt


# ---------------------------------------------------------------------------
# User message construction
# ---------------------------------------------------------------------------


class TestBuildUserMessage:
    """Tests for _build_characterize_user_message()."""

    def test_includes_research_question(self) -> None:
        advisor = _make_advisor()
        msg = advisor._build_characterize_user_message("What drives NPS?", None)
        assert "What drives NPS?" in msg

    def test_includes_data_context(self) -> None:
        advisor = _make_advisor()
        msg = advisor._build_characterize_user_message(
            "What drives NPS?",
            {"available_data": "NPS survey with verbatims"},
        )
        assert "Data context:" in msg
        assert "available_data: NPS survey with verbatims" in msg

    def test_omits_data_context_when_none(self) -> None:
        advisor = _make_advisor()
        msg = advisor._build_characterize_user_message("Why do customers leave?", None)
        assert "Data context:" not in msg


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestParseCharacterizeResponse:
    """Tests for _parse_characterize_response()."""

    def test_valid_json_returns_problem_profile(self) -> None:
        advisor = _make_advisor()
        raw = json.dumps(_valid_llm_json())
        result = advisor._parse_characterize_response(raw, "Test question")
        assert isinstance(result, ProblemProfile)
        assert result.research_question == "Test question"

    def test_all_six_dimensions_present(self) -> None:
        advisor = _make_advisor()
        raw = json.dumps(_valid_llm_json())
        result = advisor._parse_characterize_response(raw, "Q")
        assert set(result.dimensions.keys()) == set(ALLOWED_VALUES.keys())

    def test_dimensions_validated_against_allowed_sets(self) -> None:
        advisor = _make_advisor()
        payload = _valid_llm_json()
        payload["dimensions"]["exploratory_confirmatory"] = "invalid_value"
        raw = json.dumps(payload)
        with pytest.raises(ValueError, match="Invalid dimensions"):
            advisor._parse_characterize_response(raw, "Q")

    def test_situational_context_populated(self) -> None:
        advisor = _make_advisor()
        raw = json.dumps(_valid_llm_json())
        result = advisor._parse_characterize_response(raw, "Q")
        assert isinstance(result.situational_context, SituationalContext)
        assert result.situational_context.available_data == "NPS survey with verbatims"
        assert result.situational_context.hypothesis_state == "no prior hypothesis"
        assert result.situational_context.time_constraint == "weeks"
        assert result.situational_context.epistemic_stance == "suspect unknown unknowns"
        assert result.situational_context.deliverable_expectation == "exploratory landscape"

    def test_situational_context_all_null(self) -> None:
        advisor = _make_advisor()
        payload = _valid_llm_json()
        payload["situational_context"] = {
            "available_data": None,
            "hypothesis_state": None,
            "time_constraint": None,
            "epistemic_stance": None,
            "deliverable_expectation": None,
        }
        raw = json.dumps(payload)
        result = advisor._parse_characterize_response(raw, "Q")
        assert result.situational_context.available_data is None
        assert result.situational_context.hypothesis_state is None

    def test_reasoning_extracted(self) -> None:
        advisor = _make_advisor()
        raw = json.dumps(_valid_llm_json())
        result = advisor._parse_characterize_response(raw, "Q")
        assert result.reasoning != ""
        assert "exploratory" in result.reasoning

    def test_missing_dimension_key_raises(self) -> None:
        advisor = _make_advisor()
        payload = _valid_llm_json()
        del payload["dimensions"]["sample_sensitivity"]
        raw = json.dumps(payload)
        with pytest.raises(ValueError, match="Missing dimension keys"):
            advisor._parse_characterize_response(raw, "Q")

    def test_invalid_json_raises(self) -> None:
        advisor = _make_advisor()
        with pytest.raises(ValueError, match="not valid JSON"):
            advisor._parse_characterize_response("not json at all", "Q")

    def test_non_object_json_raises(self) -> None:
        advisor = _make_advisor()
        with pytest.raises(ValueError, match="not a JSON object"):
            advisor._parse_characterize_response("[1, 2, 3]", "Q")

    def test_dimensions_not_dict_raises(self) -> None:
        advisor = _make_advisor()
        payload = _valid_llm_json()
        payload["dimensions"] = "bad"
        raw = json.dumps(payload)
        with pytest.raises(ValueError, match="must be a JSON object"):
            advisor._parse_characterize_response(raw, "Q")

    def test_situational_context_not_dict_raises(self) -> None:
        advisor = _make_advisor()
        payload = _valid_llm_json()
        payload["situational_context"] = "bad"
        raw = json.dumps(payload)
        with pytest.raises(ValueError, match="must be a JSON object"):
            advisor._parse_characterize_response(raw, "Q")

    def test_markdown_fence_stripped(self) -> None:
        advisor = _make_advisor()
        raw_json = json.dumps(_valid_llm_json())
        fenced = f"```json\n{raw_json}\n```"
        result = advisor._parse_characterize_response(fenced, "Q")
        assert isinstance(result, ProblemProfile)

    def test_bare_markdown_fence_stripped(self) -> None:
        advisor = _make_advisor()
        raw_json = json.dumps(_valid_llm_json())
        fenced = f"```\n{raw_json}\n```"
        result = advisor._parse_characterize_response(fenced, "Q")
        assert isinstance(result, ProblemProfile)


# ---------------------------------------------------------------------------
# Full characterize_problem() integration with mocked LLM
# ---------------------------------------------------------------------------


class TestCharacterizeProblem:
    """Integration tests for characterize_problem() with mocked Anthropic client."""

    @pytest.mark.asyncio
    async def test_returns_problem_profile(self) -> None:
        advisor = _make_advisor()
        mock_response = _mock_llm_response(_valid_llm_json())

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await advisor.characterize_problem("What drives NPS?")

        assert isinstance(result, ProblemProfile)
        assert result.research_question == "What drives NPS?"

    @pytest.mark.asyncio
    async def test_passes_system_prompt_with_dimensions(self) -> None:
        advisor = _make_advisor()
        mock_response = _mock_llm_response(_valid_llm_json())

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            await advisor.characterize_problem("Test question")

        call_kwargs = mock_create.call_args
        system_prompt = call_kwargs.kwargs.get("system", "") or call_kwargs[1].get("system", "")
        assert "exploratory_confirmatory" in system_prompt
        assert "data_structure_affinity" in system_prompt

    @pytest.mark.asyncio
    async def test_passes_user_message_with_research_question(self) -> None:
        advisor = _make_advisor()
        mock_response = _mock_llm_response(_valid_llm_json())

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            await advisor.characterize_problem("Why are customers churning?")

        call_kwargs = mock_create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        assert messages[0]["role"] == "user"
        assert "Why are customers churning?" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_passes_data_context_in_user_message(self) -> None:
        advisor = _make_advisor()
        mock_response = _mock_llm_response(_valid_llm_json())

        data_ctx = {"available_data": "NPS survey, 500 responses"}

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            await advisor.characterize_problem("Q", data_context=data_ctx)

        call_kwargs = mock_create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_content = messages[0]["content"]
        assert "NPS survey, 500 responses" in user_content

    @pytest.mark.asyncio
    async def test_uses_configured_model(self) -> None:
        advisor = _make_advisor(model="claude-opus-4-20250514")
        mock_response = _mock_llm_response(_valid_llm_json())

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            await advisor.characterize_problem("Q")

        call_kwargs = mock_create.call_args
        model = call_kwargs.kwargs.get("model") or call_kwargs[1].get("model")
        assert model == "claude-opus-4-20250514"

    @pytest.mark.asyncio
    async def test_default_model_is_sonnet(self) -> None:
        advisor = _make_advisor()
        assert advisor.model == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_all_dimensions_validated(self) -> None:
        """All 6 dimensions present and use valid values from allowed sets."""
        advisor = _make_advisor()
        mock_response = _mock_llm_response(_valid_llm_json())

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await advisor.characterize_problem("Q")

        assert set(result.dimensions.keys()) == set(ALLOWED_VALUES.keys())
        for key, value in result.dimensions.items():
            assert value in ALLOWED_VALUES[key], f"Invalid: {key}={value}"

    @pytest.mark.asyncio
    async def test_malformed_llm_response_raises(self) -> None:
        advisor = _make_advisor()
        text_block = MagicMock()
        text_block.text = "I cannot answer that."
        text_block.type = "text"
        mock_response = MagicMock()
        mock_response.content = [text_block]

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            with pytest.raises(ValueError, match="not valid JSON"):
                await advisor.characterize_problem("Q")

    @pytest.mark.asyncio
    async def test_invalid_dimension_value_raises(self) -> None:
        advisor = _make_advisor()
        payload = _valid_llm_json()
        payload["dimensions"]["assumption_weight"] = "very_high"
        mock_response = _mock_llm_response(payload)

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            with pytest.raises(ValueError, match="Invalid dimensions"):
                await advisor.characterize_problem("Q")

    @pytest.mark.asyncio
    async def test_situational_context_populated_from_llm(self) -> None:
        advisor = _make_advisor()
        mock_response = _mock_llm_response(_valid_llm_json())

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await advisor.characterize_problem("What drives NPS?")

        sc = result.situational_context
        assert sc.available_data == "NPS survey with verbatims"
        assert sc.hypothesis_state == "no prior hypothesis"
        assert sc.time_constraint == "weeks"
        assert sc.epistemic_stance == "suspect unknown unknowns"
        assert sc.deliverable_expectation == "exploratory landscape"

    @pytest.mark.asyncio
    async def test_multiple_text_blocks_concatenated(self) -> None:
        """LLM may return multiple text blocks; ensure they are concatenated."""
        advisor = _make_advisor()
        payload = _valid_llm_json()
        full_text = json.dumps(payload)

        # Split JSON in half across two text blocks.
        mid = len(full_text) // 2
        block1 = MagicMock()
        block1.text = full_text[:mid]
        block1.type = "text"
        block2 = MagicMock()
        block2.text = full_text[mid:]
        block2.type = "text"

        mock_response = MagicMock()
        mock_response.content = [block1, block2]

        with patch.object(
            advisor._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await advisor.characterize_problem("Q")

        assert isinstance(result, ProblemProfile)
