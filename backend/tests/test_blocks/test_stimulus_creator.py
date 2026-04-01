"""Tests for StimulusCreator block."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks.generation.stimulus_creator import StimulusCreator


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


class TestStimulusCreator:
    """Test suite for StimulusCreator block."""

    def test_block_type(self) -> None:
        block = StimulusCreator()
        assert block.block_type == "generation"

    def test_input_schemas(self) -> None:
        block = StimulusCreator()
        assert block.input_schemas == ["concept_brief_set"]

    def test_output_schemas(self) -> None:
        block = StimulusCreator()
        assert block.output_schemas == ["text_corpus"]

    def test_config_schema(self) -> None:
        block = StimulusCreator()
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "stimulus_type" in schema["properties"]
        assert "tone" in schema["properties"]
        assert "model" in schema["properties"]
        assert "temperature" in schema["properties"]
        assert "seed" in schema["properties"]
        assert schema["required"] == ["stimulus_type"]
        assert set(schema["properties"]["stimulus_type"]["enum"]) == {
            "concept_board",
            "ad_copy",
            "product_description",
        }

    def test_description(self) -> None:
        block = StimulusCreator()
        assert isinstance(block.description, str)
        assert len(block.description) > 0
        assert "concept" in block.description.lower()

    def test_methodological_notes(self) -> None:
        block = StimulusCreator()
        assert isinstance(block.methodological_notes, str)
        assert len(block.methodological_notes) > 0

    def test_tags(self) -> None:
        block = StimulusCreator()
        tags = block.tags
        assert isinstance(tags, list)
        assert "llm" in tags
        assert "generation" in tags
        assert "stimulus" in tags

    def test_validate_config_accepts_valid(self) -> None:
        block = StimulusCreator()
        config = {
            "stimulus_type": "product_description",
            "tone": "professional",
            "model": "claude-sonnet-4-6",
            "temperature": 0.7,
            "seed": 42,
        }
        assert block.validate_config(config) is True

    def test_validate_config_accepts_minimal(self) -> None:
        block = StimulusCreator()
        config = {"stimulus_type": "ad_copy"}
        assert block.validate_config(config) is True

    def test_validate_config_rejects_missing_stimulus_type(self) -> None:
        block = StimulusCreator()
        config = {"tone": "professional"}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_invalid_stimulus_type(self) -> None:
        block = StimulusCreator()
        config = {"stimulus_type": "invalid_type"}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_empty_tone(self) -> None:
        block = StimulusCreator()
        config = {"stimulus_type": "concept_board", "tone": "   "}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_invalid_temperature(self) -> None:
        block = StimulusCreator()
        # Too low
        assert (
            block.validate_config({"stimulus_type": "product_description", "temperature": -0.1})
            is False
        )
        # Too high
        assert (
            block.validate_config({"stimulus_type": "product_description", "temperature": 1.1})
            is False
        )
        # Wrong type
        assert (
            block.validate_config({"stimulus_type": "product_description", "temperature": "high"})
            is False
        )

    def test_validate_config_rejects_invalid_seed(self) -> None:
        block = StimulusCreator()
        assert (
            block.validate_config({"stimulus_type": "product_description", "seed": "42"}) is False
        )

    def test_validate_config_rejects_invalid_model(self) -> None:
        block = StimulusCreator()
        assert block.validate_config({"stimulus_type": "product_description", "model": ""}) is False

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_execute_with_mocked_llm_product_description(self, mock_llm: AsyncMock) -> None:
        """Test execute with mocked LLM call for product_description."""
        mock_llm.return_value = """Product Description 1

ErgoFlow Desk is a revolutionary height-adjustable workstation designed for modern professionals.

Key Features:
- Electric height adjustment
- Memory presets
- Cable management

Product Description 2

LumbarLife Chair features adaptive lumbar support for all-day comfort.

