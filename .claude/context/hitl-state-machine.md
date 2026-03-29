# HITL State Machine

Reference for suspend/resume in `backend/engine/state.py` and `backend/api/hitl.py`.

---

## States

```
PENDING → RUNNING → COMPLETED
                 ↘
                 SUSPENDED ← human input pending
                     ↓
                  RUNNING (resumed) → COMPLETED
                                    ↘ FAILED
```

`FAILED` is terminal. `COMPLETED` is terminal. Only `SUSPENDED` can transition back to `RUNNING`.

---

## Suspend Flow

**Triggered by:** executor reaching an `HITLBase` node.

```
executor._execute_node()
  └── isinstance(block, HITLBase) → True
        ├── checkpoint_data = block.render_checkpoint(inputs)
        ├── run_state.status = SUSPENDED
        ├── run_state.hitl_checkpoint = HITLCheckpoint(node_id, checkpoint_data)
        ├── node_state.status = RUNNING  ← NOT completed yet
        └── return "suspended"

executor.execute_pipeline()
  └── detects "suspended"
        ├── await update_run(run_state)  ← persists to DB
        └── return run_state
```

Alternatively, blocks that need async work before suspending can `raise HITLSuspendSignal(checkpoint_data)` from within `execute()`. The executor catches this and handles identically.

**Important:** The node stays `RUNNING` (not `COMPLETED`) during suspension. It completes only after `process_response()` runs on resume.

---

## HITLCheckpoint Schema

```python
class HITLCheckpoint:
    node_id: str           # which node caused suspension
    checkpoint_data: dict  # from render_checkpoint() — shown to human
    resumed_at: datetime | None  # set on resume
```

`checkpoint_data` is whatever `render_checkpoint()` returns. For `ApprovalGate` it includes `prompt_text`, the input data, and config flags (`require_comment`, `allow_modification`).

---

## Resume Flow

**Triggered by:** `POST /api/v1/hitl/{run_id}/respond`

```
API handler
  └── validate run exists and status == SUSPENDED  (400 if not suspended, 404 if not found)
        └── run_state = await resume_run(run_id, human_input)
              ├── load run_state from DB
              ├── find HITL node schema in pipeline
              ├── block = get_block_class(type, impl)()
              ├── output = block.process_response(human_input)
              ├── store output on all HITL node outgoing edges in run_state.edge_data
              ├── node_state.status = COMPLETED
              ├── checkpoint.resumed_at = now()
              ├── run_state.status = RUNNING
              ├── run_state.current_node_id = None
              └── await update_run(run_state)

API handler
  └── asyncio.create_task(execute_pipeline(pipeline, run_id, run_state))
```

The executor re-enters `execute_pipeline` with the updated `RunState`. It skips already-completed nodes (checks `NodeStatus == COMPLETED` before executing) and continues from where it left off.

---

## Human Response Shape

Each HITL block defines its own expected response format via `process_response()`. For `ApprovalGate`:

```json
{
  "approved": true,
  "comment": "Looks good",
  "modified_data": null
}
```

The API accepts `{"response": dict, "metadata": dict?}`. `response` is passed directly to `process_response()`.

---

## Error Cases

| Condition | HTTP status | Behaviour |
|---|---|---|
| `run_id` not found | 404 | Raise `LookupError` |
| Run not in SUSPENDED state | 400 | Raise `ValueError` |
| Block not found in registry | 500 | Propagate `KeyError` |
| `process_response()` raises | 500 | Run stays SUSPENDED — retry safe |

**Idempotency:** If `process_response()` fails, the run remains SUSPENDED and the checkpoint is still valid. The human can resubmit. Only `update_run()` makes the state change durable — if that fails too, the run stays SUSPENDED.

---

## Serialisation

`RunState.edge_data` is serialised to JSON for DB storage. All edge data in Phase 2 is JSON-serialisable (dicts, lists, strings, numbers). Custom encoder handles `datetime` and `UUID` objects.

If a future block stores non-serialisable objects (numpy arrays, Pydantic models), they must be converted before being stored as edge output. The executor does not automatically coerce types.

---

## Adding New HITL Blocks

1. Inherit from `HITLBase` in `blocks/base.py`
2. Implement `render_checkpoint(inputs) -> dict` — returns data to show the human
3. Implement `process_response(human_input) -> dict` — converts human response to block output dict keyed by output port names
4. The executor and state machine handle suspension/resume automatically — no changes needed there
5. Document the expected `human_input` shape in the block's docstring
