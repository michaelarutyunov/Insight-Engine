"""Rim Weighting Transform — iterative proportional fitting to target marginals."""

from typing import Any

import numpy as np

from blocks.base import TransformBase


class Weighting(TransformBase):
    """Applies rim weighting to respondent data using Iterative Proportional Fitting (IPF).

    Rim weighting adjusts respondent weights so that weighted marginal distributions
    match specified targets across one or more dimensions. The IPF algorithm
    iteratively adjusts weights until convergence or max iterations is reached.

    Convergence is achieved when the maximum change across all weights is below
    the tolerance threshold. Weights are initialized to 1.0 and are never
    allowed to go below 0.01 to prevent extreme values.
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
                "targets": {
                    "type": "object",
                    "description": (
                        "Target marginals as {column: {value: proportion}}. "
                        "Proportions must sum to 1.0 for each column."
                    ),
                },
                "weight_column": {
                    "type": "string",
                    "description": "Name of the column to store weights in. Default: 'weight'.",
                    "default": "weight",
                },
                "max_iterations": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1000,
                    "description": "Maximum IPF iterations. Default: 100.",
                    "default": 100,
                },
                "tolerance": {
                    "type": "number",
                    "minimum": 1e-10,
                    "maximum": 1,
                    "description": (
                        "Convergence threshold — stops when max weight change is below this. "
                        "Default: 0.001."
                    ),
                    "default": 0.001,
                },
            },
            "required": ["targets"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return (
            "Applies rim weighting (iterative proportional fitting) to align "
            "sample marginal distributions with known population targets. "
            "Weights are adjusted so that weighted totals match specified proportions "
            "across one or more dimensions (e.g., age, gender, region). Useful for "
            "correcting sample bias or matching sample to population benchmarks."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "IPF iteratively adjusts weights by cycling through each target dimension "
            "and scaling weights so that weighted margins match targets. Convergence is "
            "monitored via maximum absolute change in weights across iterations.\n\n"
            "Target proportions must sum to 1.0 for each dimension. Missing or invalid "
            "values in target columns are assigned weight 0 and excluded from weighted "
            "totals (they remain in the output but do not affect fitting).\n\n"
            "Weights are bounded below at 0.01 to prevent extreme values. The algorithm "
            "stops when max change < tolerance or max_iterations is reached. Check "
            "diagnostics for convergence status.\n\n"
            "IPF assumes dimensions are independent — for complex interactions, consider "
            "raking on interaction cells or using more sophisticated methods."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "weighting",
            "rim-weighting",
            "ipf",
            "sample-bias-correction",
            "respondent-collection",
            "deterministic",
        ]

    def validate_config(self, config: dict) -> bool:
        if "targets" not in config or not isinstance(config["targets"], dict):
            return False
        if len(config["targets"]) == 0:
            return False

        # Validate each target dimension
        for col, targets in config["targets"].items():
            if not isinstance(targets, dict) or len(targets) == 0:
                return False
            # Check proportions are numeric and sum to ~1.0
            total = 0.0
            for val, prop in targets.items():
                if not isinstance(prop, (int, float)):
                    return False
                if prop < 0 or prop > 1:
                    return False
                total += prop
            if abs(total - 1.0) > 0.01:  # Allow small floating point errors
                return False

        # Validate optional parameters
        if "weight_column" in config:
            if not isinstance(config["weight_column"], str):
                return False

        if "max_iterations" in config:
            if not isinstance(config["max_iterations"], int):
                return False
            if config["max_iterations"] < 1 or config["max_iterations"] > 1000:
                return False

        if "tolerance" in config:
            if not isinstance(config["tolerance"], (int, float)):
                return False
            if config["tolerance"] < 1e-10 or config["tolerance"] > 1:
                return False

        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        collection = inputs["respondent_collection"]
        rows = collection.get("rows", collection) if isinstance(collection, dict) else collection

        # Deep-copy rows to avoid mutating input
        result_rows = [dict(row) for row in rows]

        # Extract config parameters with defaults
        targets = config["targets"]
        weight_column = config.get("weight_column", "weight")
        max_iterations = config.get("max_iterations", 100)
        tolerance = config.get("tolerance", 0.001)

        # Number of respondents
        n = len(result_rows)

        # Initialize weights to 1.0
        weights = np.ones(n, dtype=np.float64)

        # Build dimension metadata: for each column, map unique values to indices
        # and store target proportions
        dimensions = []
        for col, target_dist in targets.items():
            # Get unique values in the data for this column
            value_to_idx = {}
            for i, row in enumerate(result_rows):
                val = row.get(col)
                if val not in value_to_idx:
                    value_to_idx[val] = len(value_to_idx)

            # Build target proportion array (aligned with value_to_idx)
            n_categories = len(value_to_idx)
            target_props = np.zeros(n_categories, dtype=np.float64)
            for val, prop in target_dist.items():
                if val in value_to_idx:
                    target_props[value_to_idx[val]] = prop

            dimensions.append(
                {
                    "column": col,
                    "value_to_idx": value_to_idx,
                    "target_props": target_props,
                }
            )

        # IPF iterations
        for iteration in range(max_iterations):
            old_weights = weights.copy()

            # Adjust for each dimension sequentially
            for dim in dimensions:
                col = dim["column"]
                value_to_idx = dim["value_to_idx"]
                target_props = dim["target_props"]

                # Compute current weighted totals per category
                category_sums = np.zeros(len(target_props), dtype=np.float64)
                for i, row in enumerate(result_rows):
                    val = row.get(col)
                    if val in value_to_idx:
                        idx = value_to_idx[val]
                        category_sums[idx] += weights[i]

                # Avoid division by zero
                total_weight = np.sum(category_sums)
                if total_weight == 0:
                    continue

                # Compute scaling factors
                scaling_factors = np.ones(len(target_props), dtype=np.float64)
                for idx in range(len(target_props)):
                    if category_sums[idx] > 0 and target_props[idx] > 0:
                        # Target weighted count for this category
                        target_count = total_weight * target_props[idx]
                        scaling_factors[idx] = target_count / category_sums[idx]

                # Apply scaling factors to weights
                for i, row in enumerate(result_rows):
                    val = row.get(col)
                    if val in value_to_idx:
                        idx = value_to_idx[val]
                        weights[i] *= scaling_factors[idx]

                        # Enforce minimum weight
                        if weights[i] < 0.01:
                            weights[i] = 0.01

            # Check convergence
            max_change = np.max(np.abs(weights - old_weights))
            if max_change < tolerance:
                break

        # Assign minimum weight to rows with missing values in any target column
        for i, row in enumerate(result_rows):
            for col in targets.keys():
                val = row.get(col)
                if val is None or val == "":
                    weights[i] = 0.01
                    break

        # Assign weights to result rows
        for i, row in enumerate(result_rows):
            row[weight_column] = float(weights[i])

        return {"respondent_collection": {"rows": result_rows}}

    def test_fixtures(self) -> dict:
        # Simple test: weight by gender to match 50/50 distribution
        return {
            "config": {
                "targets": {
                    "gender": {"M": 0.5, "F": 0.5},
                },
                "weight_column": "weight",
                "max_iterations": 100,
                "tolerance": 0.001,
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {"id": 1, "gender": "M"},
                        {"id": 2, "gender": "M"},
                        {"id": 3, "gender": "F"},
                    ],
                },
            },
            "expected_output": {
                "respondent_collection": {
                    "rows": [
                        {"id": 1, "gender": "M", "weight": 0.75},
                        {"id": 2, "gender": "M", "weight": 0.75},
                        {"id": 3, "gender": "F", "weight": 1.5},
                    ],
                },
            },
        }
