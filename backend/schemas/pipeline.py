from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class BlockType(StrEnum):
    SOURCE = "source"
    TRANSFORM = "transform"
    ANALYSIS = "analysis"
    GENERATION = "generation"
    EVALUATION = "evaluation"
    COMPARATOR = "comparator"
    LLM_FLEX = "llm_flex"
    ROUTER = "router"
    HITL = "hitl"
    REPORTING = "reporting"
    SINK = "sink"


class Position(BaseModel):
    x: float
    y: float


class NodeSchema(BaseModel):
    node_id: UUID
    block_type: BlockType
    block_implementation: str
    label: str
    position: Position
    config: dict = Field(default_factory=dict)
    input_schema: list[str] = Field(default_factory=list)
    output_schema: list[str] = Field(default_factory=list)


class EdgeSchema(BaseModel):
    edge_id: UUID
    source_node: UUID
    target_node: UUID
    data_type: str
    validated: bool = False


class TerminationType(StrEnum):
    ROUTER_CONDITION = "router_condition"
    HITL = "hitl"
    MAX_ITERATIONS = "max_iterations"


class TerminationSchema(BaseModel):
    type: TerminationType
    max_iterations: int | None = None
    fallback: str | None = None


class LoopSchema(BaseModel):
    loop_id: UUID
    entry_node: UUID
    exit_node: UUID
    termination: TerminationSchema


class PipelineMetadata(BaseModel):
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    author: str = ""


class PipelineSchema(BaseModel):
    pipeline_id: UUID
    name: str
    version: str = "1.0"
    created_at: datetime
    updated_at: datetime
    nodes: list[NodeSchema] = Field(default_factory=list)
    edges: list[EdgeSchema] = Field(default_factory=list)
    loop_definitions: list[LoopSchema] = Field(default_factory=list)
    metadata: PipelineMetadata = Field(default_factory=PipelineMetadata)


class PipelineCreateRequest(BaseModel):
    name: str
    nodes: list[NodeSchema] = Field(default_factory=list)
    edges: list[EdgeSchema] = Field(default_factory=list)
    loop_definitions: list[LoopSchema] = Field(default_factory=list)
    metadata: PipelineMetadata = Field(default_factory=PipelineMetadata)


class PipelineUpdateRequest(BaseModel):
    name: str | None = None
    nodes: list[NodeSchema] | None = None
    edges: list[EdgeSchema] | None = None
    loop_definitions: list[LoopSchema] | None = None
    metadata: PipelineMetadata | None = None


class ConnectionValidationRequest(BaseModel):
    """Request body for POST /api/v1/pipelines/validate-connection."""

    source_block_type: str
    source_block_implementation: str
    target_block_type: str
    target_block_implementation: str
    data_type: str


class ConnectionValidationResponse(BaseModel):
    """Response for connection validation."""

    valid: bool
    reason: str | None = None


class PipelineValidationResponse(BaseModel):
    """Response for full pipeline validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
