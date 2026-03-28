"""Filter Transform block — filters respondent rows by a column condition."""

from typing import Any

from blocks.base import TransformBase


class FilterTransform(TransformBase):
    """Deterministic transform that filters rows in a respondent_collection."""

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
                "column": {
                    "type": "string",
                    "description": "Column name to filter on",
                },
                "operator": {
                    "type": "string",
                    "enum": ["eq", "neq", "gt", "lt", "gte", "lte", "contains"],
                    "description": "Comparison operator",
                },
                "value": {
                    "description": "Value to compare against",
                },
            },
            "required": ["column", "operator", "value"],
        }

    @property
    def description(self) -> str:
        return "Filters respondent_collection rows by a column value using a comparison operator."

    def validate_config(self, config: dict) -> bool:
        if "column" not in config or not isinstance(config["column"], str):
            return False
        valid_ops = {"eq", "neq", "gt", "lt", "gte", "lte", "contains"}
        if config.get("operator") not in valid_ops:
            return False
        return "value" in config

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        collection = inputs["respondent_collection"]
        rows = collection.get("rows", collection) if isinstance(collection, dict) else collection
        col = config["column"]
        op = config["operator"]
        val = config["value"]

        ops = {
            "eq": lambda r, v: str(r.get(col, "")) == str(v),
            "neq": lambda r, v: str(r.get(col, "")) != str(v),
            "gt": lambda r, v: float(r.get(col, 0)) > float(v),
            "lt": lambda r, v: float(r.get(col, 0)) < float(v),
            "gte": lambda r, v: float(r.get(col, 0)) >= float(v),
            "lte": lambda r, v: float(r.get(col, 0)) <= float(v),
            "contains": lambda r, v: str(v) in str(r.get(col, "")),
        }

        filtered = [r for r in rows if ops[op](r, val)]
        return {"respondent_collection": {"rows": filtered}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "column": "age",
                "operator": "gte",
                "value": 28,
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {"name": "Alice", "age": "30", "city": "NYC"},
                        {"name": "Bob", "age": "25", "city": "LA"},
                        {"name": "Carol", "age": "35", "city": "Chicago"},
                    ],
                },
            },
            "expected_output": {
                "respondent_collection": {
                    "rows": [
                        {"name": "Alice", "age": "30", "city": "NYC"},
                        {"name": "Carol", "age": "35", "city": "Chicago"},
                    ],
                },
            },
        }
