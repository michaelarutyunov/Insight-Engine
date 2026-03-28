"""Tests for the block catalog API endpoints."""

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


# ---------------------------------------------------------------------------
# Expected block implementations (one per type)
# ---------------------------------------------------------------------------

EXPECTED_BLOCKS = {
    ("source", "csv_source"),
    ("transform", "filter_transform"),
    ("generation", "llm_generation"),
    ("evaluation", "rubric_evaluation"),
    ("comparator", "side_by_side_comparator"),
    ("llm_flex", "prompt_flex"),
    ("router", "conditional_router"),
    ("hitl", "approval_gate"),
    ("reporting", "markdown_report"),
    ("sink", "json_sink"),
}


# ---------------------------------------------------------------------------
# GET /api/v1/blocks — list all blocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_blocks_returns_200(client):
    response = await client.get("/api/v1/blocks")
    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_list_blocks_returns_list(client):
    response = await client.get("/api/v1/blocks")
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_blocks_returns_all_ten_implementations(client):
    response = await client.get("/api/v1/blocks")
    data = response.json()

    returned_keys = {(b["block_type"], b["block_implementation"]) for b in data}
    assert returned_keys == EXPECTED_BLOCKS


@pytest.mark.asyncio
async def test_list_blocks_each_entry_has_required_fields(client):
    response = await client.get("/api/v1/blocks")
    data = response.json()

    required_fields = {
        "block_type",
        "block_implementation",
        "input_schemas",
        "output_schemas",
        "config_schema",
        "description",
    }
    for block in data:
        assert required_fields.issubset(block.keys()), (
            f"Block ({block.get('block_type')}, {block.get('block_implementation')}) "
            f"missing fields: {required_fields - block.keys()}"
        )


@pytest.mark.asyncio
async def test_list_blocks_schemas_are_lists_of_strings(client):
    response = await client.get("/api/v1/blocks")
    data = response.json()

    for block in data:
        assert isinstance(block["input_schemas"], list), (
            f"{block['block_implementation']}: input_schemas must be a list"
        )
        assert isinstance(block["output_schemas"], list), (
            f"{block['block_implementation']}: output_schemas must be a list"
        )
        for dt in block["input_schemas"] + block["output_schemas"]:
            assert isinstance(dt, str), (
                f"{block['block_implementation']}: data type identifiers must be strings"
            )


@pytest.mark.asyncio
async def test_list_blocks_config_schema_is_dict(client):
    response = await client.get("/api/v1/blocks")
    data = response.json()

    for block in data:
        assert isinstance(block["config_schema"], dict), (
            f"{block['block_implementation']}: config_schema must be a dict"
        )


# ---------------------------------------------------------------------------
# GET /api/v1/blocks/{block_type}/{implementation} — get specific block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_block_found(client):
    response = await client.get("/api/v1/blocks/source/csv_source")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["block_type"] == "source"
    assert data["block_implementation"] == "csv_source"
    assert data["output_schemas"] == ["respondent_collection"]
    assert data["input_schemas"] == []


@pytest.mark.asyncio
async def test_get_block_not_found(client):
    response = await client.get("/api/v1/blocks/nonexistent/imaginary_block")
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_get_block_sink_has_no_outputs(client):
    response = await client.get("/api/v1/blocks/sink/json_sink")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data["output_schemas"] == []
    assert "evaluation_set" in data["input_schemas"]


@pytest.mark.asyncio
async def test_get_block_evaluation_has_multiple_inputs(client):
    response = await client.get("/api/v1/blocks/evaluation/rubric_evaluation")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert set(data["input_schemas"]) == {"text_corpus", "concept_brief_set"}
    assert data["output_schemas"] == ["evaluation_set"]
