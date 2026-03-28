"""Core graph walker — traverses a validated pipeline and executes blocks in dependency order."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from blocks._llm_client import BlockExecutionError, HITLSuspendSignal
from blocks.base import HITLBase, RouterBase
from engine.loop_controller import LoopController
from engine.registry import get_block_class
from schemas.execution import (
    HITLCheckpoint,
    NodeExecutionStatus,
    NodeState,
    RunState,
    RunStatus,
)
from schemas.pipeline import PipelineSchema
from storage.runs import update_run

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Raised when the executor encounters an unrecoverable error."""


def _build_adjacency(
    pipeline: PipelineSchema,
) -> tuple[
    dict[str, list[str]],  # forward adjacency: node_id -> [target_node_ids]
    dict[str, list[str]],  # reverse adjacency: node_id -> [source_node_ids]
    dict[str, set[str]],  # outgoing edges per node: node_id -> {edge_ids}
    dict[str, set[str]],  # incoming edges per node: node_id -> {edge_ids}
]:
    """Build adjacency lists and edge maps from pipeline edges."""
    forward: dict[str, list[str]] = defaultdict(list)
    reverse: dict[str, list[str]] = defaultdict(list)
    outgoing_edges: dict[str, set[str]] = defaultdict(set)
    incoming_edges: dict[str, set[str]] = defaultdict(set)

    # Collect back-edge node pairs from loop definitions so we can exclude them
    # from the topological sort (they create cycles).
    back_edge_pairs: set[tuple[str, str]] = set()
    for loop_def in pipeline.loop_definitions:
        # The back-edge goes from exit_node back to entry_node.
        back_edge_pairs.add((str(loop_def.exit_node), str(loop_def.entry_node)))

    for edge in pipeline.edges:
        src = str(edge.source_node)
        tgt = str(edge.target_node)
        eid = str(edge.edge_id)

        # Always track edges for input collection
        outgoing_edges[src].add(eid)
        incoming_edges[tgt].add(eid)

        # Only add to structural adjacency if not a back-edge
        if (src, tgt) not in back_edge_pairs:
            forward[src].append(tgt)
            reverse[tgt].append(src)

    return forward, reverse, outgoing_edges, incoming_edges


def _topological_sort(
    node_ids: list[str],
    forward: dict[str, list[str]],
    reverse: dict[str, list[str]],
) -> list[str]:
    """Kahn's algorithm for topological sort.

    Returns nodes in execution order. Raises ExecutionError on cycles.
    """
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    for nid in node_ids:
        for tgt in forward.get(nid, []):
            if tgt in in_degree:
                in_degree[tgt] += 1

    queue: list[str] = [nid for nid in node_ids if in_degree[nid] == 0]
    result: list[str] = []

    while queue:
        # Sort for deterministic ordering
        queue.sort()
        node = queue.pop(0)
        result.append(node)
        for tgt in forward.get(node, []):
            if tgt in in_degree:
                in_degree[tgt] -= 1
                if in_degree[tgt] == 0:
                    queue.append(tgt)

    if len(result) != len(node_ids):
        raise ExecutionError("Pipeline contains a cycle that is not declared in loop_definitions")

    return result


def _find_parallel_groups(
    order: list[str],
    reverse: dict[str, list[str]],
    node_states: dict[str, NodeState],
) -> list[list[str]]:
    """Group topologically-sorted nodes into parallel execution layers.

    Nodes in the same layer have all dependencies satisfied and can run concurrently.
    """
    # Map node to its position in the topological order
    position: dict[str, int] = {nid: i for i, nid in enumerate(order)}
    layers: list[list[str]] = []
    node_to_layer: dict[str, int] = {}

    for nid in order:
        deps = reverse.get(nid, [])
        layer = 0 if not deps else max(node_to_layer.get(d, 0) for d in deps if d in position) + 1

        node_to_layer[nid] = layer
        while len(layers) <= layer:
            layers.append([])
        layers[layer].append(nid)

    return layers


