from fastapi import APIRouter

router = APIRouter(tags=["hitl"])


@router.post("/hitl/{run_id}/respond")
async def submit_hitl_response(run_id: str) -> dict:
    raise NotImplementedError
