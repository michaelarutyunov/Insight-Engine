"""K-Means segmentation transform -- clusters respondents into segments."""

from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from blocks.base import TransformBase


class KMeansTransform(TransformBase):
    """Segments respondents into clusters using K-Means.

    Requires numeric features. Output includes cluster assignments and
    centroid-based profiles for each segment.
    """

    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["segment_profile_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "n_clusters": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 20,
                    "description": "Number of clusters to form",
                },
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Column names to cluster on (must be numeric)",
                },
                "scaling": {
                    "type": "string",
                    "enum": ["standard", "minmax", "none"],
                    "default": "standard",
                    "description": "Feature scaling method",
                },
                "random_state": {
                    "type": "integer",
                    "default": 42,
                    "description": "Random seed for reproducibility",
                },
            },
            "required": ["n_clusters", "features"],
        }

    @property
    def description(self) -> str:
        return (
            "Segments respondents into clusters using K-Means. "
            "Requires numeric features. Output includes cluster assignments "
            "and centroid-based profiles for each segment."
        )

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("n_clusters"), int):
            return False
        if not (2 <= config["n_clusters"] <= 20):
            return False
        features = config.get("features")
        if not isinstance(features, list) or len(features) < 1:
            return False
        if not all(isinstance(f, str) for f in features):
            return False
        scaling = config.get("scaling", "standard")
        if scaling not in ("standard", "minmax", "none"):
            return False
        return "random_state" not in config or isinstance(config["random_state"], int)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        rows = inputs["respondent_collection"]["rows"]
        n_clusters = config["n_clusters"]
        feature_names = config["features"]
        scaling = config.get("scaling", "standard")
        random_state = config.get("random_state", 42)

        n_rows = len(rows)

        # Validate: n_clusters must be less than number of rows
        if n_clusters >= n_rows:
            raise ValueError(
                f"n_clusters ({n_clusters}) must be less than the number of input rows ({n_rows})"
            )

        # Validate: all feature columns must exist
        for col in feature_names:
            if col not in rows[0]:
                raise ValueError(f"Feature column '{col}' not found in input data")

        # Extract feature values into numpy array
        try:
            X = np.array([[float(row[col]) for col in feature_names] for row in rows])
        except (ValueError, TypeError) as e:
            raise ValueError(f"All feature columns must be numeric: {e}") from e
        # Apply scaling
        if scaling == "standard":
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
        elif scaling == "minmax":
            scaler = MinMaxScaler()
            X_scaled = scaler.fit_transform(X)
        else:
            X_scaled = X
        # Run KMeans
        kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init="auto")
        labels = kmeans.fit_predict(X_scaled)
        # Build segment profiles
        segments: list[dict[str, Any]] = []
        for segment_id in range(n_clusters):
            member_indices = [int(i) for i, label in enumerate(labels) if label == segment_id]
            size = len(member_indices)
            percentage = round(size / n_rows * 100, 2)
            # Centroid in original (unscaled) feature space
            centroid: dict[str, float] = {}
            if size > 0:
                for j, feat in enumerate(feature_names):
                    centroid[feat] = round(float(np.mean(X[member_indices, j])), 4)
            segments.append(
                {
                    "segment_id": segment_id,
                    "size": size,
                    "percentage": percentage,
                    "centroid": centroid,
                    "member_indices": member_indices,
                }
            )

        return {"segment_profile_set": {"segments": segments}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "n_clusters": 2,
                "features": ["age", "income"],
                "scaling": "standard",
                "random_state": 42,
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {"name": "Alice", "age": 25, "income": 30000},
                        {"name": "Bob", "age": 30, "income": 35000},
                        {"name": "Carol", "age": 55, "income": 90000},
                        {"name": "Dave", "age": 60, "income": 95000},
                        {"name": "Eve", "age": 28, "income": 32000},
                    ],
                },
            },
            "expected_output": None,  # Placeholder -- deterministic output verified in tests
        }