async def execute_pipeline(
    pipeline: PipelineSchema,
    run_id: str,
    run_state: RunState,
) -> RunState:
    """Execute a validated pipeline definition.

    This is the core graph walker. It:
    1. Builds adjacency lists from pipeline edges (treating loop back-edges as
       non-structural for topological sort).
    2. Topologically sorts nodes.
    3. Groups independent nodes into parallel layers.
    4. For each layer, executes all ready nodes concurrently via asyncio.gather.
    5. Handles Router conditional edges, HITL suspension, and block failures.

    Args:
        pipeline: A validated PipelineSchema.
        run_id: The run identifier (string form of UUID).
        run_state: Pre-created RunState (status=PENDING). Will be mutated and persisted.

    Returns:
        The final RunState after execution completes, suspends, or fails.
    """
    # --- Build graph structures ---
    forward, reverse, outgoing_edges, incoming_edges = _build_adjacency(pipeline)

    node_ids = [str(n.node_id) for n in pipeline.nodes]
    node_map = {str(n.node_id): n for n in pipeline.nodes}
    edge_map = {str(e.edge_id): e for e in pipeline.edges}

    # Build reverse lookup: edge_id -> (source_node_id, target_node_id)
    edge_endpoints: dict[str, tuple[str, str]] = {
        str(e.edge_id): (str(e.source_node), str(e.target_node)) for e in pipeline.edges
    }

    # --- Initialize node states ---
    for nid in node_ids:
        if nid not in run_state.node_states:
            run_state.node_states[nid] = NodeState(node_id=nid)

    # --- Topological sort ---
    try:
        order = _topological_sort(node_ids, forward, reverse)
    except ExecutionError as e:
        run_state.status = RunStatus.FAILED
        run_state.error = str(e)
        run_state.completed_at = datetime.now(UTC)
        await update_run(run_state)
        return run_state

    # --- Initialize loop controller ---
    loop_defs = [ld.model_dump() for ld in pipeline.loop_definitions]
    loop_controller = LoopController(loop_defs)

    # --- Mark run as running ---
    run_state.status = RunStatus.RUNNING
    run_state.started_at = datetime.now(UTC)
    await update_run(run_state)

    # --- Track inactive edges (from Router decisions) ---
    inactive_edges: set[str] = set()

    # --- Group into parallel layers ---
    layers = _find_parallel_groups(order, reverse, run_state.node_states)

    # --- Execute layer by layer ---
    for layer in layers:
        # Filter out nodes whose incoming edges are all inactive (skipped)
        ready_nodes: list[str] = []
        for nid in layer:
            node_incoming = incoming_edges.get(nid, set())
            if node_incoming and node_incoming.issubset(inactive_edges):
                # All incoming edges are inactive — skip this node
                run_state.node_states[nid].status = NodeExecutionStatus.SKIPPED
                # Mark all outgoing edges as inactive too
                for eid in outgoing_edges.get(nid, set()):
                    inactive_edges.add(eid)
                continue
            ready_nodes.append(nid)

        if not ready_nodes:
            continue

        # Execute all ready nodes in parallel
        if len(ready_nodes) == 1:
            result = await _execute_node(
                node_id=ready_nodes[0],
                pipeline=pipeline,
                node_map=node_map,
                edge_map=edge_map,
                edge_endpoints=edge_endpoints,
                incoming_edges=incoming_edges,
                outgoing_edges=outgoing_edges,
                inactive_edges=inactive_edges,
                run_state=run_state,
                loop_controller=loop_controller,
            )
            if result == "suspended":
                await update_run(run_state)
                return run_state
            if result == "failed":
                run_state.status = RunStatus.FAILED
                run_state.completed_at = datetime.now(UTC)
                await update_run(run_state)
                return run_state
        else:
            tasks = [
                _execute_node(
                    node_id=nid,
                    pipeline=pipeline,
                    node_map=node_map,
                    edge_map=edge_map,
                    edge_endpoints=edge_endpoints,
                    incoming_edges=incoming_edges,
                    outgoing_edges=outgoing_edges,
                    inactive_edges=inactive_edges,
                    run_state=run_state,
                    loop_controller=loop_controller,
                )
                for nid in ready_nodes
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    nid = ready_nodes[i]
                    run_state.node_states[nid].status = NodeExecutionStatus.FAILED
                    run_state.node_states[nid].error = str(res)
                    run_state.node_states[nid].completed_at = datetime.now(UTC)
                    run_state.status = RunStatus.FAILED
                    run_state.error = f"Node {nid} failed: {res}"
                    run_state.completed_at = datetime.now(UTC)
                    await update_run(run_state)
                    return run_state
                if res == "suspended":
                    await update_run(run_state)
                    return run_state
                if res == "failed":
                    run_state.status = RunStatus.FAILED
                    run_state.completed_at = datetime.now(UTC)
                    await update_run(run_state)
                    return run_state

    # --- All nodes executed successfully ---
    run_state.status = RunStatus.COMPLETED
    run_state.completed_at = datetime.now(UTC)
    run_state.current_node_id = None
    await update_run(run_state)
    return run_state


async def _execute_node(
    node_id: str,
    pipeline: PipelineSchema,
    node_map: dict[str, Any],
    edge_map: dict[str, Any],
    edge_endpoints: dict[str, tuple[str, str]],
    incoming_edges: dict[str, set[str]],
    outgoing_edges: dict[str, set[str]],
    inactive_edges: set[str],
    run_state: RunState,
    loop_controller: LoopController,
) -> str:
    """Execute a single node. Returns 'ok', 'suspended', or 'failed'."""
    node_schema = node_map[node_id]
    node_state = run_state.node_states[node_id]

    # --- Mark running ---
    node_state.status = NodeExecutionStatus.RUNNING
    node_state.started_at = datetime.now(UTC)
    run_state.current_node_id = node_id

    # --- Collect inputs from upstream edges ---
    inputs: dict[str, Any] = {}
    for eid in incoming_edges.get(node_id, set()):
        if eid in inactive_edges:
            continue
        if eid in run_state.edge_data:
            edge = edge_map[eid]
            data_type = edge.data_type
            inputs[data_type] = run_state.edge_data[eid]

    # --- Inject execution context ---
    inputs["_execution_context"] = {
        "run_id": str(run_state.run_id),
        "pipeline_id": str(run_state.pipeline_id),
        "node_id": node_id,
    }

    # --- Instantiate block ---
    try:
        block_cls = get_block_class(str(node_schema.block_type), node_schema.block_implementation)
        block = block_cls()
    except KeyError as e:
        node_state.status = NodeExecutionStatus.FAILED
        node_state.error = f"Block not found: {e}"
        node_state.completed_at = datetime.now(UTC)
        run_state.error = f"Node {node_id}: block not found: {e}"
        return "failed"

    # --- Validate config ---
    try:
        block.validate_config(node_schema.config)
    except Exception as e:
        node_state.status = NodeExecutionStatus.FAILED
        node_state.error = f"Config validation failed: {e}"
        node_state.completed_at = datetime.now(UTC)
        run_state.error = f"Node {node_id}: config validation failed: {e}"
        return "failed"

    # --- Execute block ---
    try:
        # For HITL blocks, handle suspension
        if isinstance(block, HITLBase):
            checkpoint_data = block.render_checkpoint(inputs)
            run_state.status = RunStatus.SUSPENDED
            run_state.hitl_checkpoint = HITLCheckpoint(
                node_id=node_id,
                checkpoint_data=checkpoint_data,
            )
            node_state.status = NodeExecutionStatus.RUNNING  # Still running, waiting
            return "suspended"

        output = await block.execute(inputs, node_schema.config)

    except HITLSuspendSignal as sig:
        run_state.status = RunStatus.SUSPENDED
        run_state.hitl_checkpoint = HITLCheckpoint(
            node_id=node_id,
            checkpoint_data=sig.checkpoint_data,
        )
        node_state.status = NodeExecutionStatus.RUNNING
        return "suspended"

    except (BlockExecutionError, Exception) as e:
        node_state.status = NodeExecutionStatus.FAILED
        node_state.error = str(e)
        node_state.completed_at = datetime.now(UTC)
        run_state.error = f"Node {node_id} failed: {e}"
        logger.error("Node %s failed: %s", node_id, e)
        return "failed"

    # --- Store outputs on outgoing edges ---
    for eid in outgoing_edges.get(node_id, set()):
        if eid not in inactive_edges:
            run_state.edge_data[eid] = output

    # --- Handle Router: deactivate non-selected edges ---
    if isinstance(block, RouterBase):
        selected_edges = block.resolve_route(output)
        selected_set = set(selected_edges)
        for eid in outgoing_edges.get(node_id, set()):
            if eid not in selected_set:
                inactive_edges.add(eid)

    # --- Mark completed ---
    node_state.status = NodeExecutionStatus.COMPLETED
    node_state.completed_at = datetime.now(UTC)

    return "ok"
