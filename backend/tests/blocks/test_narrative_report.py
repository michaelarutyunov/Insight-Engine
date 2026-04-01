"""Tests for NarrativeReport block."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks.reporting.narrative_report import NarrativeReport  # noqa: E402


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


class TestNarrativeReport:
    """Test suite for NarrativeReport block."""

    def test_block_type(self) -> None:
        """Verify block type is 'reporting'."""
        block = NarrativeReport()
        assert block.block_type == "reporting"

    def test_input_schemas(self) -> None:
        """Verify input schemas match specification."""
        block = NarrativeReport()
        expected_schemas = {"evaluation_set", "text_corpus", "segment_profile_set"}
        assert set(block.input_schemas) == expected_schemas

    def test_output_schemas(self) -> None:
        """Verify output schemas match specification."""
        block = NarrativeReport()
        assert block.output_schemas == ["text_corpus"]

    def test_config_schema_structure(self) -> None:
        """Verify config schema is valid JSON Schema."""
        block = NarrativeReport()
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert "narrative_style" in schema["required"]
        assert "additionalProperties" in schema
        assert schema["additionalProperties"] is False

    def test_narrative_style_enum(self) -> None:
        """Verify narrative_style has correct enum values."""
        block = NarrativeReport()
        style_prop = block.config_schema["properties"]["narrative_style"]
        assert set(style_prop["enum"]) == {
            "executive_summary",
            "detailed",
            "presentation_notes",
        }

    def test_validate_config_accepts_valid(self) -> None:
        """Verify validate_config accepts valid configuration."""
        block = NarrativeReport()
        config = {
            "narrative_style": "executive_summary",
            "audience": "executives",
            "max_length": 2000,
            "model": "claude-sonnet-4-6",
            "temperature": 0.5,
            "seed": 42,
        }
        assert block.validate_config(config) is True

    def test_validate_config_rejects_missing_style(self) -> None:
        """Verify validate_config rejects missing narrative_style."""
        block = NarrativeReport()
        assert block.validate_config({}) is False
        assert block.validate_config({"audience": "team"}) is False

    def test_validate_config_rejects_invalid_style(self) -> None:
        """Verify validate_config rejects invalid narrative_style."""
        block = NarrativeReport()
        assert block.validate_config({"narrative_style": "invalid"}) is False
        assert block.validate_config({"narrative_style": ""}) is False

    def test_validate_config_rejects_empty_audience(self) -> None:
        """Verify validate_config rejects empty audience string."""
        block = NarrativeReport()
        assert block.validate_config({"narrative_style": "detailed", "audience": ""}) is False

    def test_validate_config_rejects_invalid_max_length(self) -> None:
        """Verify validate_config rejects invalid max_length."""
        block = NarrativeReport()
        assert (
            block.validate_config({"narrative_style": "detailed", "max_length": 100}) is False
        )  # Too low
        assert (
            block.validate_config({"narrative_style": "detailed", "max_length": 20000}) is False
        )  # Too high
        assert (
            block.validate_config({"narrative_style": "detailed", "max_length": "not_a_number"})
            is False
        )

    def test_validate_config_rejects_invalid_temperature(self) -> None:
        """Verify validate_config rejects invalid temperature."""
        block = NarrativeReport()
        assert block.validate_config({"narrative_style": "detailed", "temperature": -0.1}) is False
        assert block.validate_config({"narrative_style": "detailed", "temperature": 1.1}) is False

    def test_declare_pipeline_inputs(self) -> None:
        """Verify declare_pipeline_inputs returns correct input list."""
        block = NarrativeReport()
        expected = ["evaluation_set", "text_corpus", "segment_profile_set"]
        assert block.declare_pipeline_inputs() == expected

    def test_description_is_nonempty(self) -> None:
        """Verify description is present and non-empty."""
        block = NarrativeReport()
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_methodological_notes_is_nonempty(self) -> None:
        """Verify methodological_notes is present and non-empty."""
        block = NarrativeReport()
        assert isinstance(block.methodological_notes, str)
        assert len(block.methodological_notes) > 0

    def test_tags_are_present(self) -> None:
        """Verify tags are present and include expected values."""
        block = NarrativeReport()
        tags = block.tags
        assert isinstance(tags, list)
        assert len(tags) > 0
        assert "reporting" in tags
        assert "llm" in tags
        assert "narrative" in tags

    def test_execute_returns_declared_outputs(self) -> None:
        """Verify execute returns all declared output ports."""
        block = NarrativeReport()
        fixtures = block.test_fixtures()

        # Mock the LLM call to return expected output
        with patch("blocks.reporting.narrative_report.call_llm") as mock_llm:
            # Return the expected narrative from fixtures
            mock_llm.return_value = fixtures["expected_output"]["text_corpus"]["documents"][0]

            result = _run(block.execute(fixtures["inputs"], fixtures["config"]))

            assert isinstance(result, dict)
            assert "text_corpus" in result
            assert "documents" in result["text_corpus"]
            assert isinstance(result["text_corpus"]["documents"], list)

    def test_execute_with_missing_inputs(self) -> None:
        """Verify execute handles missing input data gracefully."""
        block = NarrativeReport()
        config = {"narrative_style": "executive_summary"}
        inputs = {}  # Empty inputs

        with patch("blocks.reporting.narrative_report.call_llm") as mock_llm:
            mock_llm.return_value = "Test narrative with no data."

            result = _run(block.execute(inputs, config))

            assert "text_corpus" in result
            assert len(result["text_corpus"]["documents"]) == 1

    def test_execute_executive_summary_style(self) -> None:
        """Verify executive_summary style generates appropriate prompt."""
        block = NarrativeReport()
        config = {"narrative_style": "executive_summary"}
        inputs = {
            "evaluation_set": {"evaluations": [{"subject": "A", "scores": {"quality": 8}}]},
            "text_corpus": {"documents": ["Sample document"]},
            "segment_profile_set": {"segments": [{"name": "Segment 1"}]},
        }

        with patch("blocks.reporting.narrative_report.call_llm") as mock_llm:
            mock_llm.return_value = "Executive summary content."

            _run(block.execute(inputs, config))

            # Verify LLM was called
            assert mock_llm.call_count == 1
            call_kwargs = mock_llm.call_args.kwargs
            assert "executive" in call_kwargs["system_prompt"].lower()

    def test_execute_detailed_style(self) -> None:
        """Verify detailed style generates appropriate prompt."""
        block = NarrativeReport()
        config = {"narrative_style": "detailed"}
        inputs = {
            "evaluation_set": {"evaluations": []},
            "text_corpus": {"documents": []},
            "segment_profile_set": {"segments": []},
        }

        with patch("blocks.reporting.narrative_report.call_llm") as mock_llm:
            mock_llm.return_value = "Detailed report content."

            _run(block.execute(inputs, config))

            # Verify LLM was called
            assert mock_llm.call_count == 1
            call_kwargs = mock_llm.call_args.kwargs
            assert (
                "detailed" in call_kwargs["system_prompt"].lower()
                or "comprehensive" in call_kwargs["system_prompt"].lower()
            )

    def test_execute_presentation_notes_style(self) -> None:
        """Verify presentation_notes style generates appropriate prompt."""
        block = NarrativeReport()
        config = {"narrative_style": "presentation_notes"}
        inputs = {
            "evaluation_set": {"evaluations": []},
            "text_corpus": {"documents": []},
            "segment_profile_set": {"segments": []},
        }

        with patch("blocks.reporting.narrative_report.call_llm") as mock_llm:
            mock_llm.return_value = "Presentation notes content."

            _run(block.execute(inputs, config))

            # Verify LLM was called
            assert mock_llm.call_count == 1
            call_kwargs = mock_llm.call_args.kwargs
            assert "presentation" in call_kwargs["system_prompt"].lower()

    def test_execute_includes_audience_in_prompt(self) -> None:
        """Verify audience parameter is included in user prompt."""
        block = NarrativeReport()
        config = {"narrative_style": "executive_summary", "audience": "stakeholders"}
        inputs = {
            "evaluation_set": {"evaluations": []},
            "text_corpus": {"documents": []},
            "segment_profile_set": {"segments": []},
        }

        with patch("blocks.reporting.narrative_report.call_llm") as mock_llm:
            mock_llm.return_value = "Narrative for stakeholders."

            _run(block.execute(inputs, config))

            # Verify audience is in prompt
            call_kwargs = mock_llm.call_args.kwargs
            assert "stakeholders" in call_kwargs["user_prompt"]

    def test_execute_passes_model_and_temperature(self) -> None:
        """Verify model and temperature are passed to LLM call."""
        block = NarrativeReport()
        config = {
            "narrative_style": "executive_summary",
            "model": "claude-opus-4-6",
            "temperature": 0.8,
        }
        inputs = {
            "evaluation_set": {"evaluations": []},
            "text_corpus": {"documents": []},
            "segment_profile_set": {"segments": []},
        }

        with patch("blocks.reporting.narrative_report.call_llm") as mock_llm:
            mock_llm.return_value = "Custom model output."

            _run(block.execute(inputs, config))

            # Verify model and temperature are passed
            call_kwargs = mock_llm.call_args.kwargs
            assert call_kwargs["model"] == "claude-opus-4-6"
            assert call_kwargs["temperature"] == 0.8

    def test_execute_limits_data_to_prevent_token_overflow(self) -> None:
        """Verify large datasets are truncated to prevent token overflow."""
        block = NarrativeReport()
        config = {"narrative_style": "detailed"}

        # Create large datasets
        large_evaluations = [{"subject": f"Eval {i}", "scores": {}} for i in range(100)]
        large_documents = [f"Document {i}" * 100 for i in range(50)]
        large_segments = [{"segment_id": f"seg_{i}"} for i in range(100)]

        inputs = {
            "evaluation_set": {"evaluations": large_evaluations},
            "text_corpus": {"documents": large_documents},
            "segment_profile_set": {"segments": large_segments},
        }

        with patch("blocks.reporting.narrative_report.call_llm") as mock_llm:
            mock_llm.return_value = "Truncated data narrative."

            _run(block.execute(inputs, config))

            # Verify LLM was called (data was truncated, not passed in full)
            assert mock_llm.call_count == 1
            call_kwargs = mock_llm.call_args.kwargs
            user_prompt = call_kwargs["user_prompt"]

            # Verify truncation by checking that not all items are in prompt
            # (evaluations limited to 10, segments to 10, documents to 5)
            assert "Eval 99" not in user_prompt  # Beyond the limit
            assert "Document 40" not in user_prompt  # Beyond the limit

    def test_test_fixtures_structure(self) -> None:
        """Verify test_fixtures returns valid structure."""
        block = NarrativeReport()
        fixtures = block.test_fixtures()

        assert isinstance(fixtures, dict)
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures

        # Verify config is valid
        assert block.validate_config(fixtures["config"]) is True

        # Verify inputs have all required keys
        assert "evaluation_set" in fixtures["inputs"]
        assert "text_corpus" in fixtures["inputs"]
        assert "segment_profile_set" in fixtures["inputs"]

        # Verify output structure
        assert "text_corpus" in fixtures["expected_output"]
        assert "documents" in fixtures["expected_output"]["text_corpus"]
