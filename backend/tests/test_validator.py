"""Tests for backend/engine/validator.py."""

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import validator  # noqa: E402
from schemas.pipeline import (  # noqa: E402
    EdgeSchema,
    NodeSchema,
    PipelineSchema,
    Position,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_SOURCE_INFO = {
    "block_type": "source",
    "block_implementation": "csv_loader",
    "input_schemas": [],
    "output_schemas": ["respondent_collection"],
    "config_schema": {},
    "description": "CSV source",
}

MOCK_TEXT_SOURCE_INFO = {
    "block_type": "source",
    "block_implementation": "text_loader",
    "input_schemas": [],
    "output_schemas": ["text_corpus"],
    "config_schema": {},
    "description": "Text source",
}

MOCK_TRANSFORM_INFO = {
    "block_type": "transform",
    "block_implementation": "filter_rows",
    "input_schemas": ["respondent_collection"],
    "output_schemas": ["respondent_collection"],
    "config_schema": {},
    "description": "Filter transform",
}

MOCK_SINK_INFO = {
    "block_type": "sink",
    "block_implementation": "json_export",
    "input_schemas": ["respondent_collection"],
    "output_schemas": [],
    "config_schema": {},
    "description": "JSON sink",
}


def _mock_get_block_info(block_type: str, implementation: str) -> dict:
    """Lookup mock block info by type/implementation."""
    key = (block_type, implementation)
    mock_db = {
        ("source", "csv_loader"): MOCK_SOURCE_INFO,
        ("source", "text_loader"): MOCK_TEXT_SOURCE_INFO,
        ("transform", "filter_rows"): MOCK_TRANSFORM_INFO,
        ("sink", "json_export"): MOCK_SINK_INFO,
    }
    if key not in mock_db:
        raise KeyError(
            f"No block registered for type={block_type!r}, implementation={implementation!r}"
        )
    return mock_db[key]


# ---------------------------------------------------------------------------
# Tests for validate_connection
# ---------------------------------------------------------------------------


class TestValidateConnection:
    """Unit tests for validator.validate_connection."""

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_valid_connection(self, _mock_info) -> None:
        valid, reason = validator.validate_connection(
            source_block_type="source",
            source_block_implementation="csv_loader",
            target_block_type="transform",
            target_block_implementation="filter_rows",
            data_type="respondent_collection",
        )
        assert valid is True
        assert reason is None

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_source_not_registered(self, _mock_info) -> None:
        valid, reason = validator.validate_connection(
            source_block_type="source",
            source_block_implementation="nonexistent",
            target_block_type="transform",
            target_block_implementation="filter_rows",
            data_type="respondent_collection",
        )
        assert valid is False
        assert reason is not None
        assert "not found" in reason
        assert "nonexistent" in reason

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_target_not_registered(self, _mock_info) -> None:
        valid, reason = validator.validate_connection(
            source_block_type="source",
            source_block_implementation="csv_loader",
            target_block_type="transform",
            target_block_implementation="nonexistent",
            data_type="respondent_collection",
        )
        assert valid is False
        assert reason is not None
        assert "not found" in reason
        assert "nonexistent" in reason

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_data_type_not_in_source_outputs(self, _mock_info) -> None:
        valid, reason = validator.validate_connection(
            source_block_type="source",
            source_block_implementation="csv_loader",
            target_block_type="transform",
            target_block_implementation="filter_rows",
            data_type="text_corpus",
        )
        assert valid is False
        assert isinstance(reason, str) and "not in source block's output_schemas" in reason

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_data_type_not_in_target_inputs(self, _mock_info) -> None:
        """Sink only accepts respondent_collection, not text_corpus."""
        valid, reason = validator.validate_connection(
            source_block_type="source",
            source_block_implementation="text_loader",
            target_block_type="sink",
            target_block_implementation="json_export",
            data_type="text_corpus",
        )
        assert valid is False
        assert isinstance(reason, str) and "not in target block's input_schemas" in reason


# ---------------------------------------------------------------------------
# Tests for validate_pipeline
# ---------------------------------------------------------------------------


def _make_node(
    block_type: str = "source",
    implementation: str = "csv_loader",
) -> NodeSchema:
    return NodeSchema(
        node_id=uuid4(),
        block_type=block_type,  # type: ignore[arg-type]
        block_implementation=implementation,
        label="test",
        position=Position(x=0, y=0),
    )


def _make_edge(source: NodeSchema, target: NodeSchema, data_type: str) -> EdgeSchema:
    return EdgeSchema(
        edge_id=uuid4(),
        source_node=source.node_id,
        target_node=target.node_id,
        data_type=data_type,
    )


def _make_pipeline(
    nodes: list[NodeSchema] | None = None,
    edges: list[EdgeSchema] | None = None,
) -> PipelineSchema:
    return PipelineSchema(
        pipeline_id=uuid4(),
        name="test-pipeline",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        nodes=nodes or [],
        edges=edges or [],
    )


class TestValidatePipeline:
    """Unit tests for validator.validate_pipeline."""

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_valid_pipeline(self, _mock_info) -> None:
        source = _make_node("source", "csv_loader")
        transform = _make_node("transform", "filter_rows")
        sink = _make_node("sink", "json_export")
        edge1 = _make_edge(source, transform, "respondent_collection")
        edge2 = _make_edge(transform, sink, "respondent_collection")

        pipeline = _make_pipeline(
            nodes=[source, transform, sink],
            edges=[edge1, edge2],
        )
        valid, errors = validator.validate_pipeline(pipeline)
        assert valid is True
        assert errors == []

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_unknown_block_type(self, _mock_info) -> None:
        node = _make_node("source", "nonexistent_source")
        pipeline = _make_pipeline(nodes=[node])

        valid, errors = validator.validate_pipeline(pipeline)
        assert valid is False
        assert any("not registered" in e for e in errors)

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_edge_source_node_not_in_pipeline(self, _mock_info) -> None:
        orphan = _make_node("transform", "filter_rows")
        edge = EdgeSchema(
            edge_id=uuid4(),
            source_node=uuid4(),  # does not exist in nodes
            target_node=orphan.node_id,
            data_type="respondent_collection",
        )

        pipeline = _make_pipeline(nodes=[orphan], edges=[edge])
        valid, errors = validator.validate_pipeline(pipeline)
        assert valid is False
        assert any("source node" in e and "not found" in e for e in errors)

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_edge_target_node_not_in_pipeline(self, _mock_info) -> None:
        source = _make_node("source", "csv_loader")
        edge = EdgeSchema(
            edge_id=uuid4(),
            source_node=source.node_id,
            target_node=uuid4(),  # does not exist
            data_type="respondent_collection",
        )

        pipeline = _make_pipeline(nodes=[source], edges=[edge])
        valid, errors = validator.validate_pipeline(pipeline)
        assert valid is False
        assert any("target node" in e and "not found" in e for e in errors)

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_edge_data_type_mismatch(self, _mock_info) -> None:
        source = _make_node("source", "csv_loader")
        transform = _make_node("transform", "filter_rows")
        edge = _make_edge(source, transform, "text_corpus")

        pipeline = _make_pipeline(nodes=[source, transform], edges=[edge])
        valid, errors = validator.validate_pipeline(pipeline)
        assert valid is False
        assert any("text_corpus" in e for e in errors)

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_empty_pipeline_is_valid(self, _mock_info) -> None:
        pipeline = _make_pipeline()
        valid, errors = validator.validate_pipeline(pipeline)
        assert valid is True
        assert errors == []

    @patch.object(validator, "get_block_info", side_effect=_mock_get_block_info)
    def test_nodes_only_no_edges_is_valid(self, _mock_info) -> None:
        source = _make_node("source", "csv_loader")
        sink = _make_node("sink", "json_export")
        pipeline = _make_pipeline(nodes=[source, sink])
        valid, errors = validator.validate_pipeline(pipeline)
        assert valid is True
        assert errors == []
