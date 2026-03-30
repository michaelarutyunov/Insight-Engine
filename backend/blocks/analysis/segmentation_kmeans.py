"""K-Means segmentation analysis -- clusters respondents into segments."""

from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from blocks.base import AnalysisBase


class KMeansAnalysis(AnalysisBase):
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
            "Clusters respondents into segments using the K-Means algorithm. "
            "Use when you need a simple, interpretable segmentation of respondents "
            "based on numeric behavioral or attitudinal features. Produces segment "
            "profiles with centroid-based descriptions suitable for persona development "
            "or targeting strategies."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "ASSUMPTIONS: K-Means assumes spherical clusters of roughly equal size "
            "and variance. It minimizes within-cluster variance using Euclidean "
            "distance, which works best when clusters are compact and well-separated. "
            "The algorithm is deterministic only when random_state is fixed; "
            "different seeds may produce different segment assignments.\n\n"
            "DATA REQUIREMENTS: All features must be numeric (continuous or discrete). "
            "Categorical features must be encoded upstream using one-hot encoding, "
            "ordinal encoding, or embedding techniques. Missing values must be handled "
            "upstream via imputation or row removal. Feature scaling (standard or "
            "minmax) is strongly recommended—unscaled features with different units "
            "will distort distance calculations. The block requires n_rows >= n_clusters.\n\n"
            "LIMITATIONS: Sensitive to outliers—a single extreme respondent can "
            "substantially shift centroids. Does not automatically select the optimal "
            "number of clusters; you must specify n_clusters a priori or evaluate "
            "multiple k values downstream. Struggles with non-spherical cluster shapes "
            "(e.g., crescents, concentric circles) or clusters with highly unequal "
            "sizes or densities. May produce empty clusters if initialization is poor.\n\n"
            "ALTERNATIVES: Use LCA (segmentation_lca) when features are categorical, "
            "mixed numeric/categorical, or when probabilistic segment membership is "
            "needed. Use RFM (rfm_analysis) for transaction-based customer value "
            "segmentation where the framework is predetermined. Consider hierarchical "
            "clustering or DBSCAN when cluster shapes are non-spherical or when you "
            "don't want to specify k in advance."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "clustering",
            "segmentation",
            "unsupervised",
            "numeric-features",
            "requires-scaling",
        ]

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
