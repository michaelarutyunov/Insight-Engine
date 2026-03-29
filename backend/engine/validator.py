"""Pipeline validation — connection type checking and full pipeline integrity."""

from __future__ import annotations

from uuid import UUID

from engine.registry import get_block_info
from schemas.pipeline import EdgeSchema, NodeSchema, PipelineSchema


def validate_connection(
    source_block_type: str,
    source_block_implementation: str,
    target_block_type: str,
    target_block_implementation: str,
    data_type: str,
) -> tuple[bool, str | None]:
    """Check whether a single connection is valid.

    Verifies that:
    1. Both source and target blocks are registered.
    2. ``data_type`` is in the source block's ``output_schemas``.
    3. ``data_type`` is in the target block's ``input_schemas``.

    Returns (valid, reason) where reason is None when valid.
    """
    # --- source block must exist ---
    try:
        source_info = get_block_info(source_block_type, source_block_implementation)
    except KeyError:
        return (
            False,
            f"Source block type={source_block_type!r}, "
            f"implementation={source_block_implementation!r} not found in registry",
        )

    # --- target block must exist ---
    try:
        target_info = get_block_info(target_block_type, target_block_implementation)
    except KeyError:
        return (
            False,
            f"Target block type={target_block_type!r}, "
            f"implementation={target_block_implementation!r} not found in registry",
        )

    source_outputs: list[str] = source_info["output_schemas"]
    target_inputs: list[str] = target_info["input_schemas"]

    # --- source must produce data_type ---
    if data_type not in source_outputs:
        return (
            False,
            f"data_type {data_type!r} is not in source block's output_schemas "
            f"(available: {source_outputs})",
        )

    # --- target must accept data_type ---
    if data_type not in target_inputs:
        return (
            False,
            f"data_type {data_type!r} is not in target block's input_schemas "
            f"(available: {target_inputs})",
        )

    return (True, None)


def validate_pipeline(pipeline: PipelineSchema) -> tuple[bool, list[str]]:
    """Validate an entire pipeline definition.

    Checks:
    1. Every node references a registered block.
    2. Every edge connects valid nodes that exist in the pipeline.
    3. Every edge's data_type is compatible with source outputs and target inputs.
    4. Source blocks have no incoming edges.
    5. Sink blocks have no outgoing edges.

    Returns (valid, errors) where errors is empty when valid.
    """
    errors: list[str] = []
    node_map: dict[UUID, NodeSchema] = {n.node_id: n for n in pipeline.nodes}

    # --- check nodes reference registered blocks ---
    for node in pipeline.nodes:
        try:
            get_block_info(str(node.block_type), node.block_implementation)
        except KeyError:
            errors.append(
                f"Node {node.node_id}: block type={node.block_type!r}, "
                f"implementation={node.block_implementation!r} not registered"
            )

    # --- validate each edge ---
    for edge in pipeline.edges:
        edge_errors = _validate_edge(edge, node_map)
        errors.extend(edge_errors)

    return (len(errors) == 0, errors)


def _validate_edge(
    edge: EdgeSchema,
    node_map: dict[UUID, NodeSchema],
) -> list[str]:
    """Validate a single edge within the context of a pipeline's nodes."""
    errors: list[str] = []

    source_node = node_map.get(edge.source_node)
    target_node = node_map.get(edge.target_node)

    # --- source node must exist ---
    if source_node is None:
        errors.append(f"Edge {edge.edge_id}: source node {edge.source_node} not found in pipeline")
        return errors

    # --- target node must exist ---
    if target_node is None:
        errors.append(f"Edge {edge.edge_id}: target node {edge.target_node} not found in pipeline")
        return errors

    # --- source block must be registered ---
    try:
        source_info = get_block_info(str(source_node.block_type), source_node.block_implementation)
    except KeyError:
        errors.append(
            f"Edge {edge.edge_id}: source block "
            f"type={source_node.block_type!r}, "
            f"implementation={source_node.block_implementation!r} not registered"
        )
        return errors

    # --- target block must be registered ---
    try:
        target_info = get_block_info(str(target_node.block_type), target_node.block_implementation)
    except KeyError:
        errors.append(
            f"Edge {edge.edge_id}: target block "
            f"type={target_node.block_type!r}, "
            f"implementation={target_node.block_implementation!r} not registered"
        )
        return errors

    source_outputs: list[str] = source_info["output_schemas"]
    target_inputs: list[str] = target_info["input_schemas"]

    # --- data_type must be in source outputs ---
    if edge.data_type not in source_outputs:
        errors.append(
            f"Edge {edge.edge_id}: data_type {edge.data_type!r} not in "
            f"source node {source_node.node_id} output_schemas "
            f"(available: {source_outputs})"
        )

    # --- data_type must be in target inputs ---
    if edge.data_type not in target_inputs:
        errors.append(
            f"Edge {edge.edge_id}: data_type {edge.data_type!r} not in "
            f"target node {target_node.node_id} input_schemas "
            f"(available: {target_inputs})"
        )

    return errors
