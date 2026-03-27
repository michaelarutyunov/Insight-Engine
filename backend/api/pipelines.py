from fastapi import APIRouter

router = APIRouter(tags=["pipelines"])


@router.get("/pipelines")
async def list_pipelines() -> list:
    raise NotImplementedError


@router.post("/pipelines")
async def create_pipeline() -> dict:
    raise NotImplementedError


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str) -> dict:
    raise NotImplementedError


@router.put("/pipelines/{pipeline_id}")
async def update_pipeline(pipeline_id: str) -> dict:
    raise NotImplementedError


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str) -> dict:
    raise NotImplementedError


@router.post("/pipelines/validate")
async def validate_pipeline() -> dict:
    raise NotImplementedError
