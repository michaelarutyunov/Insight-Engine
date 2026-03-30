"""Threshold Router block — routes based on evaluation metric scores."""

from typing import Any

import numpy as np

from blocks.base import RouterBase


class ThresholdRouter(RouterBase):
    """Routes pipeline execution based on aggregated evaluation scores against a threshold."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Evaluation dimension to check (e.g., 'appeal', 'clarity')",
                },
                "threshold": {
                    "type": "number",
                    "description": "Score boundary for routing decision",
                },
                "comparison": {
                    "type": "string",
                    "enum": ["above", "below", "equal"],
                    "default": "above",
                    "description": "Comparison operator",
                },
                "aggregation": {
                    "type": "string",
                    "enum": ["mean", "median", "min", "max"],
                    "default": "mean",
                    "description": "How to aggregate scores across evaluations",
                },
                "pass_edge_label": {
                    "type": "string",
                    "default": "pass",
                    "description": "Output edge ID when condition is met",
                },
                "fail_edge_label": {
                    "type": "string",
                    "default": "fail",
                    "description": "Output edge ID when condition is not met",
                },
            },
            "required": ["metric", "threshold"],
        }

    @property
    def description(self) -> str:
        return (
            "Routes pipeline execution based on evaluation scores. "
            "Compares an aggregated metric against a threshold to choose between pass/fail paths. "
            "Use after evaluation blocks to create conditional workflows."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Threshold selection requires domain knowledge of the evaluation scale and distribution "
            "of expected scores. The block assumes scores are numeric and comparable across evaluations. "
            "Aggregation method (mean, median, min, max) significantly impacts routing behavior: mean "
            "is sensitive to outliers, median is robust, and min/max enforce worst/best-case criteria. "
            "For skewed score distributions or small sample sizes, consider using median to avoid outlier-driven "
            "routing. Limitations: single-metric routing may miss multidimensional quality signals; "
            "alternatives include percentile-based routing or multi-criteria decision rules."
        )

    @property
    def tags(self) -> list[str]:
        return [
            "routing",
            "conditional-logic",
            "evaluation-filtering",
            "threshold-gating",
            "quality-control",
            "numeric-scores",
            "aggregation",
            "evaluation-set-input",
        ]

    def validate_config(self, config: dict) -> bool:
        if "metric" not in config or not isinstance(config["metric"], str):
            return False
        if "threshold" not in config or not isinstance(config["threshold"], (int, float)):
            return False
        if config.get("comparison", "above") not in ("above", "below", "equal"):
            return False
        if config.get("aggregation", "mean") not in ("mean", "median", "min", "max"):
            return False
        return isinstance(config.get("pass_edge_label", "pass"), str) and isinstance(
            config.get("fail_edge_label", "fail"), str
        )

    def _extract_scores(self, evaluations: list[dict], metric: str) -> list[float]:
        """Extract scores for a specific metric from all evaluations."""
        scores = []
        for eval_item in evaluations:
            scores_dict = eval_item.get("scores", {})
            if metric in scores_dict:
                score = scores_dict[metric]
                if isinstance(score, (int, float)):
                    scores.append(float(score))
        return scores

    def _aggregate_scores(self, scores: list[float], aggregation: str) -> float:
        """Apply aggregation function to scores."""
        if not scores:
            return 0.0

        if aggregation == "mean":
            return float(np.mean(scores))
        if aggregation == "median":
            return float(np.median(scores))
        if aggregation == "min":
            return float(np.min(scores))
        if aggregation == "max":
            return float(np.max(scores))

        return 0.0

    def _check_threshold(self, aggregated: float, threshold: float, comparison: str) -> bool:
        """Check if aggregated value meets threshold condition."""
        if comparison == "above":
            return aggregated > threshold
        if comparison == "below":
            return aggregated < threshold
        if comparison == "equal":
            return aggregated == threshold
        return False

    def resolve_route(self, inputs: dict[str, Any], config: dict | None = None) -> list[str]:
        """Return list of output edge IDs to activate based on threshold check."""
        if not config:
            return []

        evaluation_set = inputs.get("evaluation_set", {})
        evaluations = evaluation_set.get("evaluations", [])

        metric = config["metric"]
        threshold = config["threshold"]
        comparison = config.get("comparison", "above")
        aggregation = config.get("aggregation", "mean")

        scores = self._extract_scores(evaluations, metric)
        aggregated = self._aggregate_scores(scores, aggregation)

        pass_edge = config.get("pass_edge_label", "pass")
        fail_edge = config.get("fail_edge_label", "fail")

        if self._check_threshold(aggregated, threshold, comparison):
            return [pass_edge]
        return [fail_edge]

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        """Pass through evaluation_set unchanged; routing logic in resolve_route."""
        return {"evaluation_set": inputs["evaluation_set"]}

    def test_fixtures(self) -> dict:
        return {
            "config_pass": {
                "metric": "appeal",
                "threshold": 3.0,
                "comparison": "above",
                "aggregation": "mean",
                "pass_edge_label": "high_score",
                "fail_edge_label": "low_score",
            },
            "config_fail": {
                "metric": "appeal",
                "threshold": 8.0,
                "comparison": "above",
                "aggregation": "mean",
            },
            "config_below": {
                "metric": "clarity",
                "threshold": 2.5,
                "comparison": "below",
                "aggregation": "median",
            },
            "config_equal": {
                "metric": "novelty",
                "threshold": 5.0,
                "comparison": "equal",
                "aggregation": "mean",
            },
            "inputs": {
                "evaluation_set": {
                    "evaluations": [
                        {
                            "subject": "Concept A",
                            "scores": {"appeal": 4, "clarity": 3, "novelty": 5},
                        },
                        {
                            "subject": "Concept B",
                            "scores": {"appeal": 5, "clarity": 1, "novelty": 5},
                        },
                        {
                            "subject": "Concept C",
                            "scores": {"appeal": 3, "clarity": 2, "novelty": 5},
                        },
                    ],
                },
            },
            "expected_routes_pass": ["high_score"],
            "expected_routes_fail": ["fail"],
            "expected_routes_below": ["pass"],
            "expected_routes_equal": ["pass"],
        }
