"""HITL (Human-in-the-Loop) API endpoints for submitting human responses."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from engine.state import resume_run
from schemas.execution import RunStatus
from storage.runs import get_run

router = APIRouter(tags=["hitl"])


class HITLResponseRequest(BaseModel):
    """Request body for submitting a human response to a suspended run."""

    response: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class HITLResponseResponse(BaseModel):
    """Response returned after submitting an HITL response."""

    run_id: str
    status: RunStatus


@router.post("/hitl/{run_id}/respond")
async def submit_hitl_response(
    run_id: str,
    body: HITLResponseRequest,
    background_tasks: BackgroundTasks,
) -> HITLResponseResponse:
    """Submit a human response to a suspended HITL run.

    Validates the run exists and is suspended, processes the human input,
    then relaunches pipeline execution as a background task.

    Returns:
        HITLResponseResponse with the run_id and updated status.

    Raises:
        HTTPException 404: Run not found.
        HTTPException 400: Run is not in suspended status.
    """
    # Validate run exists
    run_state = await get_run(run_id)
    if run_state is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Validate run is suspended
    if run_state.status != RunStatus.SUSPENDED:
        raise HTTPException(
            status_code=400,
            detail=f"Run {run_id} is not suspended (status={run_state.status})",
        )

    # Resume the run: process human input, update state
    try:
        updated_state = await resume_run(run_id, body.response)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Relaunch execution as a background task
    # Import here to avoid circular imports at module level
    from engine.executor import execute_pipeline
    from storage.sqlite import get_pipeline as get_pipeline_from_db

    pipeline = await get_pipeline_from_db(str(updated_state.pipeline_id))
    if pipeline is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline {updated_state.pipeline_id} not found",
        )

    background_tasks.add_task(
        execute_pipeline,
        pipeline=pipeline,
        run_id=str(updated_state.run_id),
        run_state=updated_state,
    )

    return HITLResponseResponse(
        run_id=run_id,
        status=updated_state.status,
    )
