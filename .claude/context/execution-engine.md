# Execution Engine

Reference for `backend/engine/executor.py` and `backend/engine/loop_controller.py`.

---

## Core Concept

The executor is a **layer-based async graph walker**. It does NOT stream nodes one by one — it groups topologically independent nodes into parallel layers and runs each layer with `asyncio.gather`. This is the key architectural decision.

```
Pipeline:  Source → [A, B] → Comparator → Sink

Layer 0:   Source             (no deps)
Layer 1:   A, B               (both depend on Source; no dependency between them)
Layer 2:   Comparator         (depends on A and B)
Layer 3:   Sink               (depends on Comparator)
```

---

## Graph Construction

```python
forward, reverse, outgoing_edges, incoming_edges = _build_adjacency(pipeline)
```

- `forward[node_id]` → list of downstream node IDs
- `reverse[node_id]` → list of upstream node IDs
- `outgoing_edges[node_id]` → set of edge IDs leaving this node
- `incoming_edges[node_id]` → set of edge IDs entering this node

**Loop back-edges are excluded from adjacency** — they would create cycles in the sort. A back-edge is identified by `loop_definitions[].exit_node → entry_node`. The `LoopController` handles loop iteration; the executor sees a DAG.

---

## Topological Sort

Kahn's algorithm (`_topological_sort`). Deterministic: nodes at the same in-degree level are sorted alphabetically before processing. Raises `ExecutionError` if the pipeline contains an undeclared cycle.

---

## Parallel Layers

`_find_parallel_groups` maps each node to a layer index:
- Nodes with no dependencies → layer 0
- All other nodes → `max(layer of deps) + 1`

The executor iterates layers sequentially. Within a layer, all nodes run concurrently via `asyncio.gather`.

---

## Skipped Nodes

A node is **skipped** (not failed) when all its incoming edges are in `inactive_edges`. This happens after a Router block deactivates non-selected output edges. Skipped nodes propagate skips downstream: all their outgoing edges are also added to `inactive_edges`.

This is critical — without skip propagation, the executor would wait forever for nodes on inactive branches to complete.

---

## Data Flow

Edge data is stored in `RunState.edge_data: dict[edge_id, Any]`. When a node executes:
1. Input data is collected from `incoming_edges` that are not inactive, keyed by `edge.data_type`
2. `_execution_context` is injected into inputs automatically
3. Output is stored on all non-inactive `outgoing_edges`

Each edge carries exactly one data type. If a node produces output and has 3 outgoing edges, the same output dict is stored on all 3.

---

## Router Handling

After a Router block executes:
1. `resolve_route(output)` is called — returns list of active edge IDs
2. All outgoing edges NOT in that list are added to `inactive_edges`
3. The executor does this immediately after `execute()`, before moving to the next layer

**Router blocks must return edge IDs, not node IDs.** `resolve_route` receives the block's output dict, not the inputs.

---

## HITL Suspension

When the executor reaches an `HITLBase` block:
1. `render_checkpoint(inputs)` is called synchronously
2. `RunState.status = SUSPENDED` and `RunState.hitl_checkpoint` are set
3. The executor returns `"suspended"` immediately — it does NOT call `execute()`
4. The outer loop detects `"suspended"` and calls `update_run()` + returns

Alternatively, blocks can raise `HITLSuspendSignal(checkpoint_data)` from within `execute()` — the executor catches this and handles it identically.

The node's `NodeStatus` stays `RUNNING` during suspension (it has not completed).

---

## Async Execution Pattern

The API handler uses fire-and-forget:

```python
asyncio.create_task(executor.execute_pipeline(pipeline, run_id, run_state))
return RunResponse(run_id=run_id, status="running")
```

**Never await `execute_pipeline` in a request handler** — pipelines can run for minutes. The run state is polled via `GET /api/v1/execution/{run_id}/status`.

---

## Error Handling

- Single node failure → `RunStatus.FAILED`, error stored in `RunState.error` and `NodeState.error`, execution halts
- Block not found in registry → treated as node failure
- Config validation failure → treated as node failure
- Unhandled exception in `asyncio.gather` → captured as `Exception`, treated as node failure

There is no partial retry. A failed run stays failed — the user must fix the pipeline and start a new run.

---

## Files

| File | Responsibility |
|---|---|
| `backend/engine/executor.py` | Graph walker, layer execution, Router/HITL handling |
| `backend/engine/loop_controller.py` | Loop iteration counting and termination |
| `backend/engine/state.py` | HITL suspend/resume state persistence |
| `backend/engine/registry.py` | Block discovery — do not modify |
| `backend/engine/validator.py` | Edge type checking — do not modify |
| `backend/schemas/execution.py` | `RunState`, `NodeState`, `RunStatus`, `HITLCheckpoint` |
| `backend/storage/runs.py` | `get_run`, `update_run` persistence layer |