Key Features:
- Automatic lumbar adjustment
- Breathable mesh
- Battery-free operation"""

        block = StimulusCreator()
        inputs = {
            "concept_brief_set": {
                "concepts": [
                    {
                        "name": "ErgoFlow Desk",
                        "description": "Height-adjustable desk",
                        "differentiators": ["Electric", "Cable management"],
                    },
                    {
                        "name": "LumbarLife Chair",
                        "description": "Adaptive lumbar support chair",
                        "differentiators": ["Automatic", "Breathable"],
                    },
                ]
            }
        }
        config = {
            "stimulus_type": "product_description",
            "tone": "professional",
            "model": "claude-sonnet-4-6",
            "temperature": 0.7,
        }

        result = _run(block.execute(inputs, config))

        # Verify output structure
        assert "text_corpus" in result
        assert "documents" in result["text_corpus"]
        documents = result["text_corpus"]["documents"]
        assert len(documents) == 2
        assert all(isinstance(doc, str) for doc in documents)

        # Verify LLM was called with correct parameters
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["temperature"] == 0.7
        assert "professional" in call_kwargs["system_prompt"]
        assert "ErgoFlow Desk" in call_kwargs["user_prompt"]

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_execute_concept_board_type(self, mock_llm: AsyncMock) -> None:
        """Test execute with concept_board stimulus type."""
        mock_llm.return_value = """Concept Board 1

Visual description: Modern minimalist desk in natural wood finish.
Key visual elements: Clean lines, integrated keyboard tray.
Color palette: Warm oak, white accents, soft gray.

Concept Board 2

Visual description: Sleek ergonomic chair with mesh backing.
Key visual elements: Curved silhouette, adjustable lumbar.
Color palette: Charcoal gray, silver accents, black."""

        block = StimulusCreator()
        inputs = {
            "concept_brief_set": {
                "concepts": [
                    {
                        "name": "Desk Concept",
                        "description": "Minimalist desk design",
                        "differentiators": ["Wood finish", "Clean lines"],
                    },
                    {
                        "name": "Chair Concept",
                        "description": "Ergonomic chair",
                        "differentiators": ["Mesh back", "Adjustable"],
                    },
                ]
            }
        }
        config = {"stimulus_type": "concept_board"}

        result = _run(block.execute(inputs, config))

        assert "text_corpus" in result
        assert len(result["text_corpus"]["documents"]) == 2

        # Verify system prompt contains concept board instructions
        call_kwargs = mock_llm.call_args.kwargs
        assert "concept board" in call_kwargs["system_prompt"].lower()

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_execute_ad_copy_type(self, mock_llm: AsyncMock) -> None:
        """Test execute with ad_copy stimulus type."""
        mock_llm.return_value = """Ad Copy 1

Headline: Work Better, Live Better

Body: Transform your workspace with the ErgoFlow Desk. Designed for professionals who demand comfort and productivity.

Ad Copy 2

Headline: Sit In Comfort All Day

Body: Experience the LumbarLife difference. Adaptive support that moves with you."""

        block = StimulusCreator()
        inputs = {
            "concept_brief_set": {
                "concepts": [
                    {"name": "ErgoFlow", "description": "Height-adjustable desk"},
                    {"name": "LumbarLife", "description": "Ergonomic chair"},
                ]
            }
        }
        config = {"stimulus_type": "ad_copy", "tone": "persuasive"}

        result = _run(block.execute(inputs, config))

        assert "text_corpus" in result
        assert len(result["text_corpus"]["documents"]) == 2

        # Verify system prompt contains ad copy instructions and tone
        call_kwargs = mock_llm.call_args.kwargs
        assert "ad copy" in call_kwargs["system_prompt"].lower()
        assert "persuasive" in call_kwargs["system_prompt"]

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_execute_handles_invalid_concept_data(self, mock_llm: AsyncMock) -> None:
        """Test execute raises error when concept_brief_set is not a list."""
        mock_llm.return_value = "Response text"

        block = StimulusCreator()
        inputs = {"concept_brief_set": {"concepts": "not a list"}}
        config = {"stimulus_type": "product_description"}

        with pytest.raises(Exception) as exc_info:
            _run(block.execute(inputs, config))
        assert "must contain a list" in str(exc_info.value).lower()

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_execute_without_tone(self, mock_llm: AsyncMock) -> None:
        """Test execute works without optional tone parameter."""
        mock_llm.return_value = """Stimulus 1

Content for first concept.

Stimulus 2

