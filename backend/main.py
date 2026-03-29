from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import blocks, execution, hitl, pipelines
from storage.runs import init_db as init_runs_db
from storage.sqlite import _get_connection as _init_pipeline_db


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup: ensure database tables exist."""
    db = await _init_pipeline_db()
    await db.close()
    await init_runs_db()
    yield


app = FastAPI(title="Insights IDE API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipelines.router, prefix="/api/v1")
app.include_router(blocks.router, prefix="/api/v1")
app.include_router(execution.router, prefix="/api/v1")
app.include_router(hitl.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
