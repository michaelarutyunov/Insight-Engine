"""Tests for ThresholdRouter block."""

import pytest

from blocks.routing.threshold_router import ThresholdRouter


class TestThresholdRouter:
    """Test ThresholdRouter block contract and behavior."""

    def test_block_contract(self) -> None:
        """Block must satisfy RouterBase contract."""
        block = ThresholdRouter()

        assert block.block_type == "router"
        assert "evaluation_set" in block.input_schemas
        assert "evaluation_set" in block.output_schemas
        assert isinstance(block.config_schema, dict)
        assert len(block.description) > 0

    def test_validate_config_valid(self) -> None:
        """Accept valid configurations."""
        block = ThresholdRouter()

        assert block.validate_config({"metric": "appeal", "threshold": 3.0})
        assert block.validate_config({"metric": "clarity", "threshold": 5})
        assert block.validate_config({"metric": "novelty", "threshold": 2.5, "comparison": "below"})
        assert block.validate_config(
            {"metric": "quality", "threshold": 4.0, "aggregation": "median"}
        )
        assert block.validate_config(
            {
                "metric": "appeal",
                "threshold": 3.0,
                "comparison": "above",
                "aggregation": "mean",
                "pass_edge_label": "high",
                "fail_edge_label": "low",
            }
        )

    def test_validate_config_invalid(self) -> None:
        """Reject invalid configurations."""
        block = ThresholdRouter()

        assert not block.validate_config({})
        assert not block.validate_config({"metric": "appeal"})
        assert not block.validate_config({"threshold": 3.0})
        assert not block.validate_config({"metric": 123, "threshold": 3.0})
        assert not block.validate_config({"metric": "appeal", "threshold": "high"})
        assert not block.validate_config(
            {"metric": "appeal", "threshold": 3.0, "comparison": "invalid"}
        )
        assert not block.validate_config(
            {"metric": "appeal", "threshold": 3.0, "aggregation": "invalid"}
        )

    @pytest.mark.asyncio
    async def test_execute_pass_through(self) -> None:
        """Data passes through unchanged."""
        block = ThresholdRouter()
        fixtures = block.test_fixtures()

        result = await block.execute(fixtures["inputs"], fixtures["config_pass"])
        # Output should match input exactly for pass-through
        assert result == fixtures["inputs"]

    def test_resolve_route_pass_above(self) -> None:
        """Routes to pass edge when mean score above threshold."""
        block = ThresholdRouter()
        fixtures = block.test_fixtures()

        routes = block.resolve_route(fixtures["inputs"], fixtures["config_pass"])
        assert routes == fixtures["expected_routes_pass"]

    def test_resolve_route_fail_above(self) -> None:
        """Routes to fail edge when mean score below threshold."""
        block = ThresholdRouter()
        fixtures = block.test_fixtures()

        routes = block.resolve_route(fixtures["inputs"], fixtures["config_fail"])
        assert routes == fixtures["expected_routes_fail"]

    def test_resolve_route_below(self) -> None:
        """Routes to pass edge when median score below threshold."""
        block = ThresholdRouter()
        fixtures = block.test_fixtures()

        routes = block.resolve_route(fixtures["inputs"], fixtures["config_below"])
        assert routes == fixtures["expected_routes_below"]

    def test_resolve_route_equal(self) -> None:
        """Routes to pass edge when mean score equals threshold."""
        block = ThresholdRouter()
        fixtures = block.test_fixtures()

        routes = block.resolve_route(fixtures["inputs"], fixtures["config_equal"])
        assert routes == fixtures["expected_routes_equal"]

    def test_aggregation_modes(self) -> None:
        """All aggregation modes produce correct results."""
        block = ThresholdRouter()

        inputs = {
            "evaluation_set": {
                "evaluations": [
                    {"subject": "A", "scores": {"metric": 1}},
                    {"subject": "B", "scores": {"metric": 5}},
                    {"subject": "C", "scores": {"metric": 3}},
                ]
            }
        }

        # Mean: (1 + 5 + 3) / 3 = 3
        config_mean = {"metric": "metric", "threshold": 2.5, "aggregation": "mean"}
        routes = block.resolve_route(inputs, config_mean)
        assert routes == ["pass"]

        # Median: 3
        config_median = {"metric": "metric", "threshold": 2.5, "aggregation": "median"}
        routes = block.resolve_route(inputs, config_median)
        assert routes == ["pass"]

        # Min: 1
        config_min = {"metric": "metric", "threshold": 1.5, "aggregation": "min"}
        routes = block.resolve_route(inputs, config_min)
        assert routes == ["fail"]

        # Max: 5
        config_max = {"metric": "metric", "threshold": 4.5, "aggregation": "max"}
        routes = block.resolve_route(inputs, config_max)
        assert routes == ["pass"]

    def test_comparison_operators(self) -> None:
        """All comparison operators work correctly."""
        block = ThresholdRouter()

        inputs = {"evaluation_set": {"evaluations": [{"subject": "A", "scores": {"metric": 4.0}}]}}

        # Above
        config_above = {"metric": "metric", "threshold": 3.0, "comparison": "above"}
        routes = block.resolve_route(inputs, config_above)
        assert routes == ["pass"]

        config_above_fail = {"metric": "metric", "threshold": 5.0, "comparison": "above"}
        routes = block.resolve_route(inputs, config_above_fail)
        assert routes == ["fail"]

        # Below
        config_below = {"metric": "metric", "threshold": 5.0, "comparison": "below"}
        routes = block.resolve_route(inputs, config_below)
        assert routes == ["pass"]

        config_below_fail = {"metric": "metric", "threshold": 3.0, "comparison": "below"}
        routes = block.resolve_route(inputs, config_below_fail)
        assert routes == ["fail"]

        # Equal
        config_equal = {"metric": "metric", "threshold": 4.0, "comparison": "equal"}
        routes = block.resolve_route(inputs, config_equal)
        assert routes == ["pass"]

        config_equal_fail = {"metric": "metric", "threshold": 3.0, "comparison": "equal"}
        routes = block.resolve_route(inputs, config_equal_fail)
        assert routes == ["fail"]

    def test_custom_edge_labels(self) -> None:
        """Custom pass/fail edge labels work correctly."""
        block = ThresholdRouter()

        inputs = {"evaluation_set": {"evaluations": [{"subject": "A", "scores": {"metric": 5.0}}]}}

        config = {
            "metric": "metric",
            "threshold": 3.0,
            "pass_edge_label": "approved",
            "fail_edge_label": "rejected",
        }

        routes = block.resolve_route(inputs, config)
        assert routes == ["approved"]

        config_fail = {
            "metric": "metric",
            "threshold": 7.0,
            "pass_edge_label": "approved",
            "fail_edge_label": "rejected",
        }

        routes = block.resolve_route(inputs, config_fail)
        assert routes == ["rejected"]

    def test_empty_evaluations(self) -> None:
        """Handles empty evaluation set gracefully."""
        block = ThresholdRouter()

        inputs = {"evaluation_set": {"evaluations": []}}
        config = {"metric": "appeal", "threshold": 3.0}

        routes = block.resolve_route(inputs, config)
        # With no scores, aggregated value is 0, which is below 3.0
        assert routes == ["fail"]

    def test_missing_metric_in_scores(self) -> None:
        """Handles evaluations missing the requested metric."""
        block = ThresholdRouter()

        inputs = {
            "evaluation_set": {
                "evaluations": [
                    {"subject": "A", "scores": {"other": 5}},
                    {"subject": "B", "scores": {"metric": 3}},
                ]
            }
        }
        config = {"metric": "metric", "threshold": 2.0}

        routes = block.resolve_route(inputs, config)
        # Only uses the score that has the metric
        assert routes == ["pass"]

    def test_no_config_returns_empty(self) -> None:
        """Returns empty route list when no config provided."""
        block = ThresholdRouter()

        inputs = {"evaluation_set": {"evaluations": []}}
        routes = block.resolve_route(inputs, None)
        assert routes == []

    def test_test_fixtures_complete(self) -> None:
        """Test fixtures provide all required fields."""
        block = ThresholdRouter()
        fixtures = block.test_fixtures()

        assert "config_pass" in fixtures
        assert "config_fail" in fixtures
        assert "config_below" in fixtures
        assert "config_equal" in fixtures
        assert "inputs" in fixtures
        # For pass-through routers, output equals input
        assert "expected_routes_pass" in fixtures
        assert "expected_routes_fail" in fixtures
        assert "expected_routes_below" in fixtures
        assert "expected_routes_equal" in fixtures
