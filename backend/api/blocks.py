"""Block catalog API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from engine.registry import get_block_info, list_blocks
from schemas.blocks import BlockInfoResponse, BlockListResponse

router = APIRouter(tags=["blocks"])


@router.get("/blocks", response_model=BlockListResponse)
async def list_blocks_endpoint(
    type: Annotated[str | None, Query(description="Filter blocks by type")] = None,
) -> list[dict]:
    """Return all registered block types and implementations with their schemas.

    Feeds the frontend block palette with metadata about available blocks.

    Args:
        type: Optional block type filter (e.g., "transform", "source")

    Returns:
        List of block info dictionaries. If type is provided, only blocks of that type.
    """
    all_blocks = list_blocks()

    if type is not None:
        return [b for b in all_blocks if b["block_type"] == type]

    return all_blocks


@router.get("/blocks/{block_type}/{implementation}", response_model=BlockInfoResponse)
async def get_block_endpoint(block_type: str, implementation: str) -> dict:
    """Return detailed information about a specific block implementation.

    Args:
        block_type: The block type (e.g., "source", "transform")
        implementation: The block implementation name (e.g., "csv_source")

    Returns:
        Block info with config_schema, input_schemas, output_schemas, description

    Raises:
        404: If the block is not found
    """
    try:
        return get_block_info(block_type, implementation)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Block type={block_type!r}, implementation={implementation!r} not found",
        ) from None
