from fastapi import APIRouter

router = APIRouter(tags=["execution"])


@router.post("/execution/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str) -> dict:
    raise NotImplementedError


@router.get("/execution/{job_id}/status")
async def get_job_status(job_id: str) -> dict:
    raise NotImplementedError
