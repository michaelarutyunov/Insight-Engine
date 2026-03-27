from fastapi import APIRouter

router = APIRouter(tags=["blocks"])


@router.get("/blocks")
async def list_blocks() -> list:
    raise NotImplementedError


@router.get("/blocks/{implementation}")
async def get_block(implementation: str) -> dict:
    raise NotImplementedError
