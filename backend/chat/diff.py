"""Pipeline diff utilities for co-pilot mode.

Computes structured diffs between two pipeline definitions, identifying
added/removed nodes and edges. Used by the co-pilot to show what will
change before applying modifications.

Owned by: llm-integration
"""

from __future__ import annotations

from typing import Any

from schemas.chat import EdgeDiff, NodeDiff, PipelineDiff


def _str(val: Any) -> str:
    """Coerce a value (UUID, str, etc.) to a plain string."""
    return str(val)


def compute_pipeline_diff(original: dict[str, Any], modified: dict[str, Any]) -> PipelineDiff:
    """Compute a structured diff between two pipeline definitions.

    Parameters
    ----------
    original:
        The original pipeline dict (PipelineSchema.model_dump()).
        May contain UUID objects -- they are coerced to strings internally.
    modified:
        The modified pipeline dict returned by the LLM.

    Returns
    -------
    PipelineDiff
        Structured diff with added/removed nodes and edges.
    """
    # Coerce all node/edge IDs to strings for safe comparison
    orig_nodes = {_str(n["node_id"]): n for n in original.get("nodes", [])}
    mod_nodes = {_str(n["node_id"]): n for n in modified.get("nodes", [])}

    orig_edges = {_str(e["edge_id"]): e for e in original.get("edges", [])}
    mod_edges = {_str(e["edge_id"]): e for e in modified.get("edges", [])}

    # Find added/removed nodes
    orig_node_ids = set(orig_nodes.keys())
    mod_node_ids = set(mod_nodes.keys())

    added_node_ids = mod_node_ids - orig_node_ids
    removed_node_ids = orig_node_ids - mod_node_ids

    added_nodes = [
        NodeDiff(
            id=nid,
            block_type=_str(mod_nodes[nid]["block_type"]),
            block_implementation=_str(mod_nodes[nid]["block_implementation"]),
            label=_str(mod_nodes[nid].get("label", "")),
            config=mod_nodes[nid].get("config", {}),
            position=(
                mod_nodes[nid].get("position", {}).get("x", 0),
                mod_nodes[nid].get("position", {}).get("y", 0),
            ),
            input_schema=[_str(s) for s in mod_nodes[nid].get("input_schema", [])],
            output_schema=[_str(s) for s in mod_nodes[nid].get("output_schema", [])],
        )
        for nid in added_node_ids
    ]

    removed_nodes = [
        NodeDiff(
            id=nid,
            block_type=_str(orig_nodes[nid]["block_type"]),
            block_implementation=_str(orig_nodes[nid]["block_implementation"]),
            label=_str(orig_nodes[nid].get("label", "")),
            config=orig_nodes[nid].get("config", {}),
            position=(
                orig_nodes[nid].get("position", {}).get("x", 0),
                orig_nodes[nid].get("position", {}).get("y", 0),
            ),
            input_schema=[_str(s) for s in orig_nodes[nid].get("input_schema", [])],
            output_schema=[_str(s) for s in orig_nodes[nid].get("output_schema", [])],
        )
        for nid in removed_node_ids
    ]

    # Find added/removed edges
    orig_edge_ids = set(orig_edges.keys())
    mod_edge_ids = set(mod_edges.keys())

    added_edge_ids = mod_edge_ids - orig_edge_ids
    removed_edge_ids = orig_edge_ids - mod_edge_ids

    added_edges = [
        EdgeDiff(
            id=eid,
            source=_str(mod_edges[eid]["source_node"]),
            target=_str(mod_edges[eid]["target_node"]),
            data_type=_str(mod_edges[eid]["data_type"]),
        )
        for eid in added_edge_ids
    ]

    removed_edges = [
        EdgeDiff(
            id=eid,
            source=_str(orig_edges[eid]["source_node"]),
            target=_str(orig_edges[eid]["target_node"]),
            data_type=_str(orig_edges[eid]["data_type"]),
        )
        for eid in removed_edge_ids
    ]

    return PipelineDiff(
        added_nodes=added_nodes,
        removed_nodes=removed_nodes,
        added_edges=added_edges,
        removed_edges=removed_edges,
    )
