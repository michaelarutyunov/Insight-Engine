"""Chat API -- POST /api/v1/chat for streaming research assistant responses.

Uses SSE via FastAPI StreamingResponse to stream LLM responses.
 Uses context_builder for pipeline context and block catalog context as system prompt.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from chat import copilot
from chat.assistant import stream_chat
from chat.context_builder import build_block_catalog_context
from chat.diff import compute_pipeline_diff
from schemas.chat import ChatRequest, CopilotModifyRequest, CopilotModifyResponse
from storage import sqlite as storage

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat_endpoint(body: ChatRequest) -> StreamingResponse:
    """Stream a research assistant response.

    Accepts a user message and optional pipeline_id.
    Returns SSE stream with JSON chunks: {type, content}.
    """
    return StreamingResponse(
        stream_chat(message=body.message, pipeline_id=body.pipeline_id),
        media_type="text/event-stream",
    )


@router.post("/chat/modify", response_model=CopilotModifyResponse)
async def modify_pipeline_endpoint(body: CopilotModifyRequest) -> CopilotModifyResponse:
    """Co-pilot: modify a pipeline based on natural-language instruction.

    Accepts an instruction and pipeline_id, loads the current pipeline,
    sends it to the LLM with context, and returns a structured diff
    showing what will change.

    The frontend should present this diff to the user for confirmation
    before applying the changes.
    """
    # Load the current pipeline
    pipeline = await storage.get_pipeline(body.pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Pipeline {body.pipeline_id} not found")

    # Build context for the LLM
    pipeline_json = pipeline.model_dump()
    block_catalog = build_block_catalog_context()

    # Call the co-pilot to get a modified pipeline
    try:
        modified_json = await copilot.modify_pipeline(
            instruction=body.message,
            pipeline_json=pipeline_json,
            block_catalog=block_catalog,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Compute the diff
    pipeline_diff = compute_pipeline_diff(pipeline_json, modified_json)

    # Generate a brief explanation
    explanation_parts = []
    if pipeline_diff.added_nodes:
        explanation_parts.append(f"Add {len(pipeline_diff.added_nodes)} node(s)")
    if pipeline_diff.removed_nodes:
        explanation_parts.append(f"Remove {len(pipeline_diff.removed_nodes)} node(s)")
    if pipeline_diff.added_edges:
        explanation_parts.append(f"Add {len(pipeline_diff.added_edges)} edge(s)")
    if pipeline_diff.removed_edges:
        explanation_parts.append(f"Remove {len(pipeline_diff.removed_edges)} edge(s)")

    if not explanation_parts:
        explanation = "No changes were made to the pipeline."
    else:
        explanation = "Proposed changes: " + ", ".join(explanation_parts) + "."

    return CopilotModifyResponse(
        explanation=explanation,
        pipeline_diff=pipeline_diff,
    )
