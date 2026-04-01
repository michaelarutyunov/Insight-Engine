"""RFM Analysis Block — customer value segmentation using Recency, Frequency, Monetary scoring."""

from datetime import datetime
from typing import Any

import numpy as np

from blocks.base import AnalysisBase


class RFMAnalysis(AnalysisBase):
    """Performs RFM (Recency, Frequency, Monetary) analysis to identify customer value segments.

    RFM analysis scores customers based on three behavioral dimensions:
    - Recency: How recently did they purchase? (More recent = better)
    - Frequency: How often do they purchase? (Higher = better)
    - Monetary: How much do they spend? (Higher = better)

    Each dimension is scored 1-5 (5 = best), and customers are segmented into
    value groups based on their combined RFM scores. This is a widely-used
    customer segmentation technique in direct marketing and e-commerce.
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
                "recency_col": {
                    "type": "string",
                    "description": "Column name containing recency data (date or days ago)",
                },
                "frequency_col": {
                    "type": "string",
                    "description": "Column name containing purchase frequency count",
                },
                "monetary_col": {
                    "type": "string",
                    "description": "Column name containing total monetary value",
                },
                "n_segments": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 10,
                    "default": 5,
                    "description": "Number of value segments to create",
                },
                "date_col": {
                    "type": "string",
                    "description": "Optional column with actual purchase dates (if recency_col is days ago)",
                },
                "customer_id_col": {
                    "type": "string",
                    "default": "id",
                    "description": "Column name containing customer ID",
                },
            },
            "required": ["recency_col", "frequency_col", "monetary_col"],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return (
            "Performs RFM (Recency, Frequency, Monetary) analysis to segment customers by value. "
            "Scores each customer on three dimensions (1-5 scale) and assigns to value segments. "
            "Use this block to identify high-value customers, at-risk customers, and growth opportunities. "
            "Widely used in direct marketing and customer lifecycle management."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "RFM analysis scores customers on three dimensions:\n"
            "- Recency (R): Days since last purchase (5=most recent, 1=least recent)\n"
            "- Frequency (F): Number of purchases (5=frequent, 1=infrequent)\n"
            "- Monetary (M): Total spend (5=high spend, 1=low spend)\n\n"
            "Scoring uses quintiles (5 groups) within the dataset for each dimension. "
            "Ties are broken by assigning higher scores to better values.\n\n"
            "Segment assignment uses the concatenated RFM score (e.g., '545' = R=5, F=4, M=5). "
            "Customers are grouped into n_segments based on their combined RFM scores using "
            "k-means clustering on the 3-dimensional score space.\n\n"
            "Input requirements: Each row represents a customer with recency, frequency, and "
            "monetary values. Missing values in these columns are scored as 1 (worst).\n\n"
            f"practitioner_workflow: '{self.practitioner_workflow}'"
        )

    @property
    def tags(self) -> list[str]:
        return [
            "analysis",
            "segmentation",
            "rfm",
            "customer-value",
            "marketing",
            "scoring",
            "quantiles",
            "clustering",
        ]

    @property
    def dimensions(self) -> dict[str, str]:
        """Return the 6-dimension characterization for this method."""
        return {
            "exploratory_confirmatory": "confirmatory",
            "assumption_weight": "medium",
            "output_interpretability": "high",
            "sample_sensitivity": "medium",
            "reproducibility": "high",
            "data_structure_affinity": "numeric_continuous",
        }

    def validate_config(self, config: dict) -> bool:
        """Validate configuration against schema requirements."""
        # Check required fields
        required_cols = ["recency_col", "frequency_col", "monetary_col"]
        for col in required_cols:
            if col not in config:
                return False
            if not isinstance(config[col], str) or not config[col].strip():
                return False

        # Validate n_segments if provided
        if "n_segments" in config:
            n_seg = config["n_segments"]
            if not isinstance(n_seg, int) or n_seg < 2 or n_seg > 10:
                return False

        # Validate optional fields
        if "date_col" in config and (
            not isinstance(config["date_col"], str) or not config["date_col"].strip()
        ):
            return False

        if "customer_id_col" in config and (
            not isinstance(config["customer_id_col"], str) or not config["customer_id_col"].strip()
        ):
            return False

        return True

    def _score_recency(self, values: list, reverse: bool = False) -> list[int]:
        """Score recency values 1-5 using quintiles.

        Args:
            values: List of recency values (lower = more recent if days ago, higher date = more recent)
            reverse: If True, higher values get better scores (for date format)

        Returns:
            List of scores 1-5 (5 = best)
        """
        arr = np.array(values, dtype=np.float64)
        arr = arr[~np.isnan(arr)]

        if len(arr) == 0:
            return [1] * len(values)

        # Calculate quintile boundaries
        quantiles = np.percentile(arr, [20, 40, 60, 80])

        def score_func(val):
            if np.isnan(val):
                return 1
            if reverse:
                # Higher date = more recent = better score
                if val <= quantiles[0]:
                    return 1
                elif val <= quantiles[1]:
                    return 2
                elif val <= quantiles[2]:
                    return 3
                elif val <= quantiles[3]:
                    return 4
                else:
                    return 5
            else:
                # Lower days ago = more recent = better score
                if val <= quantiles[0]:
                    return 5
                elif val <= quantiles[1]:
                    return 4
                elif val <= quantiles[2]:
                    return 3
                elif val <= quantiles[3]:
                    return 2
                else:
                    return 1

        return [score_func(v) for v in values]

    def _score_frequency(self, values: list) -> list[int]:
        """Score frequency values 1-5 using quintiles (higher = better)."""
        arr = np.array(values, dtype=np.float64)
        arr = arr[~np.isnan(arr)]

        if len(arr) == 0:
            return [1] * len(values)

        quantiles = np.percentile(arr, [20, 40, 60, 80])

        def score_func(val):
            if np.isnan(val):
                return 1
            if val <= quantiles[0]:
                return 1
            elif val <= quantiles[1]:
                return 2
            elif val <= quantiles[2]:
                return 3
            elif val <= quantiles[3]:
                return 4
            else:
                return 5

        return [score_func(v) for v in values]

    def _score_monetary(self, values: list) -> list[int]:
        """Score monetary values 1-5 using quintiles (higher = better)."""
        return self._score_frequency(values)  # Same logic as frequency

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        """Perform RFM analysis and segment customers."""
        collection = inputs["respondent_collection"]
        rows = collection.get("rows", collection) if isinstance(collection, dict) else collection

        if not isinstance(rows, list):
            raise ValueError("respondent_collection must contain a 'rows' list")

        # Extract configuration
        recency_col = config["recency_col"]
        frequency_col = config["frequency_col"]
        monetary_col = config["monetary_col"]
        n_segments = config.get("n_segments", 5)
        customer_id_col = config.get("customer_id_col", "id")
        date_col = config.get("date_col")

        # Extract column values
        recency_values = [row.get(recency_col) for row in rows]
        frequency_values = [row.get(frequency_col) for row in rows]
        monetary_values = [row.get(monetary_col) for row in rows]

        # Determine if recency is in date format or days ago
        use_date_format = False
        if date_col and len(rows) > 0:
            sample_date = rows[0].get(date_col)
            use_date_format = isinstance(sample_date, (datetime, str))

        # Score each dimension
        recency_scores = self._score_recency(recency_values, reverse=use_date_format)
        frequency_scores = self._score_frequency(frequency_values)
        monetary_scores = self._score_monetary(monetary_values)

        # Create RFM profiles
        profiles = []
        segment_labels = []

        for i, row in enumerate(rows):
            r_score = recency_scores[i]
            f_score = frequency_scores[i]
            m_score = monetary_scores[i]

            # Create RFM string (e.g., "545")
            rfm_str = f"{r_score}{f_score}{m_score}"

            # Calculate combined score for clustering
            rfm_score = r_score * 100 + f_score * 10 + m_score

            profiles.append(
                {
                    "customer_id": row.get(customer_id_col, f"customer_{i}"),
                    "recency_score": r_score,
                    "frequency_score": f_score,
                    "monetary_score": m_score,
                    "rfm_score": rfm_score,
                    "rfm_string": rfm_str,
                    "recency_raw": recency_values[i],
                    "frequency_raw": frequency_values[i],
                    "monetary_raw": monetary_values[i],
                }
            )

        # Assign segments using k-means on RFM scores
        segment_assignments = self._assign_segments(
            profiles, n_segments, recency_scores, frequency_scores, monetary_scores
        )

        # Build segment profiles
        segment_profiles = {}
        for seg_id in range(n_segments):
            seg_profiles = [p for p, s in zip(profiles, segment_assignments) if s == seg_id]

            if not seg_profiles:
                continue

            # Calculate segment statistics
            avg_r = np.mean([p["recency_score"] for p in seg_profiles])
            avg_f = np.mean([p["frequency_score"] for p in seg_profiles])
            avg_m = np.mean([p["monetary_score"] for p in seg_profiles])
            avg_monetary = np.mean([p["monetary_raw"] for p in seg_profiles])

            # Determine segment name based on scores
            if avg_r >= 4 and avg_f >= 4 and avg_m >= 4:
                seg_name = "Champions"
                seg_desc = "Recent, frequent, high-value customers"
            elif avg_r >= 4 and avg_f >= 3:
                seg_name = "Loyal Customers"
                seg_desc = "Recent and frequent purchasers"
            elif avg_r >= 4 and avg_m >= 4:
                seg_name = "Potential Loyalists"
                seg_desc = "Recent high-spenders, could increase frequency"
            elif avg_r <= 2 and avg_f >= 4:
                seg_name = "At Risk"
                seg_desc = "Frequent purchasers but haven't bought recently"
            elif avg_r <= 2 and avg_f <= 2 and avg_m <= 2:
                seg_name = "Lost"
                seg_desc = "Infrequent, low-value, inactive customers"
            elif avg_m >= 4:
                seg_name = "Big Spenders"
                seg_desc = "High monetary value regardless of frequency/recency"
            else:
                seg_name = f"Segment {seg_id + 1}"
                seg_desc = f"RFM: {avg_r:.1f}, {avg_f:.1f}, {avg_m:.1f}"

            segment_profiles[f"segment_{seg_id}"] = {
                "name": seg_name,
                "description": seg_desc,
                "size": len(seg_profiles),
                "avg_recency_score": float(avg_r),
                "avg_frequency_score": float(avg_f),
                "avg_monetary_score": float(avg_m),
                "avg_monetary_value": float(avg_monetary),
                "customer_ids": [p["customer_id"] for p in seg_profiles],
            }

        return {
            "segment_profile_set": {
                "profiles": segment_profiles,
                "segmentation_method": "rfm",
                "n_segments": n_segments,
                "scoring_date": datetime.now().isoformat(),
            }
        }

    def _assign_segments(
        self,
        profiles: list[dict],
        n_segments: int,
        recency_scores: list[int],
        frequency_scores: list[int],
        monetary_scores: list[int],
    ) -> list[int]:
        """Assign customers to segments using k-means on RFM scores.

        Args:
            profiles: List of customer RFM profiles
            n_segments: Number of segments to create
            recency_scores: List of recency scores
            frequency_scores: List of frequency scores
            monetary_scores: List of monetary scores

        Returns:
            List of segment assignments (0 to n_segments-1)
        """
        # Build feature matrix for k-means
        features = np.array(
            [[p["recency_score"], p["frequency_score"], p["monetary_score"]] for p in profiles],
            dtype=np.float64,
        )

        # Initialize centroids using quantiles
        centroids = []
        for i in range(n_segments):
            q = (i + 1) / (n_segments + 1)  # Quantile position
            r_centroid = np.quantile(recency_scores, q)
            f_centroid = np.quantile(frequency_scores, q)
            m_centroid = np.quantile(monetary_scores, q)
            centroids.append([r_centroid, f_centroid, m_centroid])

        centroids = np.array(centroids)

        # Simple k-means with max 100 iterations
        assignments = np.zeros(len(profiles), dtype=int)
        for _ in range(100):
            old_assignments = assignments.copy()

            # Assign to nearest centroid
            for i, feature in enumerate(features):
                distances = np.linalg.norm(centroids - feature, axis=1)
                assignments[i] = np.argmin(distances)

            # Check convergence
            if np.array_equal(assignments, old_assignments):
                break

            # Update centroids
            for j in range(n_segments):
                mask = assignments == j
                if np.any(mask):
                    centroids[j] = np.mean(features[mask], axis=0)

        return assignments.tolist()

    def test_fixtures(self) -> dict:
        """Provide test fixtures for contract testing."""
        return {
            "config": {
                "recency_col": "days_since_purchase",
                "frequency_col": "purchase_count",
                "monetary_col": "total_spend",
                "n_segments": 5,
                "customer_id_col": "customer_id",
            },
            "inputs": {
                "respondent_collection": {
                    "rows": [
                        {
                            "customer_id": "C001",
                            "days_since_purchase": 5,
                            "purchase_count": 15,
                            "total_spend": 1250.00,
                        },
                        {
                            "customer_id": "C002",
                            "days_since_purchase": 30,
                            "purchase_count": 8,
                            "total_spend": 650.00,
                        },
                        {
                            "customer_id": "C003",
                            "days_since_purchase": 180,
                            "purchase_count": 2,
                            "total_spend": 150.00,
                        },
                        {
                            "customer_id": "C004",
                            "days_since_purchase": 7,
                            "purchase_count": 20,
                            "total_spend": 2100.00,
                        },
                        {
                            "customer_id": "C005",
                            "days_since_purchase": 90,
                            "purchase_count": 3,
                            "total_spend": 300.00,
                        },
                    ]
                }
            },
            "expected_output": {
                "segment_profile_set": {
                    "profiles": {
                        "segment_0": {
                            "name": "Champions",
                            "description": "Recent, frequent, high-value customers",
                            "size": 1,
                            "avg_recency_score": 5.0,
                            "avg_frequency_score": 5.0,
                            "avg_monetary_score": 5.0,
                        },
                    },
                    "segmentation_method": "rfm",
                    "n_segments": 5,
                }
            },
        }
