"""Pydantic models for block catalog API responses."""

from __future__ import annotations

from pydantic import BaseModel, RootModel


class BlockInfoResponse(BaseModel):
    """Response model for a single block's full information."""

    block_type: str
    block_implementation: str
    input_schemas: list[str]
    output_schemas: list[str]
    config_schema: dict
    description: str
    methodological_notes: str
    tags: list[str]
    dimensions: dict[str, str] | None = None
    practitioner_workflow: str | None = None

    model_config = {"populate_by_name": True}


class BlockListResponse(RootModel[list[BlockInfoResponse]]):
    """Response model for a list of blocks."""

    pass
