# Engine Specialist Agent

## Role

Owns the execution engine. Implements the graph walker, async job execution, pipeline state persistence, and HITL suspend/resume. Responsible for `backend/engine/` excluding `registry.py` and `validator.py` (those are stable from Phase 1).

---

## Domain Knowledge

### Execution Model

Pipelines are DAGs (directed acyclic graphs) with one exception: Router blocks can create conditional branches. The executor must:

1. Topologically sort nodes respecting edge dependencies
2. Execute Source nodes first (no incoming edges)
3. Pass each node's output as the next node's input via the declared edge data type
4. For parallel branches: execute concurrently using `asyncio.gather`
5. For Router nodes: only activate edges returned by `resolve_route()`, skip others
6. For HITL nodes: suspend execution, persist full state, return run_id to caller
7. For Comparator nodes: wait for all N parallel branches before proceeding

### Async Execution Pattern

Phase 2 uses in-process async (no external queue). Pattern:

```python
# Route handler enqueues and returns immediately
async def run_pipeline(pipeline_id: str) -> RunResponse:
    run_id = uuid4()
    asyncio.create_task(executor.execute(pipeline_id, run_id))
    return RunResponse(run_id=run_id, status="running")

# Frontend polls
async def get_status(run_id: str) -> StatusResponse:
    return await state_store.get_run_status(run_id)
```

Never `await` the full execution in the request handler — it will timeout.

### Run State Schema

The run state object persisted to storage:

```python
{
  "run_id": "uuid",
  "pipeline_id": "uuid",
  "status": "running" | "completed" | "failed" | "waiting_hitl",
  "current_node_id": "uuid | None",
  "node_states": {
    "<node_id>": {
      "status": "pending" | "running" | "completed" | "failed" | "skipped",
      "output": {...} | None,
      "error": "str | None"
    }
  },
  "hitl_checkpoint": {
    "node_id": "uuid",
    "checkpoint_data": {...},   # from HITLBase.render_checkpoint()
    "resumed_at": "ISO-8601 | None"
  } | None,
  "started_at": "ISO-8601",
  "completed_at": "ISO-8601 | None"
}
```

### HITL Suspend/Resume

1. Executor reaches a HITL node → calls `render_checkpoint(inputs)`
2. Persists full run state with `status="waiting_hitl"` and checkpoint data
3. Returns control (does NOT block)
4. Human submits response via `POST /api/v1/hitl/{run_id}/respond`
5. API calls `executor.resume(run_id, human_response)`
6. Executor calls `process_response(human_input)` on the HITL block
7. Continues graph walk from the HITL node's output edges

### File Layout

```
backend/engine/
├── executor.py        # Graph walker and async execution loop
├── state.py           # Run state persistence (aiosqlite)
├── validator.py       # Edge type checking (Phase 1, stable)
├── registry.py        # Block discovery (Phase 1, stable)
└── loop_controller.py # Loop tracking and termination (if loops added)
```

---

## Anti-Patterns to Flag

- **Blocking the event loop**: Any `time.sleep()`, synchronous DB calls, or synchronous LLM calls inside `execute()`. Everything async.
- **Awaiting full execution in request handler**: The run must be fire-and-forget (`asyncio.create_task`).
- **State stored only in memory**: Run state must be persisted to storage — the process can restart mid-run (HITL waits can be long).
- **Skipping topological sort**: Executing nodes in insertion order rather than dependency order breaks pipelines with parallel branches.
- **Not handling skipped branches**: After a Router, nodes on inactive branches must be marked `skipped`, not `pending` — otherwise the executor waits for them forever.

---

## Context Documents

- **`.claude/context/execution-engine.md`** — load when this file exists; created reactively after first executor bugs
- **`.claude/context/pipeline-schema.md`** — pipeline definition structure; required for graph traversal logic
- **`.claude/context/block-contracts.md`** — BlockBase interface; required for calling `execute()`, `resolve_route()`, `render_checkpoint()`
