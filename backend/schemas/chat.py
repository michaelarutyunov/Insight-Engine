"""Pydantic models for the chat API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /api/v1/chat."""

    message: str = Field(
        ..., min_length=1, description="User's question to the research assistant."
    )
    pipeline_id: str | None = Field(
        default=None,
        description="Optional pipeline ID to include pipeline context.",
    )


class SSEChunk(BaseModel):
    """A single server-sent event chunk."""

    # Invariants: type is one of "token", "done", "error"
    type: str
    content: str = Field(default="", description="Token text, empty for done/error types.")


# ---------------------------------------------------------------------------
# Co-pilot schemas
# ---------------------------------------------------------------------------


class CopilotModifyRequest(BaseModel):
    """Request body for POST /api/v1/chat/modify."""

    message: str = Field(
        ..., min_length=1, description="Natural-language pipeline modification request."
    )
    pipeline_id: str = Field(..., min_length=1, description="ID of the pipeline to modify.")


class NodeDiff(BaseModel):
    """A single node in a pipeline diff (added or removed)."""

    id: str = Field(..., description="Node UUID (as string).")
    block_type: str = Field(..., description="Block type (e.g. source, transform).")
    block_implementation: str = Field(..., description="Concrete block implementation name.")
    label: str = Field(default="", description="Human-readable node label.")
    config: dict[str, Any] = Field(default_factory=dict, description="Block configuration.")
    position: tuple[float, float] = Field(..., description="(x, y) canvas position.")
    input_schema: list[str] = Field(default_factory=list)
    output_schema: list[str] = Field(default_factory=list)


class EdgeDiff(BaseModel):
    """A single edge in a pipeline diff (added or removed)."""

    id: str = Field(..., description="Edge UUID (as string).")
    source: str = Field(..., description="Source node UUID.")
    target: str = Field(..., description="Target node UUID.")
    data_type: str = Field(..., description="Edge data type identifier.")


class PipelineDiff(BaseModel):
    """Structured diff between the current pipeline and the proposed version."""

    added_nodes: list[NodeDiff] = Field(default_factory=list, description="Nodes to add.")
    removed_nodes: list[NodeDiff] = Field(default_factory=list, description="Nodes to remove.")
    added_edges: list[EdgeDiff] = Field(default_factory=list, description="Edges to add.")
    removed_edges: list[EdgeDiff] = Field(default_factory=list, description="Edges to remove.")


class CopilotModifyResponse(BaseModel):
    """Response from the co-pilot modify endpoint."""

    explanation: str = Field(
        ..., description="Human-readable explanation of what was changed and why."
    )
    pipeline_diff: PipelineDiff = Field(
        ..., description="Structured diff to apply to the pipeline."
    )
