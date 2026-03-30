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
        return """Load structured respondent data from CSV format into your pipeline.

Use this block when you need to bring survey responses, customer records, or experimental data into an analysis pipeline. Ideal for tabular data exported from survey platforms, CRM systems, or spreadsheets where each row represents a respondent and columns represent variables."""

    @property
    def methodological_notes(self) -> str:
        return """Assumes standard CSV format (RFC 4180) with consistent row structure. Supports UTF-8 encoding and single-character delimiters (comma, tab, pipe, etc.). Empty rows are skipped by the csv.DictReader.

Memory considerations: The entire CSV is loaded into memory as a list of dictionaries. For files larger than available RAM, consider streaming alternatives or chunked processing approaches.

Alternatives: For nested or hierarchical data, consider JSON or XML sources. For database connectivity, use database query blocks. For real-time data ingestion, consider API polling blocks."""

    @property
    def tags(self) -> list[str]:
        return [
            "data-import",
            "csv",
            "tabular",
            "respondent-data",
            "survey-data",
            "structured-input",
        ]

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
