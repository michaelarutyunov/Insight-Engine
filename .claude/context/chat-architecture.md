# Chat Architecture

## Overview

The chat panel exposes three interaction modes on top of the same pipeline context. All three use `context_builder.py` to assemble LLM-consumable context before making API calls.

```
frontend chat panel
        │
        ├── POST /api/v1/chat              → research assistant (streaming)
        ├── POST /api/v1/chat/modify       → co-pilot (pipeline diff)
        └── POST /api/v1/advise/*          → research advisor (3-stage)
                                                │
                                        backend/chat/
                                        ├── context_builder.py   ← shared foundation
                                        ├── assistant.py         ← research assistant
                                        ├── copilot.py           ← co-pilot
                                        └── research_advisor.py  ← advisor stages
```

---

## `context_builder.py` — Shared Foundation

**Owned by: reasoning-specialist**

This module assembles LLM context strings. It contains **no LLM calls** — pure context assembly. All three chat modes call it before constructing their prompts.

```python
# backend/chat/context_builder.py

def build_pipeline_context(pipeline_id: str) -> str:
    """Serializes current pipeline JSON as readable context for the LLM."""
    # Loads pipeline from DB, formats as human-readable node/edge description
    # Used by: assistant mode, co-pilot mode

def build_block_catalog_context(block_type_filter: str | None = None) -> str:
    """Formats block catalog (with descriptions, methodological_notes, dimensions) for LLM."""
    # Calls engine.registry.list_blocks()
    # Used by: assistant mode, advisor Stage 2

def build_advisor_context(
    profile: ReasoningProfile,
    candidates: list[MethodCandidate] | None = None,
) -> str:
    """Assembles reasoning profile preferences + candidate methods + practitioner workflows."""
    # Calls reasoning.workflows.get_workflow_for_block() for top candidate
    # Used by: advisor Stage 3
```

**Key rule**: `context_builder.py` must not import from `research_advisor.py` and must not make LLM calls. It is a pure data-formatting utility.

---

## Three Chat Modes

### 1. Research Assistant (`assistant.py`)

**Purpose**: LLM answers free-form research methodology questions.

**Context**: `build_pipeline_context()` (if `pipeline_id` provided) + `build_block_catalog_context()`

**Streaming**: Use `AsyncAnthropic` with `client.messages.stream()` and yield chunks as server-sent events. `max_tokens=4096`.

**Request**: `POST /api/v1/chat`
```json
{ "message": "What sampling approach should I use for a concept test?", "pipeline_id": "opt" }
```
**Response**: SSE stream of text chunks.

### 2. Co-Pilot (`copilot.py`)

**Purpose**: LLM reads the current pipeline and proposes a targeted modification.

**Context**: `build_pipeline_context(pipeline_id)`

**Flow**:
1. LLM receives: system context (pipeline JSON) + user instruction
2. LLM returns: a structured `PipelineDiff` (nodes to add/remove/modify, edges to add/remove)
3. Backend validates the diff against block contracts
4. Frontend shows confirmation dialog; user applies or rejects

**Request**: `POST /api/v1/chat/modify`
```json
{ "instruction": "Add a weighting step before the analysis", "pipeline_id": "abc123" }
```
**Response**: `PipelineDiff` — never auto-applied; user must confirm.

### 3. Research Advisor (`research_advisor.py`)

**Purpose**: 3-stage agentic reasoning to recommend an analytical method.

**Stages** (sequential — each feeds the next):
1. `POST /api/v1/advise/characterize` → `ProblemProfile` (dimensions + `SituationalContext`)
2. `POST /api/v1/advise/match` → `List[MethodCandidate]` (3–6 ranked)
3. `POST /api/v1/advise/recommend` → `Recommendation` (method + rationale + pipeline sketch)

**Context used**:
- Stage 1: dimension definitions + situational attribute vocabulary
- Stage 2: filtered block catalog (from `build_block_catalog_context()`) + `SituationalContext`
- Stage 3: `build_advisor_context(profile, candidates)` — includes practitioner workflow

**Not streamed** — all advisor responses are complete JSON payloads.

---

## Ownership Boundaries

| File | Owner | Calls |
|------|-------|-------|
| `context_builder.py` | reasoning-specialist | `engine.registry`, `reasoning.workflows` |
| `research_advisor.py` | reasoning-specialist | `context_builder`, `AsyncAnthropic` |
| `assistant.py` | llm-integration | `context_builder` |
| `copilot.py` | llm-integration | `context_builder` |
| `backend/api/advise.py` | reasoning-specialist | `research_advisor` |
| `backend/api/chat.py` | llm-integration | `assistant`, `copilot` |
| `frontend/src/components/chat-panel/` | canvas-specialist | `/api/v1/chat`, `/api/v1/advise` |

---

## Streaming Implementation (FastAPI)

```python
from fastapi.responses import StreamingResponse

async def stream_chat(message: str, pipeline_id: str | None):
    async def generate():
        async with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_context,
            messages=[{"role": "user", "content": message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    return StreamingResponse(generate(), media_type="text/plain")
```

Frontend consumes via `ReadableStream` — see `canvas-specialist/AGENT.md` for the TypeScript pattern.

---

## Dependency Graph

```
context_builder.py
    ├── assistant.py (chat endpoint)
    ├── copilot.py (modify endpoint)
    └── research_advisor.py
            ├── Stage 1: characterize()
            ├── Stage 2: match_candidates()  ← depends on Stage 1 output
            └── Stage 3: recommend()         ← depends on Stage 2 output
```

Build order: `context_builder.py` → advisor stages → advise API wire-up → chat assistant/copilot (parallel with advisor).
