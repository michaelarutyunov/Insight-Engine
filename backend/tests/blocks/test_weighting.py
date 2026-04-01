"""Tests for Weighting transform block."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks.transforms.weighting import Weighting


def _run(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class TestWeighting:
    def test_execute_output_simple_gender_weighting(self):
        """Test simple 50/50 gender weighting."""
        block = Weighting()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))

        # Check structure
        assert "respondent_collection" in result
        rows = result["respondent_collection"]["rows"]
        assert len(rows) == 3

        # Check weights: 2 M's should get weight 0.75, 1 F should get 1.5
        # Weighted counts: 2 * 0.75 = 1.5 (M), 1 * 1.5 = 1.5 (F) -> 50/50
        assert rows[0]["weight"] == pytest.approx(0.75, abs=0.001)
        assert rows[1]["weight"] == pytest.approx(0.75, abs=0.001)
        assert rows[2]["weight"] == pytest.approx(1.5, abs=0.001)

    def test_execute_output_multi_dimensional_weighting(self):
        """Test weighting on two dimensions simultaneously."""
        block = Weighting()
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"id": 1, "gender": "M", "age_group": "18-34"},
                    {"id": 2, "gender": "M", "age_group": "35-54"},
                    {"id": 3, "gender": "F", "age_group": "18-34"},
                    {"id": 4, "gender": "F", "age_group": "35-54"},
                ],
            },
        }
        config = {
            "targets": {
                "gender": {"M": 0.5, "F": 0.5},
                "age_group": {"18-34": 0.4, "35-54": 0.6},
            },
            "weight_column": "weight",
            "max_iterations": 100,
            "tolerance": 0.001,
        }

        result = _run(block.execute(inputs, config))
        rows = result["respondent_collection"]["rows"]

        # All rows should have weights
        for row in rows:
            assert "weight" in row
            assert row["weight"] > 0

        # Check that weighted margins approximate targets
        total_weight = sum(row["weight"] for row in rows)

        # Gender weighted totals
        m_total = sum(row["weight"] for row in rows if row["gender"] == "M")
        f_total = sum(row["weight"] for row in rows if row["gender"] == "F")

        assert m_total / total_weight == pytest.approx(0.5, abs=0.01)
        assert f_total / total_weight == pytest.approx(0.5, abs=0.01)

        # Age weighted totals
        young_total = sum(row["weight"] for row in rows if row["age_group"] == "18-34")
        old_total = sum(row["weight"] for row in rows if row["age_group"] == "35-54")

        assert young_total / total_weight == pytest.approx(0.4, abs=0.01)
        assert old_total / total_weight == pytest.approx(0.6, abs=0.01)

    def test_execute_output_custom_weight_column(self):
        """Test that weight can be stored in a custom column."""
        block = Weighting()
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"id": 1, "region": "North"},
                    {"id": 2, "region": "North"},
                    {"id": 3, "region": "South"},
                ],
            },
        }
        config = {
            "targets": {"region": {"North": 0.5, "South": 0.5}},
            "weight_column": "rw_weight",
            "max_iterations": 100,
            "tolerance": 0.001,
        }

        result = _run(block.execute(inputs, config))
        rows = result["respondent_collection"]["rows"]

        # Check custom column name
        assert "rw_weight" in rows[0]
        assert rows[0]["rw_weight"] == pytest.approx(0.75, abs=0.001)
        assert rows[2]["rw_weight"] == pytest.approx(1.5, abs=0.001)

    def test_execute_output_handles_missing_values(self):
        """Test that missing values in target columns are handled gracefully."""
        block = Weighting()
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"id": 1, "gender": "M"},
                    {"id": 2, "gender": "F"},
                    {"id": 3, "gender": None},  # Missing value
                ],
            },
        }
        config = {
            "targets": {"gender": {"M": 0.5, "F": 0.5}},
            "weight_column": "weight",
            "max_iterations": 100,
            "tolerance": 0.001,
        }

        result = _run(block.execute(inputs, config))
        rows = result["respondent_collection"]["rows"]

        # All rows should have weights
        assert all("weight" in row for row in rows)

        # Row with missing gender should have minimum weight (doesn't contribute to margins)
        assert rows[2]["weight"] == pytest.approx(0.01, abs=0.001)

    def test_execute_output_minimum_weight_bound(self):
        """Test that weights are bounded below at 0.01."""
        block = Weighting()
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"id": 1, "category": "A"},
                    {"id": 2, "category": "A"},
                    {"id": 3, "category": "A"},
                    {"id": 4, "category": "B"},
                ],
            },
        }
        config = {
            "targets": {"category": {"A": 0.1, "B": 0.9}},
            "weight_column": "weight",
            "max_iterations": 100,
            "tolerance": 0.001,
        }

        result = _run(block.execute(inputs, config))
        rows = result["respondent_collection"]["rows"]

        # All weights should be >= 0.01
        for row in rows:
            assert row["weight"] >= 0.01

        # B rows should have much higher weight than A rows
        b_weights = [row["weight"] for row in rows if row["category"] == "B"]
        a_weights = [row["weight"] for row in rows if row["category"] == "A"]

        assert sum(b_weights) > sum(a_weights)

    def test_validate_config_accepts_valid_config(self):
        """Test that validate_config accepts valid configurations."""
        block = Weighting()

        # Minimal valid config
        assert block.validate_config({"targets": {"col1": {"A": 0.5, "B": 0.5}}}) is True

        # Full valid config
        config = {
            "targets": {
                "gender": {"M": 0.5, "F": 0.5},
                "age": {"young": 0.4, "old": 0.6},
            },
            "weight_column": "weight",
            "max_iterations": 50,
            "tolerance": 0.0001,
        }
        assert block.validate_config(config) is True

    def test_validate_config_rejects_missing_targets(self):
        """Test that validate_config rejects configs without targets."""
        block = Weighting()
        assert block.validate_config({}) is False
        assert block.validate_config({"weight_column": "weight"}) is False

    def test_validate_config_rejects_invalid_target_proportions(self):
        """Test that validate_config rejects target proportions that don't sum to 1."""
        block = Weighting()

        # Sum != 1.0
        assert block.validate_config({"targets": {"col1": {"A": 0.6, "B": 0.6}}}) is False
        assert block.validate_config({"targets": {"col1": {"A": 0.3, "B": 0.3}}}) is False

        # Negative proportions
        assert block.validate_config({"targets": {"col1": {"A": -0.5, "B": 1.5}}}) is False

        # Non-numeric proportions
        assert block.validate_config({"targets": {"col1": {"A": "half", "B": 0.5}}}) is False

    def test_validate_config_rejects_invalid_max_iterations(self):
        """Test that validate_config rejects invalid max_iterations."""
        block = Weighting()

        assert (
            block.validate_config({"targets": {"col1": {"A": 1.0}}, "max_iterations": 0}) is False
        )
        assert (
            block.validate_config({"targets": {"col1": {"A": 1.0}}, "max_iterations": 1001})
            is False
        )
        assert (
            block.validate_config({"targets": {"col1": {"A": 1.0}}, "max_iterations": "100"})
            is False
        )

    def test_validate_config_rejects_invalid_tolerance(self):
        """Test that validate_config rejects invalid tolerance."""
        block = Weighting()

        assert (
            block.validate_config({"targets": {"col1": {"A": 1.0}}, "tolerance": -0.001}) is False
        )
        assert block.validate_config({"targets": {"col1": {"A": 1.0}}, "tolerance": 2.0}) is False
        assert (
            block.validate_config({"targets": {"col1": {"A": 1.0}}, "tolerance": "0.001"}) is False
        )

    def test_validate_config_rejects_invalid_weight_column(self):
        """Test that validate_config rejects invalid weight_column."""
        block = Weighting()

        assert (
            block.validate_config({"targets": {"col1": {"A": 1.0}}, "weight_column": 123}) is False
        )
        assert (
            block.validate_config({"targets": {"col1": {"A": 1.0}}, "weight_column": None}) is False
        )

    def test_description_is_nonempty_string(self):
        """Test that description is present and non-empty."""
        block = Weighting()
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_methodological_notes_is_nonempty_string(self):
        """Test that methodological_notes is present and non-empty."""
        block = Weighting()
        assert isinstance(block.methodological_notes, str)
        assert len(block.methodological_notes) > 0

    def test_tags_is_list_of_strings(self):
        """Test that tags is a non-empty list of strings."""
        block = Weighting()
        assert isinstance(block.tags, list)
        assert len(block.tags) > 0
        assert all(isinstance(t, str) for t in block.tags)

    def test_input_output_schemas(self):
        """Test that schemas are correctly declared."""
        block = Weighting()
        assert block.input_schemas == ["respondent_collection"]
        assert block.output_schemas == ["respondent_collection"]

    def test_block_type(self):
        """Test that block_type is 'transform'."""
        block = Weighting()
        assert block.block_type == "transform"

    def test_config_schema_is_valid_dict(self):
        """Test that config_schema is a valid JSON Schema dict."""
        block = Weighting()
        assert isinstance(block.config_schema, dict)
        assert "type" in block.config_schema
        assert block.config_schema["type"] == "object"
        assert "properties" in block.config_schema
        assert "required" in block.config_schema
        assert "targets" in block.config_schema["required"]

    def test_fixtures_structure(self):
        """Test that test_fixtures returns the expected structure."""
        block = Weighting()
        fixtures = block.test_fixtures()

        assert isinstance(fixtures, dict)
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures
        assert "respondent_collection" in fixtures["inputs"]
        assert "respondent_collection" in fixtures["expected_output"]
