"""CSV Loader block — loads respondent data from a CSV file."""

import csv
from pathlib import Path
from typing import Any

from blocks.base import SourceBase


class CSVLoader(SourceBase):
    """Entry point that reads a CSV file into a respondent_collection."""

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the CSV file to read",
                },
                "delimiter": {
                    "type": "string",
                    "default": ",",
                    "description": "Column delimiter character",
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding",
                },
                "has_header": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether the first row contains column names",
                },
            },
            "required": ["file_path"],
        }

    @property
    def description(self) -> str:
        return (
            "Loads tabular data from a CSV file. Each row becomes a record in a "
            "respondent_collection. Use as a pipeline entry point for survey data, "
            "customer records, or any tabular dataset."
        )

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("file_path"), str):
            return False
        if not config["file_path"].strip():
            return False
        delim = config.get("delimiter", ",")
        if not isinstance(delim, str) or len(delim) != 1:
            return False
        encoding = config.get("encoding", "utf-8")
        if not isinstance(encoding, str):
            return False
        has_header = config.get("has_header", True)
        return isinstance(has_header, bool)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        _ = inputs  # noqa: F841 — base contract requires inputs param
        file_path = Path(config["file_path"])
        delimiter = config.get("delimiter", ",")
        encoding = config.get("encoding", "utf-8")
        has_header = config.get("has_header", True)

        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        with file_path.open(encoding=encoding, newline="") as f:
            if has_header:
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)
            else:
                reader = csv.reader(f, delimiter=delimiter)
                raw_rows = list(reader)
                if not raw_rows:
                    rows = []
                else:
                    # Generate column names like col0, col1, col2...
                    num_cols = len(raw_rows[0])
                    fieldnames = [f"col{i}" for i in range(num_cols)]
                    rows = [dict(zip(fieldnames, row, strict=True)) for row in raw_rows]

        return {"respondent_collection": {"rows": rows}}

    def test_fixtures(self) -> dict:
        # For testing, callers should use tempfile to create a real CSV file
        # and pass its path. This fixture shows expected structure.
        return {
            "config": {
                "file_path": "/tmp/test_respondents.csv",
                "delimiter": ",",
                "encoding": "utf-8",
                "has_header": True,
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
            "setup_csv_content": "name,age,city\nAlice,30,NYC\nBob,25,LA",
        }