Content for second concept."""

        block = StimulusCreator()
        inputs = {
            "concept_brief_set": {
                "concepts": [
                    {"name": "Concept 1", "description": "First"},
                    {"name": "Concept 2", "description": "Second"},
                ]
            }
        }
        config = {"stimulus_type": "product_description"}

        result = _run(block.execute(inputs, config))

        assert "text_corpus" in result
        assert len(result["text_corpus"]["documents"]) == 2

        # Verify system prompt doesn't contain tone guidance
        call_kwargs = mock_llm.call_args.kwargs
        assert "tone guidance:" not in call_kwargs["system_prompt"]

    def test_test_fixtures(self) -> None:
        """Test that test_fixtures returns expected structure."""
        block = StimulusCreator()
        fixtures = block.test_fixtures()

        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures

        # Verify config structure
        assert "stimulus_type" in fixtures["config"]
        assert "tone" in fixtures["config"]
        assert "model" in fixtures["config"]
        assert "temperature" in fixtures["config"]
        assert "seed" in fixtures["config"]

        # Verify inputs structure
        assert "concept_brief_set" in fixtures["inputs"]
        assert "concepts" in fixtures["inputs"]["concept_brief_set"]

        # Verify expected output structure
        assert "text_corpus" in fixtures["expected_output"]
        assert "documents" in fixtures["expected_output"]["text_corpus"]

        # Verify validate_config accepts fixture config
        assert block.validate_config(fixtures["config"]) is True

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_parse_response_with_common_delimiters(self, mock_llm: AsyncMock) -> None:
        """Test that response parsing handles common section delimiters."""
        mock_llm.return_value = """---

Stimulus 1 content here.

---

Stimulus 2 content here.

---

Stimulus 3 content here."""

        block = StimulusCreator()
        inputs = {
            "concept_brief_set": {
                "concepts": [
                    {"name": "C1"},
                    {"name": "C2"},
                    {"name": "C3"},
                ]
            }
        }
        config = {"stimulus_type": "product_description"}

        result = _run(block.execute(inputs, config))

        assert "text_corpus" in result
        assert len(result["text_corpus"]["documents"]) == 3

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_handles_mixed_concept_structures(self, mock_llm: AsyncMock) -> None:
        """Test execute handles concepts with different structures."""
        mock_llm.return_value = "Content 1\n\nContent 2"

        block = StimulusCreator()
        inputs = {
            "concept_brief_set": {
                "concepts": [
                    {
                        "name": "Complete Concept",
                        "description": "Full description",
                        "differentiators": ["feat1", "feat2"],
                    },
                    {
                        "name": "Minimal Concept",
                        # No differentiators
                    },
                ]
            }
        }
        config = {"stimulus_type": "ad_copy"}

        result = _run(block.execute(inputs, config))

        assert "text_corpus" in result
        assert len(result["text_corpus"]["documents"]) == 2

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_get_system_prompt_includes_tone(self, mock_llm: AsyncMock) -> None:
        """Test that system prompt includes tone when provided."""
        mock_llm.return_value = "Content"

        block = StimulusCreator()
        inputs = {"concept_brief_set": {"concepts": [{"name": "Test"}]}}
        config = {"stimulus_type": "product_description", "tone": "luxury"}

        _run(block.execute(inputs, config))

        call_kwargs = mock_llm.call_args.kwargs
        assert "luxury" in call_kwargs["system_prompt"]
        assert "Tone guidance:" in call_kwargs["system_prompt"]

    @patch("blocks.generation.stimulus_creator.call_llm")
    def test_build_user_prompt_formats_concepts(self, mock_llm: AsyncMock) -> None:
        """Test that user prompt correctly formats concept briefs."""
        mock_llm.return_value = "Generated content"

        block = StimulusCreator()
        inputs = {
            "concept_brief_set": {
                "concepts": [
                    {
                        "name": "Test Concept",
                        "description": "A test concept",
                        "differentiators": ["Feature 1", "Feature 2"],
                    }
                ]
            }
        }
        config = {"stimulus_type": "ad_copy"}

        _run(block.execute(inputs, config))

        call_kwargs = mock_llm.call_args.kwargs
        user_prompt = call_kwargs["user_prompt"]
        assert "Concept 1:" in user_prompt
        assert "Test Concept" in user_prompt
        assert "A test concept" in user_prompt
        assert "Feature 1" in user_prompt
