from fastapi import APIRouter, HTTPException

from engine.registry import get_block_info, list_blocks

router = APIRouter(tags=["blocks"])


@router.get("/blocks")
async def list_blocks_endpoint() -> list[dict]:
    """Return all registered block types and implementations with their schemas.

    Feeds the frontend block palette with metadata about available blocks.
    """
    return list_blocks()


@router.get("/blocks/{block_type}/{implementation}")
async def get_block_endpoint(block_type: str, implementation: str) -> dict:
    """Return detailed information about a specific block implementation.

    Raises 404 if the block is not found.
    """
    try:
        return get_block_info(block_type, implementation)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Block type={block_type!r}, implementation={implementation!r} not found",
        ) from None
