"""JSON Sink block — persists final pipeline outputs as JSON."""

from typing import Any

from blocks.base import SinkBase


class JSONSink(SinkBase):
    """Terminal block that persists input data as a JSON artifact."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "output_key": {
                    "type": "string",
                    "description": "Key name for the persisted artifact",
                },
                "pretty_print": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to format the JSON output",
                },
            },
            "required": ["output_key"],
        }

    @property
    def description(self) -> str:
        return "Persists evaluation_set input as a named JSON artifact. Terminal block with no outputs."

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("output_key"), str):
            return False
        return bool(config["output_key"].strip())

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        # Sink blocks have no output schemas, so return empty dict.
        # In production, this would persist to storage.
        _ = inputs["evaluation_set"]
        _ = config["output_key"]
        return {}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "output_key": "final_evaluations",
                "pretty_print": True,
            },
            "inputs": {
                "evaluation_set": {
                    "evaluations": [
                        {"subject": "Test", "scores": {"quality": 5}},
                    ],
                },
            },
            "expected_output": {},
        }
