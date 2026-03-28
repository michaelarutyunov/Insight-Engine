"""Execution API — trigger pipeline runs and poll run status."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from engine.executor import execute_pipeline
from engine.validator import validate_pipeline
from schemas.execution import (
    NodeStatusResponse,
    RunCreateResponse,
    RunDetailResponse,
    RunStatus,
)
from storage.runs import create_run, get_run, update_run
from storage.sqlite import get_pipeline as storage_get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["execution"])


# ---------------------------------------------------------------------------
# Background task wrapper
# ---------------------------------------------------------------------------


async def _run_pipeline_task(pipeline_id_str: str, run_id_str: str) -> None:
    """Background task: execute pipeline and catch all exceptions."""
    from uuid import UUID

    from schemas.execution import RunStatus

    run_state = await get_run(UUID(run_id_str))
    if run_state is None:
        logger.error("Background task: run %s not found", run_id_str)
        return

    pipeline = await storage_get_pipeline(pipeline_id_str)
    if pipeline is None:
        from datetime import UTC, datetime

        run_state.status = RunStatus.FAILED
        run_state.error = f"Pipeline {pipeline_id_str} not found during execution"
        run_state.completed_at = datetime.now(UTC)
        await update_run(run_state)
        return

    try:
        await execute_pipeline(pipeline, run_id_str, run_state)
    except Exception as exc:
        from datetime import UTC, datetime

        logger.exception("Pipeline run %s failed with unhandled exception", run_id_str)
        # Re-fetch to get latest state before overwriting
        latest = await get_run(UUID(run_id_str))
        if latest is not None and latest.status not in (RunStatus.COMPLETED, RunStatus.SUSPENDED):
            latest.status = RunStatus.FAILED
            latest.error = f"Unhandled exception: {exc}"
            latest.completed_at = datetime.now(UTC)
            await update_run(latest)


# ---------------------------------------------------------------------------
# POST /api/v1/execution/{pipeline_id}/run
# ---------------------------------------------------------------------------


@router.post("/execution/{pipeline_id}/run", response_model=RunCreateResponse)
async def run_pipeline(
    pipeline_id: str,
    background_tasks: BackgroundTasks,
) -> RunCreateResponse:
    """Trigger an async pipeline run.

    1. Validate pipeline exists and passes structural validation.
    2. Create a RunState (status=pending) in the database.
    3. Launch execute_pipeline as a background task.
    4. Return run_id and status=pending immediately.
    """
    # --- load pipeline ---
    pipeline = await storage_get_pipeline(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # --- validate pipeline structure ---
    valid, errors = validate_pipeline(pipeline)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail={"message": "Pipeline validation failed", "errors": errors},
        )

    # --- create run record ---
    run_state = await create_run(pipeline.pipeline_id)

    # --- schedule background execution ---
    background_tasks.add_task(
        _run_pipeline_task,
        str(pipeline.pipeline_id),
        str(run_state.run_id),
    )

    return RunCreateResponse(run_id=run_state.run_id, status=RunStatus.PENDING)


# ---------------------------------------------------------------------------
# GET /api/v1/execution/{run_id}/status
# ---------------------------------------------------------------------------


@router.get("/execution/{run_id}/status", response_model=RunDetailResponse)
async def get_run_status(run_id: str) -> RunDetailResponse:
    """Return current run state with per-node breakdown.

    Returns 404 if the run_id is unknown.
    """
    from uuid import UUID

    try:
        uid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Run not found") from None

    run_state = await get_run(uid)
    if run_state is None:
        raise HTTPException(status_code=404, detail="Run not found")

    node_statuses = [
        NodeStatusResponse(
            node_id=ns.node_id,
            status=ns.status,
            started_at=ns.started_at,
            completed_at=ns.completed_at,
            error=ns.error,
        )
        for ns in run_state.node_states.values()
    ]

    checkpoint_data: dict | None = None
    if run_state.status == RunStatus.SUSPENDED and run_state.hitl_checkpoint is not None:
        checkpoint_data = run_state.hitl_checkpoint.checkpoint_data

    return RunDetailResponse(
        run_id=run_state.run_id,
        pipeline_id=run_state.pipeline_id,
        status=run_state.status,
        current_node_id=run_state.current_node_id,
        node_statuses=node_statuses,
        checkpoint_data=checkpoint_data,
        error=run_state.error,
        started_at=run_state.started_at,
        completed_at=run_state.completed_at,
    )
