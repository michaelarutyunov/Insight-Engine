"""Tests for the co-pilot modify endpoint and diff utilities.

Tests:
1. Unit tests for compute_pipeline_diff in chat/diff.py
2. Integration tests for POST /api/v1/chat/modify with mocked LLM.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from chat.diff import compute_pipeline_diff
from main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """Redirect the database to a temp file so tests are isolated."""
    import storage.sqlite as mod

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(mod, "_DB_PATH", tmp_db)


@pytest.fixture
def client():
    """Provide an async httpx client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
def sample_pipeline():
    """A simple pipeline for testing."""
    pid = uuid4()
    nid1, nid2 = uuid4(), uuid4()
    eid = uuid4()
    return {
        "pipeline_id": str(pid),
        "name": "Test Pipeline",
        "version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "nodes": [
            {
                "node_id": str(nid1),
                "block_type": "source",
                "block_implementation": "db_source",
                "label": "Data Source",
                "position": {"x": 100, "y": 100},
                "config": {},
                "input_schema": [],
                "output_schema": ["respondent_collection"],
            },
            {
                "node_id": str(nid2),
                "block_type": "transform",
                "block_implementation": "data_cleaning",
                "label": "Clean Data",
                "position": {"x": 400, "y": 100},
                "config": {},
                "input_schema": ["respondent_collection"],
                "output_schema": ["respondent_collection"],
            },
        ],
        "edges": [
            {
                "edge_id": str(eid),
                "source_node": str(nid1),
                "target_node": str(nid2),
                "data_type": "respondent_collection",
                "validated": False,
            }
        ],
        "loop_definitions": [],
        "metadata": {"description": "Test", "tags": [], "author": ""},
    }


@pytest.fixture
async def stored_pipeline(sample_pipeline, tmp_path):
    """Store a pipeline in the test database."""
    from schemas.pipeline import PipelineSchema

    schema = PipelineSchema(**sample_pipeline)
    tmp_db = tmp_path / "test.db"
    import storage.sqlite as mod

    original_path = mod._DB_PATH
    mod._DB_PATH = tmp_db

    # Create the pipeline directly in the DB
    import aiosqlite

    db = await aiosqlite.connect(str(tmp_db))
    await db.execute(
        "CREATE TABLE IF NOT EXISTS pipelines (id TEXT PRIMARY KEY, name TEXT, description TEXT, definition_json TEXT, created_at TEXT, updated_at TEXT)"
    )
    await db.execute(
        "INSERT INTO pipelines (id, name, description, definition_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            str(schema.pipeline_id),
            schema.name,
            schema.metadata.description,
            schema.model_dump_json(),
            schema.created_at.isoformat(),
            schema.updated_at.isoformat(),
        ),
    )
    await db.commit()
    await db.close()

    yield schema

    mod._DB_PATH = original_path


