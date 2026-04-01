"""Latent Class Analysis (LCA) segmentation — probabilistic clustering for categorical/mixed data."""

from typing import Any

import numpy as np
from sklearn.preprocessing import LabelEncoder

from blocks.base import AnalysisBase

try:
    from stepmix import StepMix
except ImportError:
    StepMix = None  # type: ignore


class LCAAnalysis(AnalysisBase):
    """Segments respondents using Latent Class Analysis.

    LCA is a probabilistic model that discovers unobserved subpopulations
    (latent classes) based on observed categorical or mixed features. Unlike
    K-Means, LCA handles categorical data natively and provides posterior
    probabilities of class membership for each respondent.
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
                "n_classes": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 20,
                    "description": "Number of latent classes to discover",
                },
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Column names to use as segmentation features",
                },
                "max_iter": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 100,
                    "description": "Maximum number of EM iterations",
                },
                "random_state": {
                    "type": "integer",
                    "default": 42,
                    "description": "Random seed for reproducibility",
                },
            },
            "required": ["n_classes", "features"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return (
            "Discovers latent segments in categorical or mixed data using "
            "Latent Class Analysis (LCA). LCA is a probabilistic model that "
            "identifies unobserved subpopulations based on observed response "
            "patterns. Unlike K-Means, LCA handles categorical features natively "
            "and provides posterior membership probabilities. Use when segmenting "
            "survey respondents based on categorical responses (e.g., agreement "
            "scales, brand choices, attribute selections) or mixed categorical/numeric "
            "data where probabilistic segment assignment is needed."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "ASSUMPTIONS: LCA assumes local independence — conditional on class "
            "membership, observed features are independent. The model assumes a "
            "finite number of latent classes generate the observed data patterns. "
            "For categorical features, LCA uses multinomial distributions within "
            "each class. For numeric features (mixed data), Gaussian distributions "
            "are used. The EM algorithm converges to a local maximum; different "
            "initializations may produce different solutions.\n\n"
            "DATA REQUIREMENTS: Designed primarily for categorical features "
            "(nominal or ordinal). Handles mixed data by combining categorical and "
            "Gaussian emissions. Numeric features should be approximately normally "
            "distributed within classes. Requires n_rows > n_classes for stable "
            "estimation. Categorical features are automatically label-encoded "
            "before fitting. Features with low variance or rare categories may cause "
            "estimation issues.\n\n"
            "LIMITATIONS: Local independence assumption may be violated in practice "
            "(correlated features within classes can bias results). No built-in "
            "model selection — you must specify n_classes a priori or evaluate "
            "multiple values using BIC/AIC downstream. Sensitive to starting "
            "values; multiple random restarts are recommended for stability. "
            "Computationally intensive for large datasets or many features compared "
            "to K-Means. Interpretation requires examining class-conditional "
            "response probabilities.\n\n"
            "ALTERNATIVES: Use K-Means (segmentation_kmeans) when all features are "
            "numeric and clusters are expected to be spherical. Use RFM (rfm_analysis) "
            "for transaction-based customer value segmentation. Use hierarchical "
            "clustering when you need a dendrogram or want to explore cluster "
            "structure at multiple granularity levels. Consider Multiple Correspondence "
            "Analysis (MCA) + K-Means as a dimensional-reduction alternative for "
            "purely categorical data."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "clustering",
            "segmentation",
            "unsupervised",
            "categorical-features",
            "mixed-data",
            "probabilistic",
        ]

    @property
    def dimensions(self) -> dict[str, str]:
        # Dimensions from reasoning-layer.md method classification table
        return {
            "exploratory_confirmatory": "mixed",
            "assumption_weight": "high",
            "output_interpretability": "high",
            "sample_sensitivity": "high",
            "reproducibility": "medium",
            "data_structure_affinity": "categorical",
        }

    @property
    def practitioner_workflow(self) -> str | None:
        return "segmentation.md"

    def validate_config(self, config: dict) -> bool:
        if not isinstance(config.get("n_classes"), int):
            return False
        if not (2 <= config["n_classes"] <= 20):
            return False
        features = config.get("features")
        if not isinstance(features, list) or len(features) < 1:
            return False
        if not all(isinstance(f, str) for f in features):
            return False
        max_iter = config.get("max_iter", 100)
        if not isinstance(max_iter, int) or max_iter < 1:
            return False
        return "random_state" not in config or isinstance(config["random_state"], int)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        if StepMix is None:
            raise ImportError("stepmix library is not installed. Run: uv add stepmix")

        rows = inputs["respondent_collection"]["rows"]
        n_classes = config["n_classes"]
        feature_names = config["features"]
        max_iter = config.get("max_iter", 100)
        random_state = config.get("random_state", 42)

        n_rows = len(rows)

        # Validate: all feature columns must exist (check before n_classes)
        first_row = rows[0]
        for col in feature_names:
            if col not in first_row:
                raise ValueError(f"Feature column '{col}' not found in input data")

        # Validate: n_classes must be less than number of rows
        if n_classes >= n_rows:
            raise ValueError(
                f"n_classes ({n_classes}) must be less than the number of input rows ({n_rows})"
            )

        # Determine feature types and prepare data
        categorical_features: list[str] = []
        numeric_features: list[str] = []
        feature_data: dict[str, list[Any]] = {feat: [] for feat in feature_names}
        original_values: dict[str, list[Any]] = {feat: [] for feat in feature_names}
        label_encoders: dict[str, LabelEncoder] = {}

        # First pass: determine types
        for feat in feature_names:
            value = first_row[feat]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric_features.append(feat)
            else:
                categorical_features.append(feat)
                label_encoders[feat] = LabelEncoder()

        # Second pass: collect and encode data
        for row in rows:
            for feat in feature_names:
                original_values[feat].append(row[feat])
                if feat in categorical_features:
                    # Label encode categorical features
                    feature_data[feat].append(row[feat])
                else:
                    # Numeric features as-is
                    feature_data[feat].append(float(row[feat]))

        # Build the data matrix for stepmix
        # stepmix expects a 2D array with encoded categorical features
        data_matrix = []
        for i in range(n_rows):
            row_data = []
            for feat in feature_names:
                if feat in categorical_features:
                    row_data.append(feature_data[feat][i])
                else:
                    row_data.append(feature_data[feat][i])
            data_matrix.append(row_data)

        X = np.array(data_matrix)

        # Encode categorical features to integers
        for feat in categorical_features:
            # Get the column index
            col_idx = feature_names.index(feat)
            # Extract the column
            col_data = X[:, col_idx]
            # Fit and transform the label encoder
            encoded = label_encoders[feat].fit_transform(col_data)
            X[:, col_idx] = encoded

        # Build measurement model specification for stepmix
        # For mixed data, we need to specify which columns are categorical vs numeric
        if categorical_features and not numeric_features:
            # All categorical
            measurement = "categorical"
        elif numeric_features and not categorical_features:
            # All numeric
            measurement = "gaussian"
        else:
            # Mixed: build a dict specification
            # stepmix uses nested dict format: {model: "type", n_columns: count}
            measurement = {}
            current_type = None
            current_count = 0

            for feat in feature_names:
                feat_type = "categorical" if feat in categorical_features else "gaussian"
                if current_type is None:
                    current_type = feat_type
                    current_count = 1
                elif current_type == feat_type:
                    current_count += 1
                else:
                    # Type changed, add previous segment
                    measurement[f"col_{len(measurement)}"] = {
                        "model": current_type,
                        "n_columns": current_count,
                    }
                    current_type = feat_type
                    current_count = 1

            # Add the last segment
            if current_type is not None:
                measurement[f"col_{len(measurement)}"] = {
                    "model": current_type,
                    "n_columns": current_count,
                }

        # Create and fit the model
        model = StepMix(
            n_components=n_classes,
            measurement=measurement,
            max_iter=max_iter,
            random_state=random_state,
            n_init=1,
        )

        model.fit(X)

        # Get class assignments
        labels = model.predict(X)

        # Build segment profiles
        segments: list[dict[str, Any]] = []

        for class_id in range(n_classes):
            member_indices = [int(i) for i, label in enumerate(labels) if label == class_id]
            size = len(member_indices)
            percentage = round(size / n_rows * 100, 2)

            # Class-conditional profile
            profile: dict[str, Any] = {}
            for feat in feature_names:
                if feat in categorical_features:
                    # For categorical: compute distribution
                    feat_values = [original_values[feat][i] for i in member_indices]
                    unique_vals = set(feat_values)
                    profile[feat] = {
                        "type": "categorical",
                        "distribution": {v: feat_values.count(v) / size for v in unique_vals},
                    }
                else:
                    # For numeric: compute mean and std
                    feat_values = [float(original_values[feat][i]) for i in member_indices]
                    profile[feat] = {
                        "type": "numeric",
                        "mean": round(np.mean(feat_values), 4),
                        "std": round(np.std(feat_values), 4),
                    }

            segments.append(
                {
                    "segment_id": class_id,
                    "size": size,
                    "percentage": percentage,
                    "profile": profile,
                    "member_indices": member_indices,
                }
            )

        return {"segment_profile_set": {"segments": segments}}

    def test_fixtures(self) -> dict:
        return {
            "config": {
                "n_classes": 2,
                "features": ["brand_choice", "satisfaction", "age"],
                "max_iter": 100,
                "random_state": 42,
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {
                            "respondent_id": "r1",
                            "brand_choice": "A",
                            "satisfaction": "high",
                            "age": 25,
                        },
                        {
                            "respondent_id": "r2",
                            "brand_choice": "A",
                            "satisfaction": "high",
                            "age": 28,
                        },
                        {
                            "respondent_id": "r3",
                            "brand_choice": "B",
                            "satisfaction": "low",
                            "age": 55,
                        },
                        {
                            "respondent_id": "r4",
                            "brand_choice": "B",
                            "satisfaction": "low",
                            "age": 60,
                        },
                        {
                            "respondent_id": "r5",
                            "brand_choice": "A",
                            "satisfaction": "medium",
                            "age": 30,
                        },
                        {
                            "respondent_id": "r6",
                            "brand_choice": "B",
                            "satisfaction": "medium",
                            "age": 58,
                        },
                    ],
                },
            },
            "expected_output": None,  # Placeholder -- probabilistic output verified in tests
        }
