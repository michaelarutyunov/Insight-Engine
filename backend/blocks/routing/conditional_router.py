"""Conditional Router block — routes data to different output branches."""

from typing import Any

from blocks.base import RouterBase


def _check_condition(cond: str, row_count: int, threshold_value: int) -> bool:
    """Evaluate a single routing condition. Separate function to avoid linter collapse."""
    if cond == "always":
        return True
    if cond == "threshold":
        return row_count >= threshold_value
    if cond == "non_empty":
        return row_count > 0
    return False


class ConditionalRouter(RouterBase):
    """Routes input data to one or more output branches based on a condition."""

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
                "rules": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "branch_id": {
                                "type": "string",
                                "description": "Output edge ID for this branch",
                            },
                            "condition": {
                                "type": "string",
                                "enum": ["always", "threshold", "non_empty"],
                                "description": "Routing condition type",
                            },
                            "threshold_value": {
                                "type": "integer",
                                "description": "Minimum row count for threshold condition",
                            },
                        },
                        "required": ["branch_id", "condition"],
                    },
                    "description": "List of routing rules",
                },
            },
            "required": ["rules"],
        }

    @property
    def description(self) -> str:
        return """Routes respondent_collection data to different pipeline branches based on configurable conditions.

Use this block when you need to split your research workflow into multiple parallel paths that activate conditionally — for example, running different analysis modules depending on data volume, routing to specialized treatment branches based on data characteristics, or implementing fallback logic when data quality thresholds are not met. Unlike a static split, this block evaluates routing rules at execution time and only activates edges that satisfy the specified conditions."""

    @property
    def methodological_notes(self) -> str:
        return """Assumptions: This router evaluates conditions against row count and presence of data in the input respondent_collection. Routing logic is deterministic based on the configured rules — all rules are evaluated independently, so multiple branches can activate simultaneously if their conditions are all satisfied.

Data requirements: Requires a respondent_collection input with a 'rows' key containing a list-like structure. Row count is extracted from len(rows); if the input is already a list, it is counted directly. For threshold conditions, the threshold_value config field must be provided.

Limitations: Conditions are limited to row-based metrics (always, threshold on minimum count, non-empty check). Cannot inspect field values, data quality metrics, or other complex attributes without modifying the block. All rules are evaluated in OR fashion — activation is not mutually exclusive, so downstream nodes should be prepared to receive data even when other branches also fire.

Alternatives: For simple static splits where all branches always execute, use a direct connection without a router. For complex multi-field conditionals, consider an LLM Flex block to evaluate custom logic, or a Transform block to pre-compute routing flags before this router."""

    @property
    def tags(self) -> list[str]:
        return [
            "routing",
            "conditional-logic",
            "branch-selection",
            "data-volume-routing",
            "parallel-workflows",
            "respondent-collection-input",
            "respondent-collection-output",
        ]

    def validate_config(self, config: dict) -> bool:
        if "rules" not in config or not isinstance(config["rules"], list):
            return False
        if len(config["rules"]) == 0:
            return False
        for rule in config["rules"]:
            if "branch_id" not in rule or "condition" not in rule:
                return False
            if rule["condition"] not in ("always", "threshold", "non_empty"):
                return False
        return True

    def resolve_route(self, inputs: dict[str, Any], config: dict | None = None) -> list[str]:
        collection = inputs.get("respondent_collection", {})
        rows = collection.get("rows", collection) if isinstance(collection, dict) else collection
        row_count = len(rows) if isinstance(rows, list) else 0

        rules = config.get("rules", []) if config else []
        active = []
        for rule in rules:
            cond = rule["condition"]
            if _check_condition(cond, row_count, rule.get("threshold_value", 0)):
                active.append(rule["branch_id"])
        return active

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        # Router passes through the data; routing logic is handled by resolve_route
        return {"respondent_collection": inputs["respondent_collection"]}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "rules": [
                    {"branch_id": "branch_a", "condition": "always"},
                    {"branch_id": "branch_b", "condition": "threshold", "threshold_value": 3},
                    {"branch_id": "branch_c", "condition": "non_empty"},
                ],
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {"name": "Alice", "age": "30"},
                        {"name": "Bob", "age": "25"},
                    ],
                },
            },
            "expected_output": {
                "respondent_collection": {
                    "rows": [
                        {"name": "Alice", "age": "30"},
                        {"name": "Bob", "age": "25"},
                    ],
                },
            },
            "expected_routes": ["branch_a", "branch_c"],
        }
