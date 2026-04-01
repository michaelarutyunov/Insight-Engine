"""Tests for segmentation_lca block."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks.analysis.segmentation_lca import LCAAnalysis  # noqa: E402


class TestLCAAnalysisBlock:
    """Test LCA block implementation."""

    @pytest.fixture
    def block(self):
        return LCAAnalysis()

    def test_block_type(self, block):
        assert block.block_type == "analysis"

    def test_input_schemas(self, block):
        assert block.input_schemas == ["respondent_collection"]

    def test_output_schemas(self, block):
        assert block.output_schemas == ["segment_profile_set"]

    def test_config_schema(self, block):
        schema = block.config_schema
        assert schema["type"] == "object"
        assert "n_classes" in schema["properties"]
        assert "features" in schema["properties"]
        assert "max_iter" in schema["properties"]
        assert "random_state" in schema["properties"]
        assert set(schema["required"]) == {"n_classes", "features"}

    def test_dimensions(self, block):
        dims = block.dimensions
        assert dims["exploratory_confirmatory"] == "mixed"
        assert dims["assumption_weight"] == "high"
        assert dims["output_interpretability"] == "high"
        assert dims["sample_sensitivity"] == "high"
        assert dims["reproducibility"] == "medium"
        assert dims["data_structure_affinity"] == "categorical"

    def test_practitioner_workflow(self, block):
        assert block.practitioner_workflow == "segmentation.md"

    def test_description_exists(self, block):
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_methodological_notes_exist(self, block):
        assert isinstance(block.methodological_notes, str)
        assert len(block.methodological_notes) > 0

    def test_tags(self, block):
        tags = block.tags
        assert isinstance(tags, list)
        assert len(tags) > 0
        assert "clustering" in tags
        assert "segmentation" in tags
        assert "categorical-features" in tags

    def test_validate_config_valid(self, block):
        config = {
            "n_classes": 3,
            "features": ["brand_choice", "satisfaction"],
            "max_iter": 100,
            "random_state": 42,
        }
        assert block.validate_config(config) is True

    def test_validate_config_missing_n_classes(self, block):
        config = {"features": ["brand_choice"]}
        assert block.validate_config(config) is False

    def test_validate_config_missing_features(self, block):
        config = {"n_classes": 3}
        assert block.validate_config(config) is False

    def test_validate_config_n_classes_out_of_range(self, block):
        config = {"n_classes": 1, "features": ["brand"]}
        assert block.validate_config(config) is False

        config = {"n_classes": 25, "features": ["brand"]}
        assert block.validate_config(config) is False

    def test_validate_config_features_not_list(self, block):
        config = {"n_classes": 3, "features": "brand"}
        assert block.validate_config(config) is False

    def test_validate_config_features_empty(self, block):
        config = {"n_classes": 3, "features": []}
        assert block.validate_config(config) is False

    def test_validate_config_max_iter_invalid(self, block):
        config = {"n_classes": 3, "features": ["brand"], "max_iter": -1}
        assert block.validate_config(config) is False

    def test_validate_config_random_state_invalid(self, block):
        config = {"n_classes": 3, "features": ["brand"], "random_state": "42"}
        assert block.validate_config(config) is False

    def test_test_fixtures(self, block):
        fixtures = block.test_fixtures()
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures
        assert "respondent_collection" in fixtures["inputs"]

    @pytest.mark.asyncio
    async def test_execute_categorical_only(self, block):
        config = {
            "n_classes": 2,
            "features": ["brand_choice", "satisfaction"],
            "max_iter": 50,
            "random_state": 42,
        }
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"respondent_id": "r1", "brand_choice": "A", "satisfaction": "high"},
                    {"respondent_id": "r2", "brand_choice": "A", "satisfaction": "high"},
                    {"respondent_id": "r3", "brand_choice": "B", "satisfaction": "low"},
                    {"respondent_id": "r4", "brand_choice": "B", "satisfaction": "low"},
                    {"respondent_id": "r5", "brand_choice": "A", "satisfaction": "medium"},
                    {"respondent_id": "r6", "brand_choice": "B", "satisfaction": "medium"},
                ],
            },
        }

        result = await block.execute(inputs, config)

        assert "segment_profile_set" in result
        segments = result["segment_profile_set"]["segments"]
        assert len(segments) == 2

        for seg in segments:
            assert "segment_id" in seg
            assert "size" in seg
            assert "percentage" in seg
            assert "profile" in seg
            assert "member_indices" in seg
            assert seg["size"] > 0
            assert 0 < seg["percentage"] <= 100

    @pytest.mark.asyncio
    async def test_execute_mixed_data(self, block):
        config = {
            "n_classes": 2,
            "features": ["brand_choice", "age"],
            "max_iter": 50,
            "random_state": 42,
        }
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"respondent_id": "r1", "brand_choice": "A", "age": 25},
                    {"respondent_id": "r2", "brand_choice": "A", "age": 28},
                    {"respondent_id": "r3", "brand_choice": "B", "age": 55},
                    {"respondent_id": "r4", "brand_choice": "B", "age": 60},
                    {"respondent_id": "r5", "brand_choice": "A", "age": 30},
                ],
            },
        }

        result = await block.execute(inputs, config)

        assert "segment_profile_set" in result
        segments = result["segment_profile_set"]["segments"]
        assert len(segments) == 2

        # Check profile includes both categorical and numeric features
        for seg in segments:
            profile = seg["profile"]
            assert "brand_choice" in profile
            assert "age" in profile
            assert profile["brand_choice"]["type"] == "categorical"
            assert profile["age"]["type"] == "numeric"

    @pytest.mark.asyncio
    async def test_execute_n_classes_exceeds_rows(self, block):
        config = {
            "n_classes": 10,
            "features": ["brand"],
            "random_state": 42,
        }
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"respondent_id": "r1", "brand": "A"},
                    {"respondent_id": "r2", "brand": "B"},
                ],
            },
        }

        with pytest.raises(ValueError, match="n_classes.*must be less than"):
            await block.execute(inputs, config)

    @pytest.mark.asyncio
    async def test_execute_missing_feature_column(self, block):
        config = {
            "n_classes": 2,
            "features": ["nonexistent_column"],
            "random_state": 42,
        }
        inputs = {
            "respondent_collection": {
                "rows": [
                    {"respondent_id": "r1", "brand": "A"},
                ],
            },
        }

        with pytest.raises(ValueError, match="Feature column.*not found"):
            await block.execute(inputs, config)

    def test_preserves_input_type_false(self, block):
        assert block.preserves_input_type is False