# ---------------------------------------------------------------------------
# Unit tests for compute_pipeline_diff
# ---------------------------------------------------------------------------
class TestComputePipelineDiff:
    def test_empty_diff_when_identical(self, sample_pipeline):
        """Returns empty diff when pipelines are identical."""
        diff = compute_pipeline_diff(sample_pipeline, sample_pipeline)
        assert len(diff.added_nodes) == 0
        assert len(diff.removed_nodes) == 0
        assert len(diff.added_edges) == 0
        assert len(diff.removed_edges) == 0

    def test_detects_added_node(self, sample_pipeline):
        """Detects a new node added in the modified pipeline."""
        new_node_id = str(uuid4())
        modified = json.loads(json.dumps(sample_pipeline))
        modified["nodes"].append(
            {
                "node_id": new_node_id,
                "block_type": "sink",
                "block_implementation": "csv_sink",
                "label": "Export CSV",
                "position": {"x": 700, "y": 100},
                "config": {},
                "input_schema": ["respondent_collection"],
                "output_schema": [],
            }
        )

        diff = compute_pipeline_diff(sample_pipeline, modified)
        assert len(diff.added_nodes) == 1
        assert diff.added_nodes[0].id == new_node_id
        assert diff.added_nodes[0].block_type == "sink"
        assert diff.added_nodes[0].block_implementation == "csv_sink"
        assert len(diff.removed_nodes) == 0

    def test_detects_removed_node(self, sample_pipeline):
        """Detects a node removed from the original pipeline."""
        modified = json.loads(json.dumps(sample_pipeline))
        removed_node = modified["nodes"].pop()
        removed_id = removed_node["node_id"]

        diff = compute_pipeline_diff(sample_pipeline, modified)
        assert len(diff.removed_nodes) == 1
        assert diff.removed_nodes[0].id == removed_id
        assert len(diff.added_nodes) == 0

    def test_detects_added_edge(self, sample_pipeline):
        """Detects a new edge added in the modified pipeline."""
        new_edge_id = str(uuid4())
        # Add a sink node first
        sink_id = str(uuid4())
        modified = json.loads(json.dumps(sample_pipeline))
        modified["nodes"].append(
            {
                "node_id": sink_id,
                "block_type": "sink",
                "block_implementation": "csv_sink",
                "label": "Export",
                "position": {"x": 700, "y": 100},
                "config": {},
                "input_schema": ["respondent_collection"],
                "output_schema": [],
            }
        )
        modified["edges"].append(
            {
                "edge_id": new_edge_id,
                "source_node": modified["nodes"][1]["node_id"],  # From the transform
                "target_node": sink_id,
                "data_type": "respondent_collection",
                "validated": False,
            }
        )

        diff = compute_pipeline_diff(sample_pipeline, modified)
        assert len(diff.added_edges) == 1
        assert diff.added_edges[0].id == new_edge_id
        assert len(diff.removed_edges) == 0

    def test_detects_removed_edge(self, sample_pipeline):
        """Detects an edge removed from the original pipeline."""
        modified = json.loads(json.dumps(sample_pipeline))
        removed_edge = modified["edges"].pop()
        removed_id = removed_edge["edge_id"]

        diff = compute_pipeline_diff(sample_pipeline, modified)
        assert len(diff.removed_edges) == 1
        assert diff.removed_edges[0].id == removed_id
        assert len(diff.added_edges) == 0

    def test_detects_multiple_changes(self, sample_pipeline):
        """Detects multiple additions and removals."""
        new_node_id = str(uuid4())
        modified = json.loads(json.dumps(sample_pipeline))
        # Add a node
        modified["nodes"].append(
            {
                "node_id": new_node_id,
                "block_type": "sink",
                "block_implementation": "csv_sink",
                "label": "Export",
                "position": {"x": 700, "y": 100},
                "config": {},
                "input_schema": ["respondent_collection"],
                "output_schema": [],
            }
        )
        # Remove the second node
        removed_node = modified["nodes"].pop(1)
        removed_id = removed_node["node_id"]
        # Remove the edge (it's now invalid)
        modified["edges"].pop(0)

        diff = compute_pipeline_diff(sample_pipeline, modified)
        assert len(diff.added_nodes) == 1
        assert len(diff.removed_nodes) == 1
        assert diff.removed_nodes[0].id == removed_id
        assert len(diff.added_edges) == 0
        assert len(diff.removed_edges) == 1


