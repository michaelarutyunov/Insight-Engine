"""Approval Gate HITL block — suspends execution for human review and approval."""

from typing import Any

from blocks.base import HITLBase


class ApprovalGate(HITLBase):
    """Suspends pipeline execution and presents data for human approval or rejection."""

    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "review_message": {
                    "type": "string",
                    "description": "Message displayed to the human reviewer",
                },
                "require_comment": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether a comment is required on approval/rejection",
                },
            },
            "required": ["review_message"],
        }

    @property
    def description(self) -> str:
        return "Suspends execution to present respondent data for human approval or rejection."

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("review_message"), str):
            return False
        return bool(config["review_message"].strip())

    def render_checkpoint(self, inputs: dict[str, Any]) -> dict:
        return {
            "review_message": "Please review the following data before proceeding.",
            "data": inputs.get("respondent_collection", {}),
            "actions": ["approve", "reject"],
        }

    def process_response(self, human_input: dict) -> dict[str, Any]:
        decision = human_input.get("decision", "reject")
        if decision == "approve":
            return {
                "respondent_collection": human_input.get("data", {}),
            }
        # On rejection, return empty collection
        return {"respondent_collection": {"rows": []}}

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:  # noqa: F841 — base contract requires config param
        # In normal execution, this would suspend and wait for HITL response.
        # For non-HITL execution paths, pass through the data unchanged.
        return {"respondent_collection": inputs["respondent_collection"]}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "review_message": "Please verify these respondents are valid.",
                "require_comment": True,
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [{"name": "Alice", "age": "30"}],
                },
            },
            "expected_output": {
                "respondent_collection": {
                    "rows": [{"name": "Alice", "age": "30"}],
                },
            },
            "expected_checkpoint": {
                "review_message": "Please review the following data before proceeding.",
                "data": {"rows": [{"name": "Alice", "age": "30"}]},
                "actions": ["approve", "reject"],
            },
            "expected_approve_output": {
                "respondent_collection": {
                    "rows": [{"name": "Alice", "age": "30"}],
                },
            },
            "expected_reject_output": {
                "respondent_collection": {"rows": []},
            },
        }
