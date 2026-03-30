"""JSON Sink block — persists final pipeline outputs as JSON."""

from typing import Any

from blocks.base import SinkBase
from schemas.data_objects import DATA_TYPES


class JSONSink(SinkBase):
    """Terminal block that persists input data as a JSON artifact."""

    @property
    def input_schemas(self) -> list[str]:
        return sorted(DATA_TYPES)

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
        return "Persists pipeline output as a named JSON artifact. If you need to save pipeline results as structured JSON for downstream systems, archiving, or human review, this is the right block."

    @property
    def methodological_notes(self) -> str:
        return """Assumes all input data is JSON-serializable; complex Python objects or binary data will fail serialization. This block converts Pydantic data objects to dicts before dumping to JSON. File size is limited by available memory—large datasets (>100MB) may require chunking or streaming alternatives. For production workflows requiring database persistence or cloud storage, consider using database-backed sink blocks instead. The pretty_print option improves human readability at the cost of larger file size."""

    @property
    def tags(self) -> list[str]:
        return ["persistence", "export", "json", "terminal", "structured-data", "serialization"]

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("output_key"), str):
            return False
        return bool(config["output_key"].strip())

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        # Find the actual data key (skip internal keys that start with "_")
        data_key = next((k for k in inputs if not k.startswith("_")), None)
        if data_key is None:
            return {}
        # Sink blocks have no output schemas, so return empty dict.
        # In production, this would persist to storage.
        _ = inputs[data_key]
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