# ---------------------------------------------------------------------------
# Integration tests for POST /api/v1/chat/modify
# ---------------------------------------------------------------------------
class TestModifyEndpoint:
    @pytest.mark.asyncio
    async def test_modify_endpoint_returns_diff(self, client, stored_pipeline, sample_pipeline):
        """POST /api/v1/chat/modify returns a structured diff."""
        modified_pipeline = json.loads(json.dumps(sample_pipeline))
        # Add a node in the "LLM response"
        new_node_id = str(uuid4())
        modified_pipeline["nodes"].append(
            {
                "node_id": new_node_id,
                "block_type": "sink",
                "block_implementation": "csv_sink",
                "label": "Export CSV",
                "position": {"x": 700, "y": 100},
                "config": {},
                "input_schema": ["respondent_collection"],
                "output_schema": [],
            }
        )

        with patch("chat.copilot.anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps(modified_pipeline))]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await client.post(
                "/api/v1/chat/modify",
                json={
                    "message": "Add a CSV export sink",
                    "pipeline_id": str(stored_pipeline.pipeline_id),
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "explanation" in data
        assert "pipeline_diff" in data
        assert "added_nodes" in data["pipeline_diff"]
        assert len(data["pipeline_diff"]["added_nodes"]) == 1
        assert data["pipeline_diff"]["added_nodes"][0]["block_implementation"] == "csv_sink"

    @pytest.mark.asyncio
    async def test_modify_endpoint_rejects_empty_message(self, client):
        """POST /api/v1/chat/modify rejects an empty message."""
        response = await client.post(
            "/api/v1/chat/modify",
            json={"message": "", "pipeline_id": str(uuid4())},
        )
        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_modify_endpoint_rejects_missing_pipeline_id(self, client):
        """POST /api/v1/chat/modify rejects missing pipeline_id."""
        response = await client.post(
            "/api/v1/chat/modify",
            json={"message": "Add a sink"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_modify_endpoint_returns_404_for_nonexistent_pipeline(self, client):
        """POST /api/v1/chat/modify returns 404 when pipeline not found."""
        with patch("chat.copilot.anthropic.AsyncAnthropic"):
            response = await client.post(
                "/api/v1/chat/modify",
                json={"message": "Add a sink", "pipeline_id": str(uuid4())},
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_modify_endpoint_returns_422_on_llm_failure(self, client, stored_pipeline):
        """POST /api/v1/chat/modify returns 422 when LLM fails to return JSON."""
        with patch("chat.copilot.anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="This is not JSON")]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await client.post(
                "/api/v1/chat/modify",
                json={
                    "message": "Add a sink",
                    "pipeline_id": str(stored_pipeline.pipeline_id),
                },
            )
        assert response.status_code == 422
        assert "Failed to parse" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_modify_endpoint_includes_block_catalog_in_context(self, client, stored_pipeline):
        """The modify endpoint includes block catalog in the LLM prompt."""
        with patch("chat.copilot.anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            # Return the same pipeline (no changes)
            mock_response.content = [
                MagicMock(text=json.dumps(stored_pipeline.model_dump(mode="json")))
            ]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await client.post(
                "/api/v1/chat/modify",
                json={
                    "message": "Make no changes",
                    "pipeline_id": str(stored_pipeline.pipeline_id),
                },
            )

            # Verify the LLM was called
            assert mock_client.messages.create.called
            call_args = mock_client.messages.create.call_args
            # Check that block catalog was included in the user prompt
            user_prompt = call_args[1]["messages"][0]["content"]
            assert "Block Catalog" in user_prompt

    @pytest.mark.asyncio
    async def test_modify_endpoint_generates_explanation(self, client, stored_pipeline):
        """The modify endpoint generates a human-readable explanation."""
        modified_pipeline = stored_pipeline.model_dump(mode="json")
        # Add two nodes
        for i in range(2):
            new_node_id = str(uuid4())
            modified_pipeline["nodes"].append(
                {
                    "node_id": new_node_id,
                    "block_type": "sink",
                    "block_implementation": "csv_sink",
                    "label": f"Export {i}",
                    "position": {"x": 700 + i * 100, "y": 100},
                    "config": {},
                    "input_schema": ["respondent_collection"],
                    "output_schema": [],
                }
            )

        with patch("chat.copilot.anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps(modified_pipeline))]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            response = await client.post(
                "/api/v1/chat/modify",
                json={
                    "message": "Add two CSV exports",
                    "pipeline_id": str(stored_pipeline.pipeline_id),
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "explanation" in data
        assert "2 node(s)" in data["explanation"]
