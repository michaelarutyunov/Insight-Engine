"""Co-pilot — LLM-driven pipeline modification.

Accepts a natural-language instruction and the current pipeline JSON, then
asks the LLM to return a *complete* modified pipeline JSON (not a patch).
The frontend diffs the returned JSON against the current state and presents
a confirm/reject dialog before applying changes.

Owned by: llm-integration
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import uuid4

import anthropic

from chat.context_builder import build_pipeline_context

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_MAX_TOKENS = 4096

SYSTEM_PROMPT = """\
You are a pipeline modification assistant for a visual research pipeline IDE.

You will receive:
1. The current pipeline definition (as structured JSON context).
2. A user instruction describing the desired modification.

Your job is to return the **complete modified pipeline JSON** — not a patch,
not a diff, but the full pipeline definition with the requested changes applied.

## Rules

1. **Return ONLY valid pipeline JSON.** No explanatory text, no markdown
   fences. The entire response must be parseable as JSON.
2. **Preserve existing node IDs and edge IDs** for any element that is not
   being removed. This is critical — changing IDs breaks references.
3. **Generate new UUIDs** (as strings) for any new nodes or edges you add.
4. **Preserve the pipeline metadata** (name, version, author, tags, description)
   unless the user explicitly asks to change them.
5. **Maintain valid edge data types.** Every edge's data_type must appear in
   both the source node's output_schema and the target node's input_schema.
6. **Source nodes must have no incoming edges. Sink nodes must have no outgoing edges.**
7. **All new nodes must have valid block_type and block_implementation values**
   from the block catalog.
8. **Set validated: false on any new edges.** The engine will validate them later.
9. **Position new nodes sensibly** — offset them from existing nodes so they
   don't overlap.
10. If the instruction is ambiguous, make the simplest reasonable interpretation.

## Pipeline JSON Schema

{
  "pipeline_id": "uuid-string",
  "name": "string",
  "version": "1.0",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "nodes": [
    {
      "node_id": "uuid-string",
      "block_type": "source|transform|analysis|generation|evaluation|comparator|llm_flex|router|hitl|reporting|sink",
      "block_implementation": "string",
      "label": "string",
      "position": {"x": float, "y": float},
      "config": {},
      "input_schema": ["string"],
      "output_schema": ["string"]
    }
  ],
  "edges": [
    {
      "edge_id": "uuid-string",
      "source_node": "uuid-string",
      "target_node": "uuid-string",
      "data_type": "string",
      "validated": false
    }
  ],
  "loop_definitions": [],
  "metadata": {"description": "string", "tags": ["string"], "author": "string"}
}
"""

USER_PROMPT_TEMPLATE = """\
## Current Pipeline

{pipeline_context}

## Block Catalog (available block implementations)

{block_catalog}

## User Instruction

{instruction}

Return the complete modified pipeline JSON. Remember: ONLY valid JSON, no markdown fences, no explanation.
"""


def _parse_pipeline_json(raw: str) -> dict[str, Any] | None:
    """Attempt to extract and parse a pipeline JSON from the LLM response.

    The LLM may wrap the JSON in markdown fences despite instructions. This
    function tries several extraction strategies:
      1. Direct JSON parse of the full response.
      2. Extract content from ```json ... ``` fences.
      3. Strip any leading/trailing non-JSON text and retry.

    Returns None if no valid JSON can be extracted.
    """
    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract from markdown fences
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: find the outermost { ... } and parse
    brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _ensure_new_ids(pipeline_json: dict[str, Any]) -> dict[str, Any]:
    """Ensure every node and edge in the modified pipeline has a valid UUID.

    The LLM should generate proper UUIDs, but this is a safety net. If any
    node_id or edge_id looks invalid or is an empty string, replace it with
    a freshly generated UUID.
    """
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    id_map: dict[str, str] = {}

    for node in pipeline_json.get("nodes", []):
        nid = node.get("node_id", "")
        if not nid or not uuid_pattern.match(nid):
            new_id = str(uuid4())
            id_map[nid] = new_id
            node["node_id"] = new_id

    for edge in pipeline_json.get("edges", []):
        eid = edge.get("edge_id", "")
        if not eid or not uuid_pattern.match(eid):
            edge["edge_id"] = str(uuid4())

        # Remap source/target if they were in the ID map
        src = edge.get("source_node", "")
        if src in id_map:
            edge["source_node"] = id_map[src]
        tgt = edge.get("target_node", "")
        if tgt in id_map:
            edge["target_node"] = id_map[tgt]

    return pipeline_json


async def modify_pipeline(
    instruction: str,
    pipeline_json: dict[str, Any],
    block_catalog: str | None = None,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    """Send the current pipeline + instruction to the LLM and return a
    complete modified pipeline JSON.

    Parameters
    ----------
    instruction:
        Natural-language description of the desired modification.
    pipeline_json:
        The current pipeline definition as a dict matching PipelineSchema.
    block_catalog:
        Formatted block catalog string from context_builder. If None,
        a minimal catalog note is included.
    model:
        Anthropic model ID.
    max_tokens:
        Max tokens for the LLM response.

    Returns
    -------
    dict
        Complete modified pipeline JSON.

    Raises
    ------
    ValueError
        If the LLM response cannot be parsed as valid pipeline JSON.
    """
    pipeline_context = build_pipeline_context(pipeline_json)

    catalog_section = block_catalog if block_catalog else "(block catalog not available)"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        pipeline_context=pipeline_context,
        block_catalog=catalog_section,
        instruction=instruction,
    )

    client = anthropic.AsyncAnthropic()

    logger.info("Co-pilot: sending modification request (model=%s)", model)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text
    logger.debug("Co-pilot: raw LLM response length=%d", len(raw_text))

    parsed = _parse_pipeline_json(raw_text)
    if parsed is None:
        logger.error("Co-pilot: failed to parse LLM response as JSON")
        raise ValueError(
            "Failed to parse LLM response as pipeline JSON. The model did not return valid JSON."
        )

    # Safety net: ensure all IDs are valid UUIDs
    parsed = _ensure_new_ids(parsed)

    # Carry forward fields the LLM might have dropped
    for field in ("pipeline_id", "created_at"):
        if field not in parsed and field in pipeline_json:
            parsed[field] = pipeline_json[field]

    if "version" not in parsed:
        parsed["version"] = pipeline_json.get("version", "1.0")

    logger.info(
        "Co-pilot: modified pipeline has %d nodes, %d edges",
        len(parsed.get("nodes", [])),
        len(parsed.get("edges", [])),
    )

    return parsed
