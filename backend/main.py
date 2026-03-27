from fastapi import FastAPI

from api import blocks, execution, hitl, pipelines

app = FastAPI(title="Insights IDE API", version="0.1.0")

app.include_router(pipelines.router, prefix="/api/v1")
app.include_router(blocks.router, prefix="/api/v1")
app.include_router(execution.router, prefix="/api/v1")
app.include_router(hitl.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
