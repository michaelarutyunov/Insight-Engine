"""Run state persistence for pipeline execution.

Stores run state and per-node status in SQLite via aiosqlite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import aiosqlite

from schemas.execution import (
    RunState,
    RunStatus,
)

_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "insights.db"

_CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    state_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""

_CREATE_NODE_STATUS_TABLE = """
CREATE TABLE IF NOT EXISTS run_node_status (
    run_id       TEXT NOT NULL,
    node_id      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    started_at   TEXT,
    completed_at TEXT,
    error        TEXT,
    PRIMARY KEY (run_id, node_id)
)
"""


async def _get_connection() -> aiosqlite.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(_DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute(_CREATE_RUNS_TABLE)
    await db.execute(_CREATE_NODE_STATUS_TABLE)
    await db.commit()
    return db


# ---------------------------------------------------------------------------
# Run CRUD
# ---------------------------------------------------------------------------


async def create_run(pipeline_id: UUID) -> RunState:
    """Create a new run for the given pipeline."""
    now = datetime.now(UTC)
    run_id = uuid4()

    run = RunState(
        run_id=run_id,
        pipeline_id=pipeline_id,
        status=RunStatus.PENDING,
        created_at=now,
        updated_at=now,
    )

    db = await _get_connection()
    try:
        await db.execute(
            "INSERT INTO runs (run_id, pipeline_id, status, state_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(run_id),
                str(pipeline_id),
                run.status,
                run.model_dump_json(),
                now.isoformat(),
                now.isoformat(),
            ),
        )
        await db.commit()
    finally:
        await db.close()

    return run


async def get_run(run_id: UUID | str) -> RunState | None:
    """Fetch a single run by id. Returns None if not found."""
    db = await _get_connection()
    try:
        cursor = await db.execute(
            "SELECT state_json FROM runs WHERE run_id = ?",
            (str(run_id),),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if row is None:
        return None

    return RunState.model_validate_json(row["state_json"])


async def update_run(run: RunState) -> RunState:
    """Persist updated run state."""
    now = datetime.now(UTC)
    run.updated_at = now

    db = await _get_connection()
    try:
        await db.execute(
            "UPDATE runs SET status = ?, state_json = ?, updated_at = ? WHERE run_id = ?",
            (run.status, run.model_dump_json(), now.isoformat(), str(run.run_id)),
        )
        await db.commit()
    finally:
        await db.close()

    return run


async def list_runs_for_pipeline(pipeline_id: UUID | str) -> list[RunState]:
    """Return all runs for a pipeline, newest first."""
    db = await _get_connection()
    try:
        cursor = await db.execute(
            "SELECT state_json FROM runs WHERE pipeline_id = ? ORDER BY updated_at DESC",
            (str(pipeline_id),),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [RunState.model_validate_json(r["state_json"]) for r in rows]


# ---------------------------------------------------------------------------
# Init (called from FastAPI lifespan)
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Ensure all required tables exist. Safe to call multiple times."""
    db = await _get_connection()
    await db.close()
