"""Tests for ApprovalGate HITL block."""

import pytest

from blocks._llm_client import BlockExecutionError, HITLSuspendSignal
from blocks.hitl.approval_gate import ApprovalGate
from schemas.data_objects import DATA_TYPES


class TestApprovalGate:
    """Test suite for ApprovalGate block."""

    def test_block_type(self) -> None:
        """Test that block_type is 'hitl'."""
        block = ApprovalGate()
        assert block.block_type == "hitl"

    def test_input_schemas(self) -> None:
        """Test that input_schemas includes all data types."""
        block = ApprovalGate()
        assert block.input_schemas == sorted(DATA_TYPES)

    def test_output_schemas(self) -> None:
        """Test that output_schemas includes all data types."""
        block = ApprovalGate()
        assert block.output_schemas == sorted(DATA_TYPES)

    def test_config_schema(self) -> None:
        """Test that config_schema has correct structure."""
        block = ApprovalGate()
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "prompt_text" in schema["properties"]
        assert "require_comment" in schema["properties"]
        assert "allow_modification" in schema["properties"]
        assert (
            schema["properties"]["prompt_text"]["default"]
            == "Please review and approve the following data"
        )
        assert schema["properties"]["require_comment"]["default"] is False
        assert schema["properties"]["allow_modification"]["default"] is False

    def test_description(self) -> None:
        """Test that description is a non-empty string."""
        block = ApprovalGate()
        assert isinstance(block.description, str)
        assert len(block.description) > 0
        assert "approval" in block.description.lower()

    def test_validate_config_with_valid_config(self) -> None:
        """Test validate_config with valid configuration."""
        block = ApprovalGate()
        config = {
            "prompt_text": "Please review",
            "require_comment": True,
            "allow_modification": False,
        }
        assert block.validate_config(config) is True

    def test_validate_config_with_defaults(self) -> None:
        """Test validate_config with default values."""
        block = ApprovalGate()
        config = {}
        assert block.validate_config(config) is True

    def test_validate_config_rejects_invalid_prompt_text(self) -> None:
        """Test validate_config rejects non-string prompt_text."""
        block = ApprovalGate()
        config = {"prompt_text": 123}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_invalid_require_comment(self) -> None:
        """Test validate_config rejects non-boolean require_comment."""
        block = ApprovalGate()
        config = {"require_comment": "yes"}
        assert block.validate_config(config) is False

    def test_validate_config_rejects_invalid_allow_modification(self) -> None:
        """Test validate_config rejects non-boolean allow_modification."""
        block = ApprovalGate()
        config = {"allow_modification": "yes"}
        assert block.validate_config(config) is False

    def test_render_checkpoint(self) -> None:
        """Test render_checkpoint returns structured review payload."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()
        inputs = {**fixtures["inputs"], "_config": fixtures["config"]}

        checkpoint = block.render_checkpoint(inputs)

        assert checkpoint == fixtures["expected_checkpoint"]
        assert "prompt" in checkpoint
        assert "data" in checkpoint
        assert "require_comment" in checkpoint
        assert "allow_modification" in checkpoint

    def test_render_checkpoint_with_defaults(self) -> None:
        """Test render_checkpoint uses default config values."""
        block = ApprovalGate()
        inputs = {"generic_blob": {"test": "data"}, "_config": {}}

        checkpoint = block.render_checkpoint(inputs)

        assert checkpoint["prompt"] == "Please review and approve the following data"
        assert checkpoint["require_comment"] is False
        assert checkpoint["allow_modification"] is False

    def test_process_response_with_approval(self) -> None:
        """Test process_response passes data through when approved."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        human_input = fixtures["test_approve_response"]
        result = block.process_response(human_input, fixtures["inputs"], fixtures["config"])

        assert result == fixtures["expected_output"]

    def test_process_response_with_rejection(self) -> None:
        """Test process_response raises BlockExecutionError when rejected."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        human_input = fixtures["test_reject_response"]

        with pytest.raises(BlockExecutionError) as exc_info:
            block.process_response(human_input, fixtures["inputs"], fixtures["config"])

        assert "Approval rejected" in str(exc_info.value)
        assert "Data is incorrect" in str(exc_info.value)

    def test_process_response_with_modification(self) -> None:
        """Test process_response respects modified_data when allow_modification is True."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        human_input = fixtures["test_modify_response"]
        config = fixtures["config_with_allow_modification"]

        result = block.process_response(human_input, fixtures["inputs"], config)

        assert result == {"generic_blob": {"key": "modified_value", "items": [4, 5, 6]}}

    def test_process_response_rejects_modification_when_disabled(self) -> None:
        """Test process_response ignores modified_data when allow_modification is False."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        human_input = fixtures["test_modify_response"]
        config = fixtures["config"]  # allow_modification is False

        result = block.process_response(human_input, fixtures["inputs"], config)

        # Should return original data, not modified_data
        assert result == fixtures["expected_output"]

    def test_process_response_requires_comment_when_configured(self) -> None:
        """Test process_response rejects responses without comment when require_comment is True."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        human_input = {"approved": True}  # No comment
        config = fixtures["config_with_require_comment"]

        with pytest.raises(BlockExecutionError) as exc_info:
            block.process_response(human_input, fixtures["inputs"], config)

        assert "Comment is required" in str(exc_info.value)

    def test_process_response_accepts_comment_when_required(self) -> None:
        """Test process_response accepts responses with comment when require_comment is True."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        human_input = {"approved": True, "comment": "Approved!"}
        config = fixtures["config_with_require_comment"]

        result = block.process_response(human_input, fixtures["inputs"], config)

        assert result == fixtures["expected_output"]

    def test_process_response_rejects_missing_approved_field(self) -> None:
        """Test process_response raises error when 'approved' field is missing."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        human_input = {"comment": "No approved field"}

        with pytest.raises(BlockExecutionError) as exc_info:
            block.process_response(human_input, fixtures["inputs"], fixtures["config"])

        assert "approved" in str(exc_info.value)

    def test_process_response_rejects_invalid_modified_data(self) -> None:
        """Test process_response raises error when modified_data is not a dict."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        human_input = {"approved": True, "modified_data": "not a dict"}
        config = fixtures["config_with_allow_modification"]

        with pytest.raises(BlockExecutionError) as exc_info:
            block.process_response(human_input, fixtures["inputs"], config)

        assert "modified_data must be a dictionary" in str(exc_info.value)

    async def test_execute_raises_suspend_signal(self) -> None:
        """Test execute raises HITLSuspendSignal with checkpoint data."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        with pytest.raises(HITLSuspendSignal) as exc_info:
            await block.execute(fixtures["inputs"], fixtures["config"])

        assert exc_info.value.checkpoint_data == fixtures["expected_checkpoint"]

    async def test_execute_injects_config_into_inputs(self) -> None:
        """Test execute injects config into inputs for render_checkpoint."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        with pytest.raises(HITLSuspendSignal) as exc_info:
            await block.execute(fixtures["inputs"], fixtures["config"])

        # Verify config was injected into checkpoint data
        checkpoint_data = exc_info.value.checkpoint_data
        assert "_config" in checkpoint_data["data"]
        assert checkpoint_data["data"]["_config"] == fixtures["config"]

    def test_test_fixtures(self) -> None:
        """Test that test_fixtures returns all required keys."""
        block = ApprovalGate()
        fixtures = block.test_fixtures()

        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures
        assert "expected_checkpoint" in fixtures
        assert "test_approve_response" in fixtures
        assert "test_reject_response" in fixtures
        assert "test_modify_response" in fixtures
        assert "config_with_require_comment" in fixtures
        assert "config_with_allow_modification" in fixtures
