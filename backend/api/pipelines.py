from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from engine.validator import validate_connection, validate_pipeline
from schemas.pipeline import (
    ConnectionValidationRequest,
    ConnectionValidationResponse,
    PipelineCreateRequest,
    PipelineSchema,
    PipelineUpdateRequest,
    PipelineValidationResponse,
)
from storage.sqlite import (
    create_pipeline as storage_create,
)
from storage.sqlite import (
    delete_pipeline as storage_delete,
)
from storage.sqlite import (
    get_pipeline as storage_get,
)
from storage.sqlite import (
    list_pipelines as storage_list,
)
from storage.sqlite import (
    update_pipeline as storage_update,
)

router = APIRouter(tags=["pipelines"])


@router.get("/pipelines", response_model=list[PipelineSchema])
async def list_pipelines() -> list[PipelineSchema]:
    """Return all pipelines, newest first."""
    return await storage_list()


@router.post("/pipelines", response_model=PipelineSchema, status_code=201)
async def create_pipeline(body: PipelineCreateRequest) -> PipelineSchema:
    """Create a new pipeline."""
    return await storage_create(body)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineSchema)
async def get_pipeline(pipeline_id: str) -> PipelineSchema:
    """Fetch a single pipeline by id."""
    pipeline = await storage_get(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/pipelines/{pipeline_id}", response_model=PipelineSchema)
async def update_pipeline(pipeline_id: str, body: PipelineUpdateRequest) -> PipelineSchema:
    """Patch-update a pipeline."""
    pipeline = await storage_update(pipeline_id, body)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.delete("/pipelines/{pipeline_id}", status_code=204)
async def delete_pipeline(pipeline_id: str) -> JSONResponse:
    """Delete a pipeline by id."""
    deleted = await storage_delete(pipeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return JSONResponse(status_code=204, content=None)


# ---------------------------------------------------------------------------
# Validation endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/pipelines/validate-connection",
    response_model=ConnectionValidationResponse,
)
async def validate_connection_endpoint(
    body: ConnectionValidationRequest,
) -> ConnectionValidationResponse:
    """Check whether a single proposed connection is type-compatible."""
    valid, reason = validate_connection(
        source_block_type=body.source_block_type,
        source_block_implementation=body.source_block_implementation,
        target_block_type=body.target_block_type,
        target_block_implementation=body.target_block_implementation,
        data_type=body.data_type,
    )
    return ConnectionValidationResponse(valid=valid, reason=reason)


@router.post(
    "/pipelines/validate",
    response_model=PipelineValidationResponse,
)
async def validate_pipeline_endpoint(
    body: PipelineSchema,
) -> PipelineValidationResponse:
    """Validate a full pipeline definition (all nodes and edges)."""
    valid, errors = validate_pipeline(body)
    return PipelineValidationResponse(valid=valid, errors=errors)
