"""Tests for the SQLite storage layer."""

from __future__ import annotations

from uuid import uuid4

import pytest

from schemas.pipeline import (
    PipelineCreateRequest,
    PipelineMetadata,
    PipelineUpdateRequest,
)
from storage.sqlite import (
    create_pipeline,
    delete_pipeline,
    get_pipeline,
    list_pipelines,
    update_pipeline,
)


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """Redirect the database to a temp file so tests are isolated."""
    import storage.sqlite as mod

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(mod, "_DB_PATH", tmp_db)


# ---------------------------------------------------------------------------
# create_pipeline
# ---------------------------------------------------------------------------


async def test_create_pipeline_returns_full_schema():
    req = PipelineCreateRequest(name="Test Pipeline")
    result = await create_pipeline(req)

    assert result.pipeline_id is not None
    assert result.name == "Test Pipeline"
    assert result.version == "1.0"
    assert result.created_at == result.updated_at
    assert result.nodes == []
    assert result.edges == []


async def test_create_pipeline_with_metadata():
    meta = PipelineMetadata(description="A test", tags=["unit"], author="ci")
    req = PipelineCreateRequest(name="With Meta", metadata=meta)
    result = await create_pipeline(req)

    assert result.metadata.description == "A test"
    assert result.metadata.tags == ["unit"]
    assert result.metadata.author == "ci"


# ---------------------------------------------------------------------------
# get_pipeline
# ---------------------------------------------------------------------------


async def test_get_pipeline_found():
    req = PipelineCreateRequest(name="Fetch Me")
    created = await create_pipeline(req)

    fetched = await get_pipeline(str(created.pipeline_id))
    assert fetched is not None
    assert fetched.pipeline_id == created.pipeline_id
    assert fetched.name == "Fetch Me"


async def test_get_pipeline_not_found():
    result = await get_pipeline(str(uuid4()))
    assert result is None


# ---------------------------------------------------------------------------
# list_pipelines
# ---------------------------------------------------------------------------


async def test_list_pipelines_empty():
    pipelines = await list_pipelines()
    assert pipelines == []


async def test_list_pipelines_returns_all():
    await create_pipeline(PipelineCreateRequest(name="P1"))
    await create_pipeline(PipelineCreateRequest(name="P2"))

    pipelines = await list_pipelines()
    names = {p.name for p in pipelines}
    assert names == {"P1", "P2"}


# ---------------------------------------------------------------------------
# update_pipeline
# ---------------------------------------------------------------------------


async def test_update_pipeline_name():
    created = await create_pipeline(PipelineCreateRequest(name="Old Name"))
    pid = str(created.pipeline_id)

    updated = await update_pipeline(pid, PipelineUpdateRequest(name="New Name"))
    assert updated is not None
    assert updated.name == "New Name"

    # Verify persistence
    fetched = await get_pipeline(pid)
    assert fetched is not None
    assert fetched.name == "New Name"


async def test_update_pipeline_preserves_unset_fields():
    created = await create_pipeline(
        PipelineCreateRequest(
            name="Keep Me",
            metadata=PipelineMetadata(description="original"),
        )
    )
    pid = str(created.pipeline_id)

    updated = await update_pipeline(pid, PipelineUpdateRequest(name="Changed"))
    assert updated is not None
    assert updated.name == "Changed"
    assert updated.metadata.description == "original"


async def test_update_pipeline_not_found():
    result = await update_pipeline(str(uuid4()), PipelineUpdateRequest(name="x"))
    assert result is None


async def test_update_pipeline_updates_timestamp():
    created = await create_pipeline(PipelineCreateRequest(name="Timestamp"))
    pid = str(created.pipeline_id)

    updated = await update_pipeline(pid, PipelineUpdateRequest(name="Timestamp v2"))
    assert updated is not None
    assert updated.updated_at >= created.updated_at


# ---------------------------------------------------------------------------
# delete_pipeline
# ---------------------------------------------------------------------------


async def test_delete_pipeline_found():
    created = await create_pipeline(PipelineCreateRequest(name="Delete Me"))
    pid = str(created.pipeline_id)

    deleted = await delete_pipeline(pid)
    assert deleted is True

    fetched = await get_pipeline(pid)
    assert fetched is None


async def test_delete_pipeline_not_found():
    deleted = await delete_pipeline(str(uuid4()))
    assert deleted is False
