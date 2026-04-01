"""Research assistant -- streams LLM responses using Anthropic API.

Accepts a user message and optional pipeline context, streams the research methodology answer back as server-sent events (SSE).

 Each SSE chunk is a JSON object: {type, token|done|error, content: str}.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import anthropic

from chat.context_builder import build_block_catalog_context, build_pipeline_context
from storage.sqlite import get_pipeline

logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# System prompt for the research assistant
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_BASE = """\
You are the Insight Engine research assistant -- an expert in research methodology, \
statistical analysis, and insights workflow design.
 You help researchers plan and refine their analytical pipelines. You can:
 - Recommend research methods and analytical approaches
 - Explain methodological concepts and tradeoffs
 - Suggest pipeline structures and block configurations
 - Interpret analysis results and recommend next steps

 Always be specific, practical, and grounded in real methodology. When discussing \
blocks from the catalog, reference them by their exact type/implementation names."""
_CLIENT: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    """Return a lazily-cached Anthropic async client."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.AsyncAnthropic()
    return _CLIENT


def _build_system_prompt(pipeline_json: dict | None = None) -> str:
    """Build the system prompt string for the research assistant.
    Always includes the block catalog.  Optionally includes pipeline
    context when *pipeline_json* is provided.
    """
    parts: list[str] = []
    # Always include the block catalog
    catalog_context = build_block_catalog_context()
    parts.append(f"<block_catalog>\n{catalog_context}\n</block_catalog>")
    # Optionally include pipeline context
    if pipeline_json is not None:
        pipeline_context = build_pipeline_context(pipeline_json)
        parts.append(f"<pipeline_context>\n{pipeline_context}\n</pipeline_context>")
    return _SYSTEM_PROMPT_BASE + "\n\n" + "\n".join(parts)


async def stream_chat(
    message: str,
    pipeline_id: str | None = None,
) -> AsyncIterator[str, None]:
    """Stream the research assistant response as SSE chunks.

       Yields JSON-encoded strings, each shaped as:
           {"type": "token", "content": "..."} during streaming,
           {"type": "done", "content": ""} when the stream completes,
           {"type": "error", "content": "..."} on failure.
    Parameters
       ----------
       message:
           The user's question.
       pipeline_id:
           Optional pipeline ID to include pipeline context.
    """
    client = _get_client()
    # Resolve pipeline context if pipeline_id provided
    pipeline_json: dict | None = None
    if pipeline_id is not None:
        pipeline_data = await get_pipeline(pipeline_id)
        if pipeline_data is not None:
            pipeline_json = pipeline_data.model_dump()
        else:
            logger.warning(
                "Pipeline %s not found; proceeding without pipeline context",
                pipeline_id,
            )
    system_prompt = _build_system_prompt(pipeline_json)
    try:
        async with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": message}],
        ) as stream:
            async for text in stream.text_stream:
                yield json.dumps({"type": "token", "content": text}) + "\n"
        # Signal completion
        yield json.dumps({"type": "done", "content": ""}) + "\n"
    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        yield json.dumps({"type": "error", "content": str(exc)}) + "\n"
    except Exception as exc:
        logger.error("Unexpected error in stream_chat: %s", exc)
        yield json.dumps({"type": "error", "content": str(exc)}) + "\n"
