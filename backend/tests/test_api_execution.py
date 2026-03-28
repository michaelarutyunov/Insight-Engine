"""Tests for the execution API endpoints."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """Redirect both storage modules to a temp file so tests are isolated."""
    import storage.runs as runs_mod
    import storage.sqlite as sqlite_mod

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(runs_mod, "_DB_PATH", tmp_db)
    monkeypatch.setattr(sqlite_mod, "_DB_PATH", tmp_db)


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_minimal_pipeline(client: AsyncClient) -> str:
    """Create a single-node (csv_loader source) pipeline and return its ID."""
    from uuid import uuid4

    node_id = str(uuid4())
    pipeline_body = {
        "name": "Test Pipeline",
        "nodes": [
            {
                "node_id": node_id,
                "block_type": "source",
                "block_implementation": "csv_loader",
                "label": "Load CSV",
                "config": {"file_path": "data.csv"},
                "position": {"x": 0, "y": 0},
            }
        ],
        "edges": [],
        "loop_definitions": [],
    }
    resp = await client.post("/api/v1/pipelines", json=pipeline_body)
    assert resp.status_code == 201, resp.text
    return resp.json()["pipeline_id"]


# ---------------------------------------------------------------------------
# POST /api/v1/execution/{pipeline_id}/run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_returns_200_with_pending_status(client):
    pipeline_id = await _create_minimal_pipeline(client)
    resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data["status"] == "pending"
    assert "run_id" in data


@pytest.mark.asyncio
async def test_run_returns_404_for_nonexistent_pipeline(client):
    fake_id = str(uuid4())
    resp = await client.post(f"/api/v1/execution/{fake_id}/run")
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_run_returns_400_for_invalid_pipeline(client):
    """A pipeline that references a non-existent block should return 400."""
    node_id = str(uuid4())
    src_id = str(uuid4())
    # Pipeline with a node referencing an unregistered block implementation
    pipeline_body = {
        "name": "Bad Pipeline",
        "nodes": [
            {
                "node_id": src_id,
                "block_type": "source",
                "block_implementation": "csv_loader",
                "label": "Load CSV",
                "config": {"file_path": "data.csv"},
                "position": {"x": 0, "y": 0},
            },
            {
                "node_id": node_id,
                "block_type": "transform",
                "block_implementation": "nonexistent_impl",
                "label": "Fake Transform",
                "config": {},
                "position": {"x": 200, "y": 0},
            },
        ],
        "edges": [],
        "loop_definitions": [],
    }
    resp = await client.post("/api/v1/pipelines", json=pipeline_body)
    assert resp.status_code == 201, resp.text
    pipeline_id = resp.json()["pipeline_id"]

    run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
    assert run_resp.status_code == HTTPStatus.BAD_REQUEST


# ---------------------------------------------------------------------------
# GET /api/v1/execution/{run_id}/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_returns_404_for_unknown_run(client):
    fake_run_id = str(uuid4())
    resp = await client.get(f"/api/v1/execution/{fake_run_id}/status")
    assert resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_status_returns_run_details(client):
    pipeline_id = await _create_minimal_pipeline(client)
    run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
    run_id = run_resp.json()["run_id"]

    status_resp = await client.get(f"/api/v1/execution/{run_id}/status")
    assert status_resp.status_code == HTTPStatus.OK

    data = status_resp.json()
    assert data["run_id"] == run_id
    assert data["pipeline_id"] == pipeline_id
    assert data["status"] in ("pending", "running", "completed", "failed", "suspended")
    assert "node_statuses" in data
    assert isinstance(data["node_statuses"], list)


@pytest.mark.asyncio
async def test_status_node_statuses_have_correct_fields(client):
    pipeline_id = await _create_minimal_pipeline(client)
    run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
    run_id = run_resp.json()["run_id"]

    # Allow background task to complete
    await asyncio.sleep(0.2)

    status_resp = await client.get(f"/api/v1/execution/{run_id}/status")
    assert status_resp.status_code == HTTPStatus.OK
    data = status_resp.json()

    for node_status in data["node_statuses"]:
        assert "node_id" in node_status
        assert "status" in node_status


@pytest.mark.asyncio
async def test_pipeline_executes_via_background_task(client):
    """Verify the background task actually runs the pipeline (poll until completed)."""
    pipeline_id = await _create_minimal_pipeline(client)
    run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
    assert run_resp.status_code == HTTPStatus.OK
    run_id = run_resp.json()["run_id"]

    # Poll until completed or failed (max ~2 seconds)
    final_status = None
    for _ in range(20):
        await asyncio.sleep(0.1)
        status_resp = await client.get(f"/api/v1/execution/{run_id}/status")
        data = status_resp.json()
        if data["status"] in ("completed", "failed"):
            final_status = data["status"]
            break

    assert final_status is not None, "Run did not complete within timeout"
    # csv_loader needs a real file path, so it may fail — either outcome is acceptable
    # as long as the background task actually ran and transitioned away from pending
    assert final_status in ("completed", "failed")


@pytest.mark.asyncio
async def test_status_response_fields_typed(client):
    """Verify all required response fields are present and typed correctly."""
    pipeline_id = await _create_minimal_pipeline(client)
    run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
    run_id = run_resp.json()["run_id"]

    status_resp = await client.get(f"/api/v1/execution/{run_id}/status")
    data = status_resp.json()

    # Required fields must be present
    for field in ("run_id", "pipeline_id", "status", "node_statuses"):
        assert field in data, f"Missing field: {field}"

    # Nullable fields may be None or absent but must not be missing from schema
    assert "current_node_id" in data
    assert "error" in data
    assert "started_at" in data
    assert "completed_at" in data
    assert "checkpoint_data" in data
