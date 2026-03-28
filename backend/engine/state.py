"""HITL suspend/resume state machine.

Provides suspend_run() and resume_run() for persisting and restoring
execution state when a Human-in-the-Loop block pauses the pipeline.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from blocks.base import HITLBase
from engine.registry import get_block_class
from schemas.execution import (
    NodeExecutionStatus,
    RunState,
    RunStatus,
)
from storage.runs import get_run, update_run

logger = logging.getLogger(__name__)


async def suspend_run(run_state: RunState) -> None:
    """Persist a suspended run state to the database.

    The executor calls this after catching an HITLSuspendSignal.
    The run_state should already have status=SUSPENDED and hitl_checkpoint set.

    Args:
        run_state: The RunState with status=SUSPENDED and hitl_checkpoint populated.
    """
    if run_state.status != RunStatus.SUSPENDED:
        raise ValueError(
            f"Cannot suspend run {run_state.run_id}: status is {run_state.status}, expected SUSPENDED"
        )
    if run_state.hitl_checkpoint is None:
        raise ValueError(f"Cannot suspend run {run_state.run_id}: hitl_checkpoint is None")

    await update_run(run_state)
    logger.info("Run %s suspended at node %s", run_state.run_id, run_state.hitl_checkpoint.node_id)


async def resume_run(run_id: str, human_input: dict[str, Any]) -> RunState:
    """Resume a suspended run by processing the human response.

    Loads the persisted RunState, instantiates the HITL block that caused
    suspension, calls process_response(human_input) to produce output,
    stores that output on the HITL node's outgoing edges, marks the node
    completed, and sets status=RUNNING so execute_pipeline can continue.

    Args:
        run_id: The run identifier string.
        human_input: The human reviewer's response dict.

    Returns:
        Updated RunState with status=RUNNING and edge_data populated.

    Raises:
        ValueError: If the run is not found or not in SUSPENDED status.
        KeyError: If the HITL block class cannot be found in the registry.
    """
    # Load persisted state
    run_state = await get_run(run_id)
    if run_state is None:
        raise LookupError(f"Run {run_id} not found")

    if run_state.status != RunStatus.SUSPENDED:
        raise ValueError(f"Run {run_id} is not suspended (status={run_state.status})")

    checkpoint = run_state.hitl_checkpoint
    if checkpoint is None:
        raise ValueError(f"Run {run_id} is suspended but has no hitl_checkpoint")

    hitl_node_id = checkpoint.node_id

    # We need the pipeline schema to find the node definition and outgoing edges.
    # Import here to avoid circular imports.
    from storage.sqlite import get_pipeline as get_pipeline_from_db

    pipeline = await get_pipeline_from_db(str(run_state.pipeline_id))
    if pipeline is None:
        raise LookupError(f"Pipeline {run_state.pipeline_id} not found")

    # Find the HITL node in the pipeline
    node_schema = None
    for n in pipeline.nodes:
        if str(n.node_id) == hitl_node_id:
            node_schema = n
            break

    if node_schema is None:
        raise ValueError(f"Node {hitl_node_id} not found in pipeline {pipeline.pipeline_id}")

    # Instantiate the HITL block
    block_cls = get_block_class(str(node_schema.block_type), node_schema.block_implementation)
    block = block_cls()

    if not isinstance(block, HITLBase):
        raise ValueError(
            f"Node {hitl_node_id} block {node_schema.block_implementation} is not an HITL block"
        )

    # Process human response to get block output
    output = block.process_response(human_input)

    # Store output on all outgoing edges of the HITL node
    for edge in pipeline.edges:
        if str(edge.source_node) == hitl_node_id:
            run_state.edge_data[str(edge.edge_id)] = output

    # Mark the HITL node as completed
    node_state = run_state.node_states.get(hitl_node_id)
    if node_state is not None:
        node_state.status = NodeExecutionStatus.COMPLETED
        node_state.completed_at = datetime.now(UTC)

    # Update checkpoint with resume timestamp
    checkpoint.resumed_at = datetime.now(UTC)

    # Set status to running so executor can continue
    run_state.status = RunStatus.RUNNING
    run_state.current_node_id = None  # Executor will determine next node

    await update_run(run_state)
    logger.info("Run %s resumed from node %s", run_state.run_id, hitl_node_id)

    return run_state
