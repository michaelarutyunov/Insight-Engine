"""Tests for pipeline template fixtures."""

import json
from pathlib import Path

import pytest

from schemas.pipeline import PipelineSchema


class TestPipelineTemplates:
    """Test that all template files are valid pipeline definitions."""

    @pytest.fixture
    def templates_dir(self):
        """Path to templates directory."""
        return Path(__file__).parent.parent / "templates"

    def test_all_templates_are_valid_json(self, templates_dir):
        """Verify all template files contain valid JSON."""
        template_files = list(templates_dir.glob("*.json"))
        assert len(template_files) == 3, "Expected exactly 3 template files"

        for template_file in template_files:
            with open(template_file) as f:
                data = json.load(f)
            assert isinstance(data, dict), f"{template_file.name} should parse to a dict"

    def test_concept_prescreen_template_validates(self, templates_dir):
        """Concept prescreen template should conform to pipeline schema."""
        with open(templates_dir / "concept_prescreen.json") as f:
            data = json.load(f)

        pipeline = PipelineSchema(**data)
        assert pipeline.name == "Concept Prescreen Pipeline"
        assert len(pipeline.nodes) == 4
        assert len(pipeline.edges) == 3

    def test_discussion_guide_builder_template_validates(self, templates_dir):
        """Discussion guide builder template should conform to pipeline schema."""
        with open(templates_dir / "discussion_guide_builder.json") as f:
            data = json.load(f)

        pipeline = PipelineSchema(**data)
        assert pipeline.name == "Discussion Guide Builder"
        assert len(pipeline.nodes) == 5
        assert len(pipeline.edges) == 4

    def test_segmentation_report_template_validates(self, templates_dir):
        """Segmentation report template should conform to pipeline schema."""
        with open(templates_dir / "segmentation_report.json") as f:
            data = json.load(f)

        pipeline = PipelineSchema(**data)
        assert pipeline.name == "Segmentation Report Pipeline"
        assert len(pipeline.nodes) == 3
        assert len(pipeline.edges) == 2

    def test_template_metadata_required(self, templates_dir):
        """All templates should have required metadata fields."""
        for template_file in templates_dir.glob("*.json"):
            with open(template_file) as f:
                data = json.load(f)

            assert "metadata" in data, f"{template_file.name} missing metadata"
            metadata = data["metadata"]
            assert "description" in metadata, f"{template_file.name} missing description"
            assert "tags" in metadata, f"{template_file.name} missing tags"
            assert isinstance(metadata["tags"], list), f"{template_file.name} tags should be a list"

    def test_template_nodes_have_valid_schemas(self, templates_dir):
        """All nodes in templates should have valid input/output schemas."""
        from schemas.data_objects import DATA_TYPES

        valid_types = set(DATA_TYPES)

        for template_file in templates_dir.glob("*.json"):
            with open(template_file) as f:
                data = json.load(f)

            for node in data["nodes"]:
                # Source nodes should have empty input_schema
                if node["block_type"] == "source":
                    assert node["input_schema"] == [], (
                        f"{template_file.name} {node['node_id']}: "
                        f"Source nodes must have empty input_schema"
                    )

                # Sink nodes should have empty output_schema
                if node["block_type"] == "sink":
                    assert node["output_schema"] == [], (
                        f"{template_file.name} {node['node_id']}: "
                        f"Sink nodes must have empty output_schema"
                    )

                # All declared schemas should be in the data type vocabulary
                for schema in node.get("input_schema", []):
                    assert schema in valid_types, (
                        f"{template_file.name} {node['node_id']}: "
                        f"Unknown input schema type: {schema}"
                    )

                for schema in node.get("output_schema", []):
                    assert schema in valid_types, (
                        f"{template_file.name} {node['node_id']}: "
                        f"Unknown output schema type: {schema}"
                    )

    def test_template_edges_have_valid_data_types(self, templates_dir):
        """All edges should reference valid data types."""
        from schemas.data_objects import DATA_TYPES

        valid_types = set(DATA_TYPES)

        for template_file in templates_dir.glob("*.json"):
            with open(template_file) as f:
                data = json.load(f)

            # Build node lookup
            nodes_by_id = {n["node_id"]: n for n in data["nodes"]}

            for edge in data["edges"]:
                # Edge data_type must be valid
                assert edge["data_type"] in valid_types, (
                    f"{template_file.name} {edge['edge_id']}: "
                    f"Invalid data type: {edge['data_type']}"
                )

                # Edge data_type must be in source node's output_schema
                source_node = nodes_by_id[edge["source_node"]]
                assert edge["data_type"] in source_node["output_schema"], (
                    f"{template_file.name} {edge['edge_id']}: "
                    f"Data type {edge['data_type']} not in source node output"
                )

                # Edge data_type must be in target node's input_schema
                target_node = nodes_by_id[edge["target_node"]]
                assert edge["data_type"] in target_node["input_schema"], (
                    f"{template_file.name} {edge['edge_id']}: "
                    f"Data type {edge['data_type']} not in target node input"
                )

    def test_template_block_implementations_exist(self, templates_dir):
        """All referenced block implementations should exist in the registry."""
        from engine.registry import list_blocks

        registry_list = list_blocks()
        registry_implementations = {b["block_implementation"] for b in registry_list}

        for template_file in templates_dir.glob("*.json"):
            with open(template_file) as f:
                data = json.load(f)

            for node in data["nodes"]:
                impl = node["block_implementation"]
                assert impl in registry_implementations, (
                    f"{template_file.name} {node['node_id']}: "
                    f"Block implementation '{impl}' not found in registry"
                )

    def test_template_position_data_present(self, templates_dir):
        """All nodes should have position data for canvas rendering."""
        for template_file in templates_dir.glob("*.json"):
            with open(template_file) as f:
                data = json.load(f)

            for node in data["nodes"]:
                assert "position" in node, (
                    f"{template_file.name} {node['node_id']} missing position"
                )
                pos = node["position"]
                assert "x" in pos and isinstance(pos["x"], (int, float)), (
                    f"{template_file.name} {node['node_id']} invalid x position"
                )
                assert "y" in pos and isinstance(pos["y"], (int, float)), (
                    f"{template_file.name} {node['node_id']} invalid y position"
                )

    def test_template_configs_are_valid(self, templates_dir):
        """All node configs should pass block validation."""
        from engine.registry import get_block_class

        for template_file in templates_dir.glob("*.json"):
            with open(template_file) as f:
                data = json.load(f)

            for node in data["nodes"]:
                impl = node["block_implementation"]
                block_type = node["block_type"]
                block_class = get_block_class(block_type, impl)
                block_instance = block_class()

                # Config should pass validation
                assert block_instance.validate_config(node["config"]), (
                    f"{template_file.name} {node['node_id']} ({impl}): Config validation failed"
                )
