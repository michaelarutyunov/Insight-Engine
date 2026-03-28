"""SQLite-backed storage for pipeline definitions.

Uses aiosqlite for native async support. All functions are async def and
designed to be awaited directly in FastAPI route handlers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiosqlite

from schemas.pipeline import (
    PipelineCreateRequest,
    PipelineSchema,
    PipelineUpdateRequest,
)

_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "insights.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipelines (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    definition_json TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""


async def _get_connection() -> aiosqlite.Connection:
    """Open (or create) the database and ensure the schema exists."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(_DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute(_CREATE_TABLE_SQL)
    await db.commit()
    return db


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


async def create_pipeline(request: PipelineCreateRequest) -> PipelineSchema:
    """Insert a new pipeline row and return the full schema."""
    now = datetime.now(UTC)
    pipeline_id = uuid4()

    pipeline = PipelineSchema(
        pipeline_id=pipeline_id,
        name=request.name,
        version="1.0",
        created_at=now,
        updated_at=now,
        nodes=request.nodes,
        edges=request.edges,
        loop_definitions=request.loop_definitions,
        metadata=request.metadata,
    )

    definition_json = pipeline.model_dump_json()
    description = request.metadata.description

    db = await _get_connection()
    try:
        await db.execute(
            "INSERT INTO pipelines (id, name, description, definition_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(pipeline_id),
                request.name,
                description,
                definition_json,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        await db.commit()
    finally:
        await db.close()

    return pipeline


async def get_pipeline(pipeline_id: str) -> PipelineSchema | None:
    """Fetch a single pipeline by id. Returns None if not found."""
    db = await _get_connection()
    try:
        cursor = await db.execute(
            "SELECT definition_json FROM pipelines WHERE id = ?",
            (pipeline_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if row is None:
        return None

    return PipelineSchema.model_validate_json(row["definition_json"])


async def list_pipelines() -> list[PipelineSchema]:
    """Return all pipelines, newest first."""
    db = await _get_connection()
    try:
        cursor = await db.execute("SELECT definition_json FROM pipelines ORDER BY updated_at DESC")
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [PipelineSchema.model_validate_json(r["definition_json"]) for r in rows]


async def update_pipeline(
    pipeline_id: str, request: PipelineUpdateRequest
) -> PipelineSchema | None:
    """Patch-update a pipeline. Returns the updated schema or None if not found."""
    existing = await get_pipeline(pipeline_id)
    if existing is None:
        return None

    now = datetime.now(UTC)

    # Apply partial updates — only overwrite fields that were explicitly set.
    if request.name is not None:
        existing.name = request.name
    if request.nodes is not None:
        existing.nodes = request.nodes
    if request.edges is not None:
        existing.edges = request.edges
    if request.loop_definitions is not None:
        existing.loop_definitions = request.loop_definitions
    if request.metadata is not None:
        existing.metadata = request.metadata

    existing.updated_at = now

    definition_json = existing.model_dump_json()
    description = existing.metadata.description

    db = await _get_connection()
    try:
        await db.execute(
            "UPDATE pipelines SET name = ?, description = ?, definition_json = ?, updated_at = ? "
            "WHERE id = ?",
            (
                existing.name,
                description,
                definition_json,
                now.isoformat(),
                pipeline_id,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    return existing


async def delete_pipeline(pipeline_id: str) -> bool:
    """Delete a pipeline by id. Returns True if a row was deleted."""
    db = await _get_connection()
    try:
        cursor = await db.execute(
            "DELETE FROM pipelines WHERE id = ?",
            (pipeline_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
