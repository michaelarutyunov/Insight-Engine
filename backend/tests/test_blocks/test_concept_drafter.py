"""Tests for ConceptDrafter block."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks.generation.concept_drafter import ConceptDrafter


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


class TestConceptDrafter:
    """Test suite for ConceptDrafter block."""

    def test_block_type(self) -> None:
        block = ConceptDrafter()
        assert block.block_type == "generation"

    def test_input_schemas(self) -> None:
        block = ConceptDrafter()
        assert block.input_schemas == ["respondent_collection"]

    def test_output_schemas(self) -> None:
        block = ConceptDrafter()
        assert block.output_schemas == ["concept_brief_set"]

    def test_config_schema(self) -> None:
        block = ConceptDrafter()
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "prompt_template" in schema["properties"]
        assert "n_concepts" in schema["properties"]
        assert "model" in schema["properties"]
        assert "temperature" in schema["properties"]
        assert "seed" in schema["properties"]
        assert schema["required"] == ["prompt_template"]

    def test_description(self) -> None:
        block = ConceptDrafter()
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_methodological_notes(self) -> None:
        block = ConceptDrafter()
        assert isinstance(block.methodological_notes, str)
        assert len(block.methodological_notes) > 0

    def test_tags(self) -> None:
        block = ConceptDrafter()
        tags = block.tags
        assert isinstance(tags, list)
        assert "llm" in tags
        assert "generation" in tags
        assert "concepts" in tags

    def test_validate_config_accepts_valid(self) -> None:
        block = ConceptDrafter()
        config = {
            "prompt_template": "Generate concepts: {input}",
            "n_concepts": 5,
            "model": "claude-sonnet-4-6",
            "temperature": 0.7,
            "seed": 42,
        }
        assert block.validate_config(config) is True

    def test_validate_config_rejects_missing_prompt(self) -> None:
        block = ConceptDrafter()
        config = {"n_concepts": 5}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_empty_prompt(self) -> None:
        block = ConceptDrafter()
        config = {"prompt_template": "   "}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_invalid_n_concepts(self) -> None:
        block = ConceptDrafter()
        # Too small
        assert block.validate_config({"prompt_template": "test", "n_concepts": 0}) is False
        # Too large
        assert block.validate_config({"prompt_template": "test", "n_concepts": 21}) is False
        # Wrong type
        assert block.validate_config({"prompt_template": "test", "n_concepts": "five"}) is False

    def test_validate_config_rejects_invalid_temperature(self) -> None:
        block = ConceptDrafter()
        # Too low
        assert block.validate_config({"prompt_template": "test", "temperature": -0.1}) is False
        # Too high
        assert block.validate_config({"prompt_template": "test", "temperature": 1.1}) is False
        # Wrong type
        assert block.validate_config({"prompt_template": "test", "temperature": "high"}) is False

    def test_validate_config_rejects_invalid_seed(self) -> None:
        block = ConceptDrafter()
        assert block.validate_config({"prompt_template": "test", "seed": "42"}) is False

    def test_validate_config_accepts_minimal(self) -> None:
        block = ConceptDrafter()
        config = {"prompt_template": "Generate concepts: {input}"}
        assert block.validate_config(config) is True

    @patch("blocks.generation.concept_drafter.call_llm_json")
    def test_execute_with_mocked_llm(self, mock_llm: AsyncMock) -> None:
        """Test execute with mocked LLM call."""
        # Setup mock response
        mock_llm.return_value = {
            "concepts": [
                {
                    "name": "Test Concept 1",
                    "description": "A test concept for validation",
                    "differentiators": ["Feature 1", "Feature 2", "Feature 3"],
                },
                {
                    "name": "Test Concept 2",
                    "description": "Another test concept",
                    "differentiators": ["Unique feature 1", "Unique feature 2"],
                },
            ]
        }

        block = ConceptDrafter()
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"respondent_id": "r1", "need": "ergonomic support"},
                    {"respondent_id": "r2", "need": "better lighting"},
                ]
            }
        }
        config = {
            "prompt_template": "Generate furniture concepts: {input}",
            "n_concepts": 2,
            "model": "claude-sonnet-4-6",
            "temperature": 0.7,
        }

        result = _run(block.execute(inputs, config))

        # Verify output structure
        assert "concept_brief_set" in result
        assert "concepts" in result["concept_brief_set"]
        concepts = result["concept_brief_set"]["concepts"]
        assert len(concepts) == 2
        assert all("name" in c for c in concepts)
        assert all("description" in c for c in concepts)
        assert all("differentiators" in c for c in concepts)

        # Verify LLM was called with correct parameters
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["temperature"] == 0.7
        assert "Generate furniture concepts:" in call_kwargs["user_prompt"]

    @patch("blocks.generation.concept_drafter.call_llm_json")
    def test_execute_handles_missing_concepts_key(self, mock_llm: AsyncMock) -> None:
        """Test execute raises error when LLM response missing concepts key."""
        mock_llm.return_value = {"wrong_key": []}

        block = ConceptDrafter()
        inputs = {"respondent_collection": {"rows": [{"id": "r1"}]}}
        config = {"prompt_template": "Generate concepts: {input}"}

        with pytest.raises(Exception) as exc_info:
            _run(block.execute(inputs, config))
        assert "missing 'concepts' key" in str(exc_info.value).lower()

    @patch("blocks.generation.concept_drafter.call_llm_json")
    def test_execute_handles_invalid_concepts_structure(self, mock_llm: AsyncMock) -> None:
        """Test execute raises error when concepts is not a list."""
        mock_llm.return_value = {"concepts": "not a list"}

        block = ConceptDrafter()
        inputs = {"respondent_collection": {"rows": [{"id": "r1"}]}}
        config = {"prompt_template": "Generate concepts: {input}"}

        with pytest.raises(Exception) as exc_info:
            _run(block.execute(inputs, config))
        assert "not a list" in str(exc_info.value).lower()

    @patch("blocks.generation.concept_drafter.call_llm_json")
    def test_execute_handles_missing_concept_fields(self, mock_llm: AsyncMock) -> None:
        """Test execute raises error when concept missing required fields."""
        mock_llm.return_value = {
            "concepts": [
                {
                    "name": "Incomplete Concept",
                    # Missing 'description' and 'differentiators'
                }
            ]
        }

        block = ConceptDrafter()
        inputs = {"respondent_collection": {"rows": [{"id": "r1"}]}}
        config = {"prompt_template": "Generate concepts: {input}"}

        with pytest.raises(Exception) as exc_info:
            _run(block.execute(inputs, config))
        assert "missing required field" in str(exc_info.value).lower()

    def test_test_fixtures(self) -> None:
        """Test that test_fixtures returns expected structure."""
        block = ConceptDrafter()
        fixtures = block.test_fixtures()

        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures

        # Verify config structure
        assert "prompt_template" in fixtures["config"]
        assert "n_concepts" in fixtures["config"]
        assert "model" in fixtures["config"]
        assert "temperature" in fixtures["config"]
        assert "seed" in fixtures["config"]

        # Verify inputs structure
        assert "respondent_collection" in fixtures["inputs"]

        # Verify expected output structure
        assert "concept_brief_set" in fixtures["expected_output"]
        assert "concepts" in fixtures["expected_output"]["concept_brief_set"]

        # Verify validate_config accepts fixture config
        assert block.validate_config(fixtures["config"]) is True
