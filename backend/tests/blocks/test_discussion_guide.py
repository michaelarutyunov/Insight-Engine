"""Tests for DiscussionGuide block."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks.generation.discussion_guide import DiscussionGuide


def _run(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class TestDiscussionGuide:
    """Test suite for DiscussionGuide block."""

    def test_block_type(self) -> None:
        block = DiscussionGuide()
        assert block.block_type == "generation"

    def test_input_schemas(self) -> None:
        block = DiscussionGuide()
        assert block.input_schemas == ["respondent_collection"]

    def test_output_schemas(self) -> None:
        block = DiscussionGuide()
        assert block.output_schemas == ["text_corpus"]

    def test_config_schema(self) -> None:
        block = DiscussionGuide()
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "research_objectives" in schema["properties"]
        assert "interview_type" in schema["properties"]
        assert "duration_minutes" in schema["properties"]
        assert "model" in schema["properties"]
        assert "temperature" in schema["properties"]
        assert "seed" in schema["properties"]
        assert schema["required"] == ["research_objectives"]

    def test_description(self) -> None:
        block = DiscussionGuide()
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_methodological_notes(self) -> None:
        block = DiscussionGuide()
        assert isinstance(block.methodological_notes, str)
        assert len(block.methodological_notes) > 0

    def test_tags(self) -> None:
        block = DiscussionGuide()
        tags = block.tags
        assert isinstance(tags, list)
        assert "llm" in tags
        assert "generation" in tags
        assert "qualitative" in tags

    def test_validate_config_accepts_valid(self) -> None:
        block = DiscussionGuide()
        config = {
            "research_objectives": ["Understand needs", "Explore pain points"],
            "interview_type": "idi",
            "duration_minutes": 60,
            "model": "claude-sonnet-4-6",
            "temperature": 0.5,
            "seed": 42,
        }
        assert block.validate_config(config) is True

    def test_validate_config_rejects_missing_objectives(self) -> None:
        block = DiscussionGuide()
        config = {"interview_type": "idi"}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_empty_objectives(self) -> None:
        block = DiscussionGuide()
        config = {"research_objectives": []}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_invalid_objective_type(self) -> None:
        block = DiscussionGuide()
        assert block.validate_config({"research_objectives": "not a list"}) is False

    def test_validate_config_rejects_empty_objective_string(self) -> None:
        block = DiscussionGuide()
        assert block.validate_config({"research_objectives": ["valid", "   "]}) is False

    def test_validate_config_rejects_invalid_interview_type(self) -> None:
        block = DiscussionGuide()
        assert (
            block.validate_config({"research_objectives": ["test"], "interview_type": "invalid"})
            is False
        )

    def test_validate_config_rejects_invalid_duration(self) -> None:
        block = DiscussionGuide()
        # Too small
        assert (
            block.validate_config({"research_objectives": ["test"], "duration_minutes": 10})
            is False
        )
        # Too large
        assert (
            block.validate_config({"research_objectives": ["test"], "duration_minutes": 200})
            is False
        )
        # Wrong type
        assert (
            block.validate_config({"research_objectives": ["test"], "duration_minutes": "60"})
            is False
        )

    def test_validate_config_rejects_invalid_temperature(self) -> None:
        block = DiscussionGuide()
        # Too low
        assert (
            block.validate_config({"research_objectives": ["test"], "temperature": -0.1}) is False
        )
        # Too high
        assert block.validate_config({"research_objectives": ["test"], "temperature": 1.1}) is False
        # Wrong type
        assert (
            block.validate_config({"research_objectives": ["test"], "temperature": "high"}) is False
        )

    def test_validate_config_rejects_invalid_seed(self) -> None:
        block = DiscussionGuide()
        assert block.validate_config({"research_objectives": ["test"], "seed": "42"}) is False

    def test_validate_config_accepts_minimal(self) -> None:
        block = DiscussionGuide()
        config = {"research_objectives": ["Understand user needs"]}
        assert block.validate_config(config) is True

    @patch("blocks.generation.discussion_guide.call_llm")
    def test_execute_with_mocked_llm(self, mock_llm: AsyncMock) -> None:
        """Test execute with mocked LLM call."""
        # Setup mock response
        mock_llm.return_value = """# Discussion Guide

## Introduction
Welcome participants...

