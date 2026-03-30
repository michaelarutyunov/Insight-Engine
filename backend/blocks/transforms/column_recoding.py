"""Column Recoding Transform — value mapping and numeric binning."""

from typing import Any

from blocks.base import TransformBase


class ColumnRecoding(TransformBase):
    """Deterministic transform that recodes column values via mapping or binning.

    Supports two recoding modes per column:
      - ``map``: replace values according to a literal mapping dict.
      - ``bin``: assign labels based on inclusive numeric ranges
        (``min <= value < max``; the last bin in the list also includes
        the upper bound so the maximum value is not orphaned).

    Columns are overwritten in-place unless ``output_column`` is specified
    for a recoding entry, in which case the recoded result is written to a
    new column leaving the original untouched.
    """

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
                "recodings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {
                                "type": "string",
                                "description": "Source column to recode",
                            },
                            "type": {
                                "type": "string",
                                "enum": ["map", "bin"],
                                "description": "Recoding mode: 'map' for value mapping, 'bin' for numeric binning",
                            },
                            "mapping": {
                                "type": "object",
                                "description": "For 'map' mode: old value to new value pairs",
                            },
                            "bins": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "min": {
                                            "type": "number",
                                            "description": "Inclusive lower bound of the bin",
                                        },
                                        "max": {
                                            "type": "number",
                                            "description": "Exclusive upper bound (inclusive for the last bin)",
                                        },
                                        "label": {
                                            "type": "string",
                                            "description": "Label assigned to values in this range",
                                        },
                                    },
                                    "required": ["min", "max", "label"],
                                },
                                "description": "For 'bin' mode: list of {min, max, label} range definitions",
                            },
                            "output_column": {
                                "type": "string",
                                "description": "Optional target column name; defaults to overwriting the source column",
                            },
                        },
                        "required": ["column", "type"],
                    },
                    "minItems": 1,
                    "description": "List of recoding specifications to apply sequentially",
                },
            },
            "required": ["recodings"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return (
            "Recodes column values in a respondent_collection using either "
            "value mapping (replace specific values with new ones) or numeric "
            "binning (group continuous values into labeled ranges). Useful for "
            "standardizing coded responses, collapsing categories, or creating "
            "grouped variables from continuous data before segmentation or analysis."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Applies recodings sequentially in the order specified. Each recoding "
            "operates independently on the original column value — recodings do not "
            "cascade (a value mapped in the first recoding is not visible to later "
            "recodings of the same column unless output_column differs).\n\n"
            "For 'map' mode, values not present in the mapping dict are left unchanged. "
            "For 'bin' mode, a value is assigned to the first bin whose range it falls "
            "into (min <= value < max, with the last bin also including max). Values "
            "that match no bin are left unchanged.\n\n"
            "Binning is inclusive-lower / exclusive-upper except for the final bin "
            "which is inclusive on both ends, ensuring the maximum value is captured. "
            "Non-numeric values in a binned column will cause that row's value to be "
            "left unchanged (no error raised)."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "data-preparation",
            "recoding",
            "value-mapping",
            "binning",
            "respondent-collection",
            "deterministic",
        ]

    def validate_config(self, config: dict) -> bool:
        if "recodings" not in config or not isinstance(config["recodings"], list):
            return False
        if len(config["recodings"]) == 0:
            return False
        for recode in config["recodings"]:
            if not isinstance(recode, dict):
                return False
            if "column" not in recode or not isinstance(recode["column"], str):
                return False
            if recode.get("type") not in ("map", "bin"):
                return False
            if recode["type"] == "map" and "mapping" not in recode:
                return False
            if recode["type"] == "bin":
                bins = recode.get("bins")
                if not isinstance(bins, list) or len(bins) == 0:
                    return False
                for b in bins:
                    if not isinstance(b, dict):
                        return False
                    if "min" not in b or "max" not in b or "label" not in b:
                        return False
                    if not isinstance(b["label"], str):
                        return False
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        collection = inputs["respondent_collection"]
        rows = collection.get("rows", collection) if isinstance(collection, dict) else collection

        # Deep-copy rows so the original is not mutated
        result_rows = [dict(row) for row in rows]

        for recode in config["recodings"]:
            col = recode["column"]
            target_col = recode.get("output_column", col)
            mode = recode["type"]

            if mode == "map":
                mapping = recode["mapping"]
                for row in result_rows:
                    if col in row:
                        val = row[col]
                        # Use string key lookup for robustness — JSON keys are always strings
                        key = str(val) if not isinstance(val, str) else val
                        if key in mapping:
                            row[target_col] = mapping[key]
                        elif val in mapping:
                            row[target_col] = mapping[val]
                        # If neither key nor val is in mapping, leave value unchanged

            elif mode == "bin":
                bins = recode["bins"]
                last_idx = len(bins) - 1
                for row in result_rows:
                    if col not in row:
                        continue
                    raw = row[col]
                    try:
                        val = float(raw)
                    except (TypeError, ValueError):
                        continue
                    for i, b in enumerate(bins):
                        lo = b["min"]
                        hi = b["max"]
                        # Last bin is inclusive on both ends
                        if i == last_idx:
                            if lo <= val <= hi:
                                row[target_col] = b["label"]
                                break
                        else:
                            if lo <= val < hi:
                                row[target_col] = b["label"]
                                break

        return {"respondent_collection": {"rows": result_rows}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "recodings": [
                    {
                        "column": "education",
                        "type": "map",
                        "mapping": {
                            "HS": "High School",
                            "BA": "Bachelor",
                            "MA": "Master",
                            "PhD": "Doctorate",
                        },
                    },
                    {
                        "column": "age",
                        "type": "bin",
                        "bins": [
                            {"min": 0, "max": 25, "label": "Under 25"},
                            {"min": 25, "max": 40, "label": "25-39"},
                            {"min": 40, "max": 60, "label": "40-59"},
                            {"min": 60, "max": 120, "label": "60+"},
                        ],
                        "output_column": "age_group",
                    },
                ],
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {"name": "Alice", "age": 30, "education": "MA"},
                        {"name": "Bob", "age": 22, "education": "HS"},
                        {"name": "Carol", "age": 55, "education": "PhD"},
                        {"name": "Dave", "age": 65, "education": "BA"},
                        {"name": "Eve", "age": 40, "education": "Other"},
                    ],
                },
            },
            "expected_output": {
                "respondent_collection": {
                    "rows": [
                        {"name": "Alice", "age": 30, "education": "Master", "age_group": "25-39"},
                        {
                            "name": "Bob",
                            "age": 22,
                            "education": "High School",
                            "age_group": "Under 25",
                        },
                        {
                            "name": "Carol",
                            "age": 55,
                            "education": "Doctorate",
                            "age_group": "40-59",
                        },
                        {"name": "Dave", "age": 65, "education": "Bachelor", "age_group": "60+"},
                        {"name": "Eve", "age": 40, "education": "Other", "age_group": "40-59"},
                    ],
                },
            },
        }
