"""Tests for the connection validation API endpoint."""

from __future__ import annotations

from http import HTTPStatus

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
    """Provide an async httpx client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# Helper to build a connection validation request body.
def _body(
    source_type="source",
    source_impl="csv_source",
    target_type="transform",
    target_impl="filter_transform",
    data_type="respondent_collection",
    **kwargs,
) -> dict:
    return {
        "source_block_type": source_type,
        "source_block_implementation": source_impl,
        "target_block_type": target_type,
        "target_block_implementation": target_impl,
        "data_type": data_type,
    }


# ---------------------------------------------------------------------------
# Valid connections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_connection_source_to_transform(client):
    """csv_source -> filter_transform via respondent_collection."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is True
    assert data["reason"] is None


@pytest.mark.asyncio
async def test_valid_connection_transform_to_generation(client):
    """filter_transform -> llm_generation via respondent_collection."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            source_type="transform",
            source_impl="filter_transform",
            target_type="generation",
            target_impl="llm_generation",
            data_type="respondent_collection",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_valid_connection_generation_to_evaluation(client):
    """llm_generation -> rubric_evaluation via text_corpus."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            source_type="generation",
            source_impl="llm_generation",
            source_port="text_corpus",
            target_type="evaluation",
            target_impl="rubric_evaluation",
            target_port="text_corpus",
            data_type="text_corpus",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_valid_connection_evaluation_to_comparator(client):
    """rubric_evaluation -> side_by_side_comparator via evaluation_set."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            source_type="evaluation",
            source_impl="rubric_evaluation",
            source_port="evaluation_set",
            target_type="comparator",
            target_impl="side_by_side_comparator",
            target_port="evaluation_set",
            data_type="evaluation_set",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_valid_connection_comparator_to_sink(client):
    """side_by_side_comparator -> json_sink via evaluation_set."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            source_type="comparator",
            source_impl="side_by_side_comparator",
            source_port="evaluation_set",
            target_type="sink",
            target_impl="json_sink",
            target_port="evaluation_set",
            data_type="evaluation_set",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_valid_connection_evaluation_to_reporting(client):
    """rubric_evaluation -> markdown_report via evaluation_set."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            source_type="evaluation",
            source_impl="rubric_evaluation",
            source_port="evaluation_set",
            target_type="reporting",
            target_impl="markdown_report",
            target_port="evaluation_set",
            data_type="evaluation_set",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is True


# ---------------------------------------------------------------------------
# Invalid connections — wrong data type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_connection_wrong_data_type(client):
    """csv_source produces respondent_collection, but target expects evaluation_set."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            source_port="evaluation_set",
            target_type="comparator",
            target_impl="side_by_side_comparator",
            target_port="evaluation_set",
            data_type="evaluation_set",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is False
    assert "not in source block's output_schemas" in data["reason"]


@pytest.mark.asyncio
async def test_invalid_connection_data_type_not_in_target_inputs(client):
    """llm_generation produces text_corpus, but filter_transform only accepts respondent_collection."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            source_type="generation",
            source_impl="llm_generation",
            source_port="text_corpus",
            target_type="transform",
            target_impl="filter_transform",
            target_port="text_corpus",
            data_type="text_corpus",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is False
    assert "not in target block's input_schemas" in data["reason"]


# ---------------------------------------------------------------------------
# Invalid connections — nonexistent blocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_connection_source_block_not_found(client):
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            source_type="source",
            source_impl="nonexistent_source",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is False
    assert "not found in registry" in data["reason"]


@pytest.mark.asyncio
async def test_invalid_connection_target_block_not_found(client):
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json=_body(
            target_type="sink",
            target_impl="nonexistent_sink",
        ),
    )
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["valid"] is False
    assert "not found in registry" in data["reason"]


# ---------------------------------------------------------------------------
# Request validation — missing fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_connection_missing_fields_returns_422(client):
    """Missing required fields should return 422 Unprocessable Entity."""
    response = await client.post(
        "/api/v1/pipelines/validate-connection",
        json={},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
