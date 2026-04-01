"""Tests for PresentationOutline block."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks.reporting.presentation_outline import PresentationOutline


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


class TestPresentationOutline:
    """Test suite for PresentationOutline block."""

    def test_block_type_is_reporting(self):
        block = PresentationOutline()
        assert block.block_type == "reporting"

    def test_input_schemas(self):
        block = PresentationOutline()
        assert block.input_schemas == ["evaluation_set", "text_corpus"]

    def test_output_schemas(self):
        block = PresentationOutline()
        assert block.output_schemas == ["text_corpus"]

    def test_declare_pipeline_inputs(self):
        block = PresentationOutline()
        assert block.declare_pipeline_inputs() == ["evaluation_set", "text_corpus"]

    def test_config_schema_structure(self):
        block = PresentationOutline()
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "n_slides" in schema["properties"]
        assert "format" in schema["properties"]
        assert "audience" in schema["properties"]
        assert "model" in schema["properties"]
        assert "temperature" in schema["properties"]
        assert schema["additionalProperties"] is False

    def test_validate_config_accepts_minimal(self):
        block = PresentationOutline()
        # Empty config should use all defaults
        assert block.validate_config({}) is True

    def test_validate_config_accepts_full_config(self):
        block = PresentationOutline()
        config = {
            "n_slides": 15,
            "format": "narrative",
            "audience": "researchers",
            "model": "claude-opus-4-20250514",
            "temperature": 0.7,
        }
        assert block.validate_config(config) is True

    def test_validate_config_rejects_invalid_n_slides(self):
        block = PresentationOutline()
        assert block.validate_config({"n_slides": 0}) is False
        assert block.validate_config({"n_slides": -1}) is False
        assert block.validate_config({"n_slides": 51}) is False
        assert block.validate_config({"n_slides": "ten"}) is False

    def test_validate_config_rejects_invalid_format(self):
        block = PresentationOutline()
        assert block.validate_config({"format": "invalid"}) is False
        assert block.validate_config({"format": 123}) is False

    def test_validate_config_rejects_invalid_audience(self):
        block = PresentationOutline()
        assert block.validate_config({"audience": 123}) is False
        assert block.validate_config({"audience": ["list"]}) is False

    def test_validate_config_rejects_invalid_model(self):
        block = PresentationOutline()
        assert block.validate_config({"model": ""}) is False
        assert block.validate_config({"model": 123}) is False

    def test_validate_config_rejects_invalid_temperature(self):
        block = PresentationOutline()
        assert block.validate_config({"temperature": -0.1}) is False
        assert block.validate_config({"temperature": 1.1}) is False
        assert block.validate_config({"temperature": "high"}) is False

    def test_description_is_nonempty_string(self):
        block = PresentationOutline()
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_methodological_notes_is_nonempty_string(self):
        block = PresentationOutline()
        assert isinstance(block.methodological_notes, str)
        assert len(block.methodological_notes) > 0

    def test_tags(self):
        block = PresentationOutline()
        tags = block.tags
        assert isinstance(tags, list)
        assert "reporting" in tags
        assert "llm" in tags
        assert "presentation" in tags

    def test_has_test_fixtures(self):
        block = PresentationOutline()
        fixtures = block.test_fixtures()
        assert isinstance(fixtures, dict)
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures

    def test_validate_config_accepts_fixture_config(self):
        block = PresentationOutline()
        config = block.test_fixtures()["config"]
        assert block.validate_config(config) is True

    def test_execute_returns_declared_outputs(self):
        block = PresentationOutline()
        fixtures = block.test_fixtures()

        # Mock the LLM call
        with patch("blocks.reporting.presentation_outline.call_llm") as mock_llm:
            # Return a simple outline
            mock_llm.return_value = "Slide 1: Title\n- Point 1\n\nSlide 2: Content\n- Point 2"
            result = _run(block.execute(fixtures["inputs"], fixtures["config"]))

        assert isinstance(result, dict)
        assert "text_corpus" in result
        assert "documents" in result["text_corpus"]
        assert len(result["text_corpus"]["documents"]) == 1

    def test_execute_calls_llm_with_correct_parameters(self):
        block = PresentationOutline()
        fixtures = block.test_fixtures()

        with patch("blocks.reporting.presentation_outline.call_llm") as mock_llm:
            mock_llm.return_value = "Mock outline"
            _run(block.execute(fixtures["inputs"], fixtures["config"]))

            # Verify LLM was called
            assert mock_llm.call_count == 1
            call_kwargs = mock_llm.call_args.kwargs

            # Check parameters
            assert call_kwargs["model"] == "claude-sonnet-4-20250514"
            assert call_kwargs["temperature"] == 0.5
            assert "system_prompt" in call_kwargs
            assert "user_prompt" in call_kwargs

    def test_execute_with_bullet_format(self):
        block = PresentationOutline()
        config = {"n_slides": 3, "format": "bullet"}
        inputs = {
            "evaluation_set": {"evaluations": [{"subject": "A", "scores": {"q": 5}}]},
            "text_corpus": {"documents": ["Test doc"]},
        }

        with patch("blocks.reporting.presentation_outline.call_llm") as mock_llm:
            mock_llm.return_value = "Slide 1: Test\n- Bullet 1"
            _run(block.execute(inputs, config))

            # Verify bullet format was included in prompt
            call_kwargs = mock_llm.call_args.kwargs
            assert "bullet" in call_kwargs["user_prompt"]
            assert "narrative" not in call_kwargs["user_prompt"]

    def test_execute_with_narrative_format(self):
        block = PresentationOutline()
        config = {"n_slides": 3, "format": "narrative"}
        inputs = {
            "evaluation_set": {"evaluations": [{"subject": "A", "scores": {"q": 5}}]},
            "text_corpus": {"documents": ["Test doc"]},
        }

        with patch("blocks.reporting.presentation_outline.call_llm") as mock_llm:
            mock_llm.return_value = "Slide 1: Test\nDetailed description"
            _run(block.execute(inputs, config))

            # Verify narrative format was included in prompt
            call_kwargs = mock_llm.call_args.kwargs
            assert "narrative" in call_kwargs["user_prompt"]

    def test_execute_handles_empty_evaluation_set(self):
        block = PresentationOutline()
        config = {"n_slides": 2}
        inputs = {
            "evaluation_set": {"evaluations": []},
            "text_corpus": {"documents": ["Test"]},
        }

        with patch("blocks.reporting.presentation_outline.call_llm") as mock_llm:
            mock_llm.return_value = "Slide 1: Title\n- Point"
            result = _run(block.execute(inputs, config))

            # Verify execution completes
            assert "text_corpus" in result
            # Verify LLM was still called
            assert mock_llm.call_count == 1

    def test_execute_handles_empty_text_corpus(self):
        block = PresentationOutline()
        config = {"n_slides": 2}
        inputs = {
            "evaluation_set": {"evaluations": [{"subject": "A"}]},
            "text_corpus": {"documents": []},
        }

        with patch("blocks.reporting.presentation_outline.call_llm") as mock_llm:
            mock_llm.return_value = "Slide 1: Title\n- Point"
            result = _run(block.execute(inputs, config))

            # Verify execution completes
            assert "text_corpus" in result

    def test_format_evaluations(self):
        block = PresentationOutline()
        evaluations = [
            {"subject": "A", "scores": {"q": 5}},
            {"subject": "B", "scores": {"q": 7}},
        ]
        result = block._format_evaluations(evaluations)
        assert "Evaluation 1:" in result
        assert "Evaluation 2:" in result
        assert "subject" in result

    def test_format_evaluations_empty(self):
        block = PresentationOutline()
        result = block._format_evaluations([])
        assert "No evaluation data" in result

    def test_format_documents(self):
        block = PresentationOutline()
        documents = ["Doc 1 content here", "Doc 2 content here"]
        result = block._format_documents(documents)
        assert "Document 1:" in result
        assert "Document 2:" in result
        assert "Doc 1 content" in result

    def test_format_documents_truncates_long(self):
        block = PresentationOutline()
        long_doc = "x" * 1000
        result = block._format_documents([long_doc])
        assert "truncated" in result
        assert len(result) < len(long_doc)

    def test_format_documents_empty(self):
        block = PresentationOutline()
        result = block._format_documents([])
        assert "No supporting documents" in result
