"""CSV Source block — loads respondent data from a CSV string."""

import csv
import io
from typing import Any

from blocks.base import SourceBase


class CSVSource(SourceBase):
    """Entry point that parses a CSV string into a respondent_collection."""

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "csv_data": {
                    "type": "string",
                    "description": "Raw CSV content to parse",
                },
                "delimiter": {
                    "type": "string",
                    "default": ",",
                    "description": "Column delimiter character",
                },
            },
            "required": ["csv_data"],
        }

    @property
    def description(self) -> str:
        return "Parses a CSV string into a respondent_collection for downstream processing."

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("csv_data"), str):
            return False
        if not config["csv_data"].strip():
            return False
        delim = config.get("delimiter", ",")
        return isinstance(delim, str) and len(delim) == 1

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        _ = inputs  # noqa: F841 — base contract requires inputs param
        reader = csv.DictReader(
            io.StringIO(config["csv_data"]),
            delimiter=config.get("delimiter", ","),
        )
        rows = [row for row in reader]
        return {"respondent_collection": {"rows": rows}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "csv_data": "name,age,city\nAlice,30,NYC\nBob,25,LA",
                "delimiter": ",",
            },
            "inputs": {},
            "expected_output": {
                "respondent_collection": {
                    "rows": [
                        {"name": "Alice", "age": "30", "city": "NYC"},
                        {"name": "Bob", "age": "25", "city": "LA"},
                    ],
                },
            },
        }
