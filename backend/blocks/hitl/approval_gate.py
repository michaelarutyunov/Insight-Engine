"""Approval Gate HITL block — suspends execution for human review and approval."""

from typing import Any

from blocks._llm_client import BlockExecutionError, HITLSuspendSignal
from blocks.base import HITLBase
from schemas.data_objects import DATA_TYPES


class ApprovalGate(HITLBase):
    """Human approval checkpoint. Pauses pipeline execution and presents data for human review.

    Reviewer can approve, reject, or modify data before continuing.
    """

    @property
    def input_schemas(self) -> list[str]:
        return sorted(DATA_TYPES)

    @property
    def output_schemas(self) -> list[str]:
        return sorted(DATA_TYPES)

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt_text": {
                    "type": "string",
                    "default": "Please review and approve the following data",
                    "description": "Message displayed to the human reviewer",
                },
                "require_comment": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether a comment is required on approval/rejection",
                },
                "allow_modification": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether the reviewer can modify the data before approval",
                },
            },
        }

    @property
    def description(self) -> str:
        return "Human approval checkpoint. Pauses pipeline execution and presents data for human review. Reviewer can approve, reject, or modify data before continuing."

    def validate_config(self, config: dict) -> bool:
        """Validate the configuration.

        Args:
            config: Configuration dictionary

        Returns:
            True if config is valid
        """
        prompt_text = config.get("prompt_text", "")
        if not isinstance(prompt_text, str):
            return False

        require_comment = config.get("require_comment", False)
        if not isinstance(require_comment, bool):
            return False

        allow_modification = config.get("allow_modification", False)
        return isinstance(allow_modification, bool)

    def render_checkpoint(self, inputs: dict[str, Any]) -> dict:
        """Prepare data to present to the human reviewer.

        Args:
            inputs: Input data from previous blocks

        Returns:
            Dictionary containing prompt, data, and config flags
        """
        config = inputs.get("_config", {})
        return {
            "prompt": config.get("prompt_text", "Please review and approve the following data"),
            "data": inputs,
            "require_comment": config.get("require_comment", False),
            "allow_modification": config.get("allow_modification", False),
        }

    def process_response(
        self, human_input: dict, original_inputs: dict[str, Any], config: dict
    ) -> dict[str, Any]:
        """Handle the human's response and produce the block's output.

        Args:
            human_input: Human's response with approved, comment, and optional modified_data
            original_inputs: Original input data
            config: Block configuration

        Returns:
            Output data dictionary

        Raises:
            BlockExecutionError: If approval is rejected or validation fails
        """
        approved = human_input.get("approved")
        if not isinstance(approved, bool):
            raise BlockExecutionError("Response must include 'approved' boolean field")

        comment = human_input.get("comment", "")
        modified_data = human_input.get("modified_data")

        # Check comment requirement
        require_comment = config.get("require_comment", False)
        if require_comment and not comment:
            raise BlockExecutionError("Comment is required when require_comment is true")

        # Handle rejection
        if not approved:
            reason = comment or "No reason provided"
            raise BlockExecutionError(f"Approval rejected: {reason}")

        # Find the actual data key (skip internal keys like _config, _execution_context)
        data_key = next(
            (k for k in original_inputs if not k.startswith("_")),
            "generic_blob",
        )

        # Handle approval with modification
        allow_modification = config.get("allow_modification", False)
        if allow_modification and modified_data is not None:
            if not isinstance(modified_data, dict):
                raise BlockExecutionError("modified_data must be a dictionary")
            return {data_key: modified_data}

        # Handle simple approval - pass through original data
        return {data_key: original_inputs.get(data_key, {})}

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        """Execute this block.

        Args:
            inputs: Input data dictionary
            config: Block configuration

        Raises:
            HITLSuspendSignal: Always raises to signal execution should suspend
        """
        # Inject config into inputs for render_checkpoint
        inputs_with_config = {**inputs, "_config": config}

        checkpoint = self.render_checkpoint(inputs_with_config)
        raise HITLSuspendSignal(checkpoint_data=checkpoint)

    def test_fixtures(self) -> dict:
        """Provide sample inputs, config, and expected outputs for contract tests."""
        return {
            "config": {
                "prompt_text": "Please review this data before proceeding",
                "require_comment": False,
                "allow_modification": False,
            },
            "inputs": {
                "generic_blob": {"key": "value", "items": [1, 2, 3]},
            },
            "expected_output": {
                "generic_blob": {"key": "value", "items": [1, 2, 3]},
            },
            "expected_checkpoint": {
                "prompt": "Please review this data before proceeding",
                "data": {
                    "generic_blob": {"key": "value", "items": [1, 2, 3]},
                    "_config": {
                        "prompt_text": "Please review this data before proceeding",
                        "require_comment": False,
                        "allow_modification": False,
                    },
                },
                "require_comment": False,
                "allow_modification": False,
            },
            "test_approve_response": {
                "approved": True,
                "comment": "Looks good!",
            },
            "test_reject_response": {
                "approved": False,
                "comment": "Data is incorrect",
            },
            "test_modify_response": {
                "approved": True,
                "comment": "Made some corrections",
                "modified_data": {"key": "modified_value", "items": [4, 5, 6]},
            },
            "config_with_require_comment": {
                "prompt_text": "Please review",
                "require_comment": True,
                "allow_modification": False,
            },
            "config_with_allow_modification": {
                "prompt_text": "Please review",
                "require_comment": False,
                "allow_modification": True,
            },
        }
