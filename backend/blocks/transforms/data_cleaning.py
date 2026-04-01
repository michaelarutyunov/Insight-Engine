"""Data Cleaning Transform block — configurable missing value handling and outlier treatment."""

import statistics
from copy import deepcopy
from typing import Any

from blocks.base import TransformBase


class DataCleaning(TransformBase):
    """Deterministic transform that cleans respondent_collection data.

    Handles missing values (drop rows or impute) and outlier treatment
    (z-score or IQR capping). Both operations are optional — the block
    can do only missing-value handling, only outlier treatment, or both.
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
                "missing_strategy": {
                    "type": "string",
                    "enum": ["drop", "impute"],
                    "description": "How to handle missing values: drop rows or impute them",
                },
                "impute_method": {
                    "type": "string",
                    "enum": ["mean", "median", "mode", "constant"],
                    "description": (
                        "Imputation method when missing_strategy is 'impute'. "
                        "'constant' uses the value from impute_value."
                    ),
                },
                "impute_value": {
                    "description": (
                        "Fill value when impute_method is 'constant'. "
                        "Can be any type (number, string, etc.)."
                    ),
                },
                "outlier_method": {
                    "type": "string",
                    "enum": ["zscore", "iqr", "none"],
                    "description": (
                        "Outlier detection method. 'zscore' uses standard deviations, "
                        "'iqr' uses interquartile range. 'none' skips outlier treatment."
                    ),
                },
                "outlier_threshold": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": (
                        "Threshold for outlier detection. For zscore: number of standard "
                        "deviations (default 3.0). For iqr: multiplier for IQR (default 1.5)."
                    ),
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Column names to clean. If omitted, all numeric columns are used."
                    ),
                },
            },
            "required": ["missing_strategy"],
        }

    @property
    def description(self) -> str:
        return (
            "Cleans respondent_collection data with configurable missing value handling "
            "and outlier treatment. Missing values can be handled by dropping rows or "
            "imputing with mean, median, mode, or a constant value. Outliers can be "
            "detected using z-score or IQR methods and capped at the boundary values. "
            "Operations can target specific columns or apply to all numeric columns."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Missing value handling: 'drop' removes any row containing a missing (None) "
            "value in the target columns. 'impute' fills missing values using the selected "
            "method. Mean and median imputation only apply to numeric columns; mode "
            "imputation works for any column type. Constant imputation uses the provided "
            "value regardless of column type.\n\n"
            "Outlier treatment: Detected outliers are capped (Winsorized) to the boundary "
            "value rather than removed. Z-score method caps values beyond N standard "
            "deviations from the mean. IQR method caps values beyond Q1 - threshold*IQR "
            "and Q3 + threshold*IQR. Outlier treatment is applied after missing value "
            "handling to ensure accurate statistics.\n\n"
            "Both operations are deterministic: the same input and config always produce "
            "the same output. Non-numeric columns are silently skipped during outlier "
            "treatment. For complex cleaning logic across multiple passes, chain multiple "
            "data_cleaning blocks in series."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "data-preparation",
            "cleaning",
            "missing-values",
            "imputation",
            "outliers",
            "respondent-collection",
            "deterministic",
        ]

    def validate_config(self, config: dict) -> bool:
        if "missing_strategy" not in config:
            return False
        if config["missing_strategy"] not in ("drop", "impute"):
            return False
        if config["missing_strategy"] == "impute":
            method = config.get("impute_method")
            if method not in ("mean", "median", "mode", "constant"):
                return False
            if method == "constant" and "impute_value" not in config:
                return False
        outlier_method = config.get("outlier_method", "none")
        if outlier_method not in ("zscore", "iqr", "none"):
            return False
        threshold = config.get("outlier_threshold", 3.0)
        if not isinstance(threshold, (int, float)) or threshold <= 0:
            return False
        columns = config.get("columns")
        if columns is not None and (
            not isinstance(columns, list) or not all(isinstance(c, str) for c in columns)
        ):
            return False
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        collection = inputs["respondent_collection"]
        rows = (
            deepcopy(collection.get("rows", []))
            if isinstance(collection, dict)
            else deepcopy(collection)
        )

        target_cols = self._resolve_target_columns(rows, config.get("columns"))

        # Phase 1: Missing value handling
        rows = self._handle_missing(rows, target_cols, config)

        # Phase 2: Outlier treatment (after missing values are resolved)
        outlier_method = config.get("outlier_method", "none")
        if outlier_method != "none":
            threshold = config.get("outlier_threshold", 3.0)
            rows = self._handle_outliers(rows, target_cols, outlier_method, threshold)

        return {"respondent_collection": {"rows": rows}}

    def _resolve_target_columns(self, rows: list[dict], columns: list[str] | None) -> list[str]:
        if columns:
            return columns
        # Auto-detect numeric columns from all rows
        numeric_cols: set[str] = set()
        for row in rows:
            for key, val in row.items():
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    numeric_cols.add(key)
        return sorted(numeric_cols)

    def _handle_missing(self, rows: list[dict], target_cols: list[str], config: dict) -> list[dict]:
        strategy = config["missing_strategy"]

        if strategy == "drop":
            return [
                row
                for row in rows
                if not any(row.get(col) is None for col in target_cols if col in row)
            ]

        # Impute
        method = config.get("impute_method", "mean")
        fill_values = self._compute_fill_values(rows, target_cols, method, config)
        for row in rows:
            for col in target_cols:
                if col in row and row[col] is None:
                    row[col] = fill_values.get(col)
        return rows

    def _compute_fill_values(
        self, rows: list[dict], target_cols: list[str], method: str, config: dict
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for col in target_cols:
            values = [row[col] for row in rows if col in row and row[col] is not None]
            if method == "constant":
                result[col] = config["impute_value"]
            elif method == "mean":
                numeric = [
                    v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)
                ]
                result[col] = statistics.mean(numeric) if numeric else None
            elif method == "median":
                numeric = [
                    v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)
                ]
                result[col] = statistics.median(numeric) if numeric else None
            elif method == "mode":
                if values:
                    try:
                        result[col] = statistics.mode(values)
                    except statistics.StatisticsError:
                        # Multiple modes — pick the first encountered
                        result[col] = values[0]
                else:
                    result[col] = None
        return result

    def _handle_outliers(
        self,
        rows: list[dict],
        target_cols: list[str],
        method: str,
        threshold: float,
    ) -> list[dict]:
        for col in target_cols:
            numeric = [
                row[col]
                for row in rows
                if col in row
                and isinstance(row[col], (int, float))
                and not isinstance(row[col], bool)
            ]
            if len(numeric) < 2:
                continue

            if method == "zscore":
                low, high = self._zscore_bounds(numeric, threshold)
            else:  # iqr
                low, high = self._iqr_bounds(numeric, threshold)

            for row in rows:
                if (
                    col in row
                    and isinstance(row[col], (int, float))
                    and not isinstance(row[col], bool)
                ):
                    if row[col] < low:
                        row[col] = low
                    elif row[col] > high:
                        row[col] = high
        return rows

    @staticmethod
    def _zscore_bounds(values: list[float], threshold: float) -> tuple[float, float]:
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev == 0:
            return (mean, mean)
        low = mean - threshold * stdev
        high = mean + threshold * stdev
        return (low, high)

    @staticmethod
    def _iqr_bounds(values: list[float], threshold: float) -> tuple[float, float]:
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = sorted_vals[q1_idx]
        q3 = sorted_vals[q3_idx]
        iqr = q3 - q1
        low = q1 - threshold * iqr
        high = q3 + threshold * iqr
        return (low, high)

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "missing_strategy": "impute",
                "impute_method": "mean",
                "outlier_method": "zscore",
                "outlier_threshold": 2.0,
                "columns": ["age", "income"],
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {"id": 1, "age": 25, "income": 50000},
                        {"id": 2, "age": None, "income": 60000},
                        {"id": 3, "age": 35, "income": None},
                        {"id": 4, "age": 30, "income": 200000},
                        {"id": 5, "age": 28, "income": 55000},
                    ],
                },
            },
            "expected_output": {
                "respondent_collection": {
                    "rows": [
                        {"id": 1, "age": 25, "income": 50000},
                        {"id": 2, "age": 29.5, "income": 60000},
                        {"id": 3, "age": 35, "income": 66250.0},
                        {"id": 4, "age": 30, "income": 200000},
                        {"id": 5, "age": 28, "income": 55000},
                    ],
                },
            },
        }
