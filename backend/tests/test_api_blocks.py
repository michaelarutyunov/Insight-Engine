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
    ("source", "csv_loader"),
    ("source", "db_source"),
    ("source", "sample_provider_source"),
    ("transform", "filter_transform"),
    ("transform", "column_recoding"),
    ("transform", "data_cleaning"),
    ("analysis", "segmentation_kmeans"),
    ("generation", "llm_generation"),
    ("evaluation", "rubric_evaluation"),
    ("evaluation", "concept_evaluator"),
    ("comparator", "side_by_side_comparator"),
    ("llm_flex", "prompt_flex"),
    ("router", "conditional_router"),
    ("router", "threshold_router"),
    ("hitl", "approval_gate"),
    ("reporting", "markdown_report"),
    ("sink", "json_sink"),
    ("sink", "api_push_sink"),
    ("sink", "notification_sink"),
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
async def test_list_blocks_returns_all_implementations(client):
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
        "methodological_notes",
        "tags",
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


# ---------------------------------------------------------------------------
# GET /api/v1/blocks?type={block_type} — filter by type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_blocks_no_filter_returns_all(client):
    """Test that omitting type parameter returns all blocks."""
    response = await client.get("/api/v1/blocks")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    returned_keys = {(b["block_type"], b["block_implementation"]) for b in data}
    assert returned_keys == EXPECTED_BLOCKS


@pytest.mark.asyncio
async def test_list_blocks_filter_by_type_transform(client):
    """Test filtering blocks by type=transform."""
    response = await client.get("/api/v1/blocks?type=transform")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert all(b["block_type"] == "transform" for b in data)
    assert any(b["block_implementation"] == "filter_transform" for b in data)


@pytest.mark.asyncio
async def test_list_blocks_filter_by_type_source(client):
    """Test filtering blocks by type=source."""
    response = await client.get("/api/v1/blocks?type=source")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert all(b["block_type"] == "source" for b in data)
    assert len(data) == 4
    impls = {b["block_implementation"] for b in data}
    assert impls == {"csv_source", "csv_loader", "db_source", "sample_provider_source"}


@pytest.mark.asyncio
async def test_list_blocks_filter_by_type_generation(client):
    """Test filtering blocks by type=generation."""
    response = await client.get("/api/v1/blocks?type=generation")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert all(b["block_type"] == "generation" for b in data)
    assert any(b["block_implementation"] == "llm_generation" for b in data)


@pytest.mark.asyncio
async def test_list_blocks_filter_by_type_invalid(client):
    """Test filtering by a type that has no blocks returns empty list."""
    response = await client.get("/api/v1/blocks?type=nonexistent")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_blocks_filter_case_sensitive(client):
    """Test that type filter is case-sensitive."""
    response = await client.get("/api/v1/blocks?type=Transform")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data == []


# ---------------------------------------------------------------------------
# New fields: methodological_notes and tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_blocks_each_entry_has_methodological_notes(client):
    response = await client.get("/api/v1/blocks")
    data = response.json()

    for block in data:
        assert "methodological_notes" in block, (
            f"Block ({block['block_type']}, {block['block_implementation']}) "
            f"missing methodological_notes"
        )
        assert isinstance(block["methodological_notes"], str)


@pytest.mark.asyncio
async def test_list_blocks_each_entry_has_tags(client):
    response = await client.get("/api/v1/blocks")
    data = response.json()

    for block in data:
        assert "tags" in block, (
            f"Block ({block['block_type']}, {block['block_implementation']}) "
            f"missing tags"
        )
        assert isinstance(block["tags"], list)
        for tag in block["tags"]:
            assert isinstance(tag, str)


@pytest.mark.asyncio
async def test_get_block_has_methodological_notes_and_tags(client):
    response = await client.get("/api/v1/blocks/source/csv_source")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert "methodological_notes" in data
    assert isinstance(data["methodological_notes"], str)
    assert "tags" in data
    assert isinstance(data["tags"], list)


# ---------------------------------------------------------------------------
# GET /api/v1/blocks?tags={tag} — filter by tag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_blocks_filter_by_tag_clustering(client):
    """Test filtering blocks by tags=clustering."""
    response = await client.get("/api/v1/blocks?tags=clustering")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert len(data) > 0
    for block in data:
        assert "clustering" in block["tags"], (
            f"{block['block_implementation']} should have 'clustering' tag"
        )


@pytest.mark.asyncio
async def test_list_blocks_filter_by_tag_no_match(client):
    """Test filtering by a tag that has no blocks returns empty list."""
    response = await client.get("/api/v1/blocks?tags=nonexistent_tag")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_blocks_filter_by_tags_comma_separated(client):
    """Test filtering by multiple comma-separated tags (OR logic)."""
    # Get all blocks with either tag
    response = await client.get("/api/v1/blocks?tags=clustering,data-preparation")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    for block in data:
        block_tags = set(block["tags"])
        assert block_tags.intersection({"clustering", "data-preparation"}), (
            f"{block['block_implementation']} should have 'clustering' or 'data-preparation' tag"
        )


@pytest.mark.asyncio
async def test_list_blocks_filter_by_type_and_tags_combined(client):
    """Test that type and tags filters work together."""
    response = await client.get("/api/v1/blocks?type=analysis&tags=clustering")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert len(data) > 0
    for block in data:
        assert block["block_type"] == "analysis"
        assert "clustering" in block["tags"]


@pytest.mark.asyncio
async def test_list_blocks_filter_by_type_and_tags_no_overlap(client):
    """Test combined filters when no blocks match both."""
    response = await client.get("/api/v1/blocks?type=sink&tags=clustering")
    assert response.status_code == HTTPStatus.OK

    data = response.json()
    assert data == []
