"""Tests for the pipeline CRUD API endpoints."""

from __future__ import annotations

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
    """Redirect the database to a temp file so tests are isolated."""
    import storage.sqlite as mod

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(mod, "_DB_PATH", tmp_db)


@pytest.fixture
def client():
    """Provide a sync httpx client wired to the FastAPI app.

    The endpoints are async but httpx handles that via ASGITransport.
    We use the sync client so tests can be plain (non-async) functions,
    keeping the test runner simple.
    """
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# POST /api/v1/pipelines — create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pipeline(client):
    payload = {"name": "Test Pipeline"}
    response = await client.post("/api/v1/pipelines", json=payload)

    assert response.status_code == HTTPStatus.CREATED

    data = response.json()
    assert data["name"] == "Test Pipeline"
    assert data["version"] == "1.0"
    assert data["pipeline_id"] is not None
    assert data["nodes"] == []
    assert data["edges"] == []


@pytest.mark.asyncio
async def test_create_pipeline_with_metadata(client):
    payload = {
        "name": "With Meta",
        "metadata": {
            "description": "A test",
            "tags": ["unit"],
            "author": "ci",
        },
    }
    response = await client.post("/api/v1/pipelines", json=payload)

    assert response.status_code == HTTPStatus.CREATED

    data = response.json()
    assert data["metadata"]["description"] == "A test"
    assert data["metadata"]["tags"] == ["unit"]
    assert data["metadata"]["author"] == "ci"


# ---------------------------------------------------------------------------
# GET /api/v1/pipelines — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pipelines_empty(client):
    response = await client.get("/api/v1/pipelines")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_pipelines_returns_all(client):
    await client.post("/api/v1/pipelines", json={"name": "P1"})
    await client.post("/api/v1/pipelines", json={"name": "P2"})

    response = await client.get("/api/v1/pipelines")

    assert response.status_code == HTTPStatus.OK
    names = {p["name"] for p in response.json()}
    assert names == {"P1", "P2"}


# ---------------------------------------------------------------------------
# GET /api/v1/pipelines/{id} — get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pipeline_found(client):
    create_resp = await client.post("/api/v1/pipelines", json={"name": "Fetch Me"})
    pipeline_id = create_resp.json()["pipeline_id"]

    response = await client.get(f"/api/v1/pipelines/{pipeline_id}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Fetch Me"


@pytest.mark.asyncio
async def test_get_pipeline_not_found(client):
    response = await client.get(f"/api/v1/pipelines/{uuid4()}")

    assert response.status_code == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# PUT /api/v1/pipelines/{id} — update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_pipeline_name(client):
    create_resp = await client.post("/api/v1/pipelines", json={"name": "Old"})
    pipeline_id = create_resp.json()["pipeline_id"]

    response = await client.put(
        f"/api/v1/pipelines/{pipeline_id}",
        json={"name": "New"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "New"


@pytest.mark.asyncio
async def test_update_pipeline_preserves_unset_fields(client):
    create_resp = await client.post(
        "/api/v1/pipelines",
        json={"name": "Keep", "metadata": {"description": "original"}},
    )
    pipeline_id = create_resp.json()["pipeline_id"]

    response = await client.put(
        f"/api/v1/pipelines/{pipeline_id}",
        json={"name": "Changed"},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["name"] == "Changed"
    assert data["metadata"]["description"] == "original"


@pytest.mark.asyncio
async def test_update_pipeline_not_found(client):
    response = await client.put(
        f"/api/v1/pipelines/{uuid4()}",
        json={"name": "x"},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_update_pipeline_updates_timestamp(client):
    create_resp = await client.post("/api/v1/pipelines", json={"name": "TS"})
    pipeline_id = create_resp.json()["pipeline_id"]
    created_at = create_resp.json()["created_at"]

    response = await client.put(
        f"/api/v1/pipelines/{pipeline_id}",
        json={"name": "TS v2"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["updated_at"] >= created_at


# ---------------------------------------------------------------------------
# DELETE /api/v1/pipelines/{id} — delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_pipeline_found(client):
    create_resp = await client.post("/api/v1/pipelines", json={"name": "Delete Me"})
    pipeline_id = create_resp.json()["pipeline_id"]

    response = await client.delete(f"/api/v1/pipelines/{pipeline_id}")

    assert response.status_code == HTTPStatus.NO_CONTENT

    # Verify it's gone
    get_resp = await client.get(f"/api/v1/pipelines/{pipeline_id}")
    assert get_resp.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_delete_pipeline_not_found(client):
    response = await client.delete(f"/api/v1/pipelines/{uuid4()}")

    assert response.status_code == HTTPStatus.NOT_FOUND
