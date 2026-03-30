"""Context assembly module — shared foundation for all three chat modes.

Provides pure-data formatting functions that produce LLM-consumable context
strings.  Contains **no LLM API calls** — only serialisation and formatting.

Owned by: reasoning-specialist
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine import registry
from reasoning.profiles import ReasoningProfile
from reasoning.workflows import get_workflow_for_block

# Default location of reasoning profiles (relative to backend root).
_PROFILES_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "reasoning_profiles"


# ---------------------------------------------------------------------------
# Pipeline context
# ---------------------------------------------------------------------------


def build_pipeline_context(pipeline_json: dict[str, Any]) -> str:
    """Serialise a pipeline definition dict as a readable context string.

    Parameters
    ----------
    pipeline_json:
        A dict matching the :class:`PipelineSchema` shape (may come from
        ``model_dump()`` or from raw JSON).  The caller is responsible for
        loading the pipeline from storage — this function does **not** touch
        the database.

    Returns
    -------
    str
        Human-readable multi-line description of the pipeline suitable for
        inclusion in an LLM system prompt.
    """
    lines: list[str] = []

    # -- Header ---------------------------------------------------------------
    name = pipeline_json.get("name", "Untitled Pipeline")
    version = pipeline_json.get("version", "1.0")
    lines.append(f"# Pipeline: {name} (v{version})")
    lines.append("")

    meta = pipeline_json.get("metadata", {})
    if meta.get("description"):
        lines.append(f"Description: {meta['description']}")
    if meta.get("author"):
        lines.append(f"Author: {meta['author']}")
    if meta.get("tags"):
        lines.append(f"Tags: {', '.join(meta['tags'])}")
    if any(meta.get(k) for k in ("description", "author", "tags")):
        lines.append("")

    # -- Nodes ---------------------------------------------------------------
    nodes = pipeline_json.get("nodes", [])
    lines.append(f"## Nodes ({len(nodes)})")
    lines.append("")
    for node in nodes:
        label = node.get("label", "unlabeled")
        btype = node.get("block_type", "?")
        bimpl = node.get("block_implementation", "?")
        config = node.get("config", {})
        pos = node.get("position", {})
        pos_str = f" at ({pos.get('x', 0)}, {pos.get('y', 0)})" if pos else ""

        config_str = ""
        if config:
            config_parts = [f"{k}={v!r}" for k, v in config.items()]
            config_str = f" | config: {{{', '.join(config_parts)}}}"

        lines.append(f'  - [{btype}/{bimpl}] "{label}"{pos_str}{config_str}')
    lines.append("")

    # -- Edges ---------------------------------------------------------------
    edges = pipeline_json.get("edges", [])
    lines.append(f"## Edges ({len(edges)})")
    lines.append("")
    for edge in edges:
        src = edge.get("source_node", "?")
        tgt = edge.get("target_node", "?")
        dtype = edge.get("data_type", "?")
        validated = edge.get("validated", False)
        val_str = " (validated)" if validated else ""
        lines.append(f"  - {src} --[{dtype}]--> {tgt}{val_str}")
    lines.append("")

    # -- Loops ---------------------------------------------------------------
    loops = pipeline_json.get("loop_definitions", [])
    if loops:
        lines.append(f"## Loops ({len(loops)})")
        lines.append("")
        for loop in loops:
            lid = loop.get("loop_id", "?")
            entry = loop.get("entry_node", "?")
            exit_node = loop.get("exit_node", "?")
            term = loop.get("termination", {})
            term_type = term.get("type", "?")
            max_iter = term.get("max_iterations")
            max_iter_str = f", max_iterations={max_iter}" if max_iter else ""
            lines.append(
                f"  - Loop {lid}: {entry} -> {exit_node} (terminates: {term_type}{max_iter_str})"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Block catalog context
# ---------------------------------------------------------------------------


def build_block_catalog_context(
    block_type_filter: str | None = None,
) -> str:
    """Format the block catalog for LLM consumption.

    Calls :func:`engine.registry.list_blocks` internally to discover all
    registered blocks.  Each entry includes its description,
    ``methodological_notes``, and — when present — dimensional metadata.

    Parameters
    ----------
    block_type_filter:
        Optional block type to restrict the output (e.g. ``"analysis"``).
        When ``None`` all registered blocks are included.

    Returns
    -------
    str
        Formatted multi-line string describing every matching block.
    """
    blocks = registry.list_blocks()

    if block_type_filter is not None:
        blocks = [b for b in blocks if b.get("block_type") == block_type_filter]

    lines: list[str] = []
    lines.append("# Block Catalog")
    lines.append("")

    if not blocks:
        lines.append("(no blocks registered)")
        return "\n".join(lines)

    for block in sorted(
        blocks, key=lambda b: (b.get("block_type", ""), b.get("block_implementation", ""))
    ):
        btype = block.get("block_type", "?")
        bimpl = block.get("block_implementation", "?")
        desc = block.get("description", "")
        notes = block.get("methodological_notes", "")
        tags = block.get("tags", [])
        input_schemas = block.get("input_schemas", [])
        output_schemas = block.get("output_schemas", [])
        dimensions = block.get("dimensions", {})
        practitioner_workflow = block.get("practitioner_workflow")

        lines.append(f"## {btype}/{bimpl}")
        if desc:
            lines.append(f"Description: {desc}")
        if notes:
            lines.append(f"Methodological notes: {notes}")
        if tags:
            lines.append(f"Tags: {', '.join(tags)}")
        lines.append(f"Input schemas: {input_schemas}")
        lines.append(f"Output schemas: {output_schemas}")

        if dimensions:
            dim_parts = [f"{k}={v}" for k, v in dimensions.items()]
            lines.append(f"Dimensions: {{{', '.join(dim_parts)}}}")

        if practitioner_workflow is not None:
            lines.append(f"Practitioner workflow: {practitioner_workflow}")

        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Advisor context
# ---------------------------------------------------------------------------


def build_advisor_context(
    profile: ReasoningProfile,
    candidates: list[dict[str, Any]] | None = None,
    base_dir: Path | None = None,
) -> str:
    """Assemble reasoning profile preferences, candidate summaries, and
    practitioner workflow text for advisor Stage 3.

    Parameters
    ----------
    profile:
        The loaded :class:`ReasoningProfile` providing dimension weights
        and methodological preferences.
    candidates:
        Optional list of candidate dicts (shaped like
        :class:`MethodCandidate`).  Each should contain at least
        ``block_implementation``, ``block_type``, ``fit_score``,
        ``fit_reasoning``, ``tradeoffs``, and ``dimensions``.
    base_dir:
        Root directory for resolving practitioner workflow files.
        Defaults to ``reasoning_profiles/`` at the project root.

    Returns
    -------
    str
        Assembled context string ready for inclusion in the Stage 3 prompt.
    """
    if base_dir is None:
        base_dir = _PROFILES_BASE_DIR

    lines: list[str] = []

    # -- Profile preferences --------------------------------------------------
    lines.append("# Reasoning Profile")
    lines.append("")
    lines.append(f"Name: {profile.name}")
    lines.append(f"Version: {profile.version}")
    lines.append(f"Description: {profile.description}")
    lines.append("")

    lines.append("## Dimension Weights")
    for dim, weight in profile.dimension_weights.items():
        lines.append(f"  {dim}: {weight}")
    lines.append("")

    prefs = profile.preferences
    lines.append("## Methodological Preferences")
    lines.append(f"  Default stance: {prefs.default_stance}")
    lines.append(f"  Transparency threshold: {prefs.transparency_threshold}")
    lines.append(f"  Prefer established methods: {prefs.prefer_established}")
    lines.append("")

    # -- Candidates -----------------------------------------------------------
    if candidates:
        lines.append(f"# Method Candidates ({len(candidates)})")
        lines.append("")

        for idx, cand in enumerate(candidates, 1):
            bimpl = cand.get("block_implementation", "?")
            btype = cand.get("block_type", "?")
            score = cand.get("fit_score", 0.0)
            reasoning = cand.get("fit_reasoning", "")
            tradeoffs = cand.get("tradeoffs", "")
            dims = cand.get("dimensions", {})

            lines.append(f"## Candidate {idx}: {btype}/{bimpl}")
            lines.append(f"Fit score: {score}")
            if reasoning:
                lines.append(f"Fit reasoning: {reasoning}")
            if tradeoffs:
                lines.append(f"Tradeoffs: {tradeoffs}")
            if dims:
                dim_parts = [f"{k}={v}" for k, v in dims.items()]
                lines.append(f"Dimensions: {{{', '.join(dim_parts)}}}")
            lines.append("")

        # -- Practitioner workflow for top candidate -------------------------
        top_impl = candidates[0].get("block_implementation", "")
        workflow_text = get_workflow_for_block(top_impl, profile, base_dir)
        if workflow_text:
            lines.append("# Practitioner Workflow (top candidate)")
            lines.append("")
            lines.append(workflow_text)
            lines.append("")

    return "\n".join(lines)