## Questions
1. What are your thoughts?
"""
        block = DiscussionGuide()
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"respondent_id": "r1", "age": "35-44", "needs": "ergonomic support"},
                    {"respondent_id": "r2", "age": "25-34", "needs": "better lighting"},
                ]
            }
        }
        config = {
            "research_objectives": ["Understand needs", "Explore pain points"],
            "interview_type": "idi",
            "duration_minutes": 60,
            "model": "claude-sonnet-4-6",
            "temperature": 0.5,
        }

        result = _run(block.execute(inputs, config))

        # Verify output structure
        assert "text_corpus" in result
        assert "documents" in result["text_corpus"]
        documents = result["text_corpus"]["documents"]
        assert len(documents) == 1
        assert isinstance(documents[0], str)
        assert len(documents[0]) > 0

        # Verify LLM was called with correct parameters
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["temperature"] == 0.5
        assert "IDI" in call_kwargs["user_prompt"] or "idi" in call_kwargs["user_prompt"]
        assert "60 minutes" in call_kwargs["user_prompt"]

    @patch("blocks.generation.discussion_guide.call_llm")
    def test_execute_handles_non_string_response(self, mock_llm: AsyncMock) -> None:
        """Test execute raises error when LLM response is not a string."""
        mock_llm.return_value = {"not": "a string"}

        block = DiscussionGuide()
        inputs = {"respondent_collection": {"rows": [{"id": "r1"}]}}
        config = {"research_objectives": ["Test objective"]}

        with pytest.raises(Exception) as exc_info:
            _run(block.execute(inputs, config))
        assert "not a string" in str(exc_info.value).lower()

    @patch("blocks.generation.discussion_guide.call_llm")
    def test_execute_handles_empty_response(self, mock_llm: AsyncMock) -> None:
        """Test execute raises error when LLM returns empty string."""
        mock_llm.return_value = "   "

        block = DiscussionGuide()
        inputs = {"respondent_collection": {"rows": [{"id": "r1"}]}}
        config = {"research_objectives": ["Test objective"]}

        with pytest.raises(Exception) as exc_info:
            _run(block.execute(inputs, config))
        assert "empty" in str(exc_info.value).lower()

    @patch("blocks.generation.discussion_guide.call_llm")
    def test_execute_handles_block_execution_error(self, mock_llm: AsyncMock) -> None:
        """Test execute propagates BlockExecutionError from LLM call."""
        from blocks._llm_client import BlockExecutionError

        mock_llm.side_effect = BlockExecutionError("API error")

        block = DiscussionGuide()
        inputs = {"respondent_collection": {"rows": [{"id": "r1"}]}}
        config = {"research_objectives": ["Test objective"]}

        with pytest.raises(Exception) as exc_info:
            _run(block.execute(inputs, config))
        assert "generation failed" in str(exc_info.value).lower()

    def test_test_fixtures(self) -> None:
        """Test that test_fixtures returns expected structure."""
        block = DiscussionGuide()
        fixtures = block.test_fixtures()

        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures

        # Verify config structure
        assert "research_objectives" in fixtures["config"]
        assert "interview_type" in fixtures["config"]
        assert "duration_minutes" in fixtures["config"]
        assert "model" in fixtures["config"]
        assert "temperature" in fixtures["config"]
        assert "seed" in fixtures["config"]

        # Verify inputs structure
        assert "respondent_collection" in fixtures["inputs"]

        # Verify expected output structure
        assert "text_corpus" in fixtures["expected_output"]
        assert "documents" in fixtures["expected_output"]["text_corpus"]

        # Verify validate_config accepts fixture config
        assert block.validate_config(fixtures["config"]) is True

    @patch("blocks.generation.discussion_guide.call_llm")
    def test_execute_with_focus_group_type(self, mock_llm: AsyncMock) -> None:
        """Test execute with focus_group interview type."""
        mock_llm.return_value = "# Focus Group Guide\n\n## Introduction\n..."

        block = DiscussionGuide()
        inputs = {"respondent_collection": {"rows": [{"id": "r1"}]}}
        config = {
            "research_objectives": ["Test objective"],
            "interview_type": "focus_group",
            "duration_minutes": 90,
        }

        result = _run(block.execute(inputs, config))

        assert "text_corpus" in result
        call_kwargs = mock_llm.call_args.kwargs
        assert (
            "FOCUS_GROUP" in call_kwargs["user_prompt"]
            or "focus_group" in call_kwargs["user_prompt"]
        )
        assert "90 minutes" in call_kwargs["user_prompt"]

    @patch("blocks.generation.discussion_guide.call_llm")
    def test_execute_with_online_type(self, mock_llm: AsyncMock) -> None:
        """Test execute with online interview type."""
        mock_llm.return_value = "# Online Interview Guide\n\n## Introduction\n..."

        block = DiscussionGuide()
        inputs = {"respondent_collection": {"rows": [{"id": "r1"}]}}
        config = {
            "research_objectives": ["Test objective"],
            "interview_type": "online",
            "duration_minutes": 30,
        }

        result = _run(block.execute(inputs, config))

        assert "text_corpus" in result
        call_kwargs = mock_llm.call_args.kwargs
        assert "ONLINE" in call_kwargs["user_prompt"] or "online" in call_kwargs["user_prompt"]
        assert "30 minutes" in call_kwargs["user_prompt"]

    def test_interview_type_enum_values(self) -> None:
        """Test that config_schema only allows valid interview_type values."""
        block = DiscussionGuide()
        schema = block.config_schema
        valid_types = schema["properties"]["interview_type"]["enum"]
        assert valid_types == ["idi", "focus_group", "online"]
