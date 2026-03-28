"""Execution run state models for pipeline execution tracking."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeState(BaseModel):
    """Per-node execution state within a run."""

    node_id: str
    status: NodeExecutionStatus = NodeExecutionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class HITLCheckpoint(BaseModel):
    """HITL suspension checkpoint data."""

    node_id: str
    checkpoint_data: dict = Field(default_factory=dict)
    resumed_at: datetime | None = None


class RunState(BaseModel):
    """Full execution run state, persisted to storage."""

    run_id: UUID
    pipeline_id: UUID
    status: RunStatus = RunStatus.PENDING
    current_node_id: str | None = None
    node_states: dict[str, NodeState] = Field(default_factory=dict)
    edge_data: dict[str, dict] = Field(default_factory=dict)
    loop_counters: dict[str, int] = Field(default_factory=dict)
    hitl_checkpoint: HITLCheckpoint | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RunCreateRequest(BaseModel):
    """Request to start a pipeline run."""

    pipeline_id: UUID


class RunResponse(BaseModel):
    """Response returned when triggering a run."""

    run_id: UUID
    status: RunStatus


class RunStatusResponse(BaseModel):
    """Detailed run status for polling."""

    run_id: UUID
    pipeline_id: UUID
    status: RunStatus
    current_node_id: str | None = None
    node_states: dict[str, NodeState] = Field(default_factory=dict)
    hitl_checkpoint: HITLCheckpoint | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunCreateResponse(BaseModel):
    """Response returned immediately after triggering a run."""

    run_id: UUID
    status: RunStatus


class NodeStatusResponse(BaseModel):
    """Per-node status summary for run status response."""

    node_id: str
    status: NodeExecutionStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class RunDetailResponse(BaseModel):
    """Detailed run status with per-node breakdown for polling."""

    run_id: UUID
    pipeline_id: UUID
    status: RunStatus
    current_node_id: str | None = None
    node_statuses: list[NodeStatusResponse] = Field(default_factory=list)
    checkpoint_data: dict | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
