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
        return (
            "Filters rows from a respondent_collection based on a column condition "
            "using comparison operators (equals, not equals, greater than, less than, "
            "contains). Use when you need to subset respondents by demographic, behavioral, "
            "or attitudinal criteria before downstream analysis or segmentation."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Operates on respondent_collection data type with row-level filtering. "
            "All comparison operators cast column values to strings for equality checks "
            "(eq, neq, contains) and to floats for numeric comparisons (gt, lt, gte, lte). "
            "This means numeric filters will fail on non-numeric data — consider upstream "
            "data cleaning or recoding if columns have mixed types. Missing values are "
            "treated as empty strings or zero, which may produce unexpected results.\n\n"
            "Filters are applied row-wise; this block does not support aggregation, "
            "grouping, or multi-column conditions. For complex filtering logic involving "
            "AND/OR conditions across multiple columns, chain multiple filter_transform "
            "blocks in series. For conditional routing rather than row subsetting, "
            "consider using a Router block instead."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "data-preparation",
            "row-filtering",
            "subsetting",
            "respondent-collection",
            "deterministic",
        ]

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
