# Pipeline Schema Specification

## Current Version: 1.0

The pipeline definition is the primary artifact of the platform — it is what gets saved, loaded, shared, versioned, and eventually sold. It must be LLM-readable, LLM-writable, and stable across minor platform updates.

Pydantic models live in `backend/schemas/pipeline.py`.

---

## Top-Level Structure

| Field          | Type        | Required | Description                                           |
|----------------|-------------|----------|-------------------------------------------------------|
| `pipeline_id`  | UUID string | yes      | Unique identifier for this pipeline                   |
| `name`         | string      | yes      | Human-readable name                                   |
| `version`      | string      | yes      | Schema version (currently `"1.0"`)                    |
| `created_at`   | ISO-8601    | yes      | Creation timestamp                                    |
| `updated_at`   | ISO-8601    | yes      | Last modification timestamp                           |
| `nodes`        | Node[]      | yes      | Ordered list of block nodes                           |
| `edges`        | Edge[]      | yes      | Directed connections between nodes                    |
| `loop_definitions` | Loop[] | no       | Explicit loop declarations (required for any loop)    |
| `metadata`     | Metadata    | yes      | Description, tags, author                             |

---

## Node Schema

| Field                  | Type          | Required | Description                                               |
|------------------------|---------------|----------|-----------------------------------------------------------|
| `node_id`              | UUID string   | yes      | Unique identifier within this pipeline                    |
| `block_type`           | enum string   | yes      | Abstract category — one of the 10 base types              |
| `block_implementation` | string        | yes      | Concrete implementation key (e.g. `segmentation_kmeans`)  |
| `label`                | string        | yes      | Display name shown on canvas                              |
| `position`             | `{x: float, y: float}` | yes | Canvas coordinates; stored with the definition    |
| `config`               | object        | yes      | Block-specific configuration; must pass `validate_config()` |
| `input_schema`         | string[]      | yes      | Accepted input data type identifiers                      |
| `output_schema`        | string[]      | yes      | Produced output data type identifiers                     |

### block_type enum values
`source` | `transform` | `generation` | `evaluation` | `comparator` | `llm_flex` | `router` | `hitl` | `reporting` | `sink`

### Type-specific node constraints
| block_type    | input_schema | output_schema |
|---------------|--------------|---------------|
| `source`      | `[]`         | non-empty     |
| `sink`        | non-empty    | `[]`          |
| `comparator`  | single type, quantity N (declared as one type; engine accepts N edges of that type) | non-empty |
| `reporting`   | may reference non-adjacent upstream nodes via `declare_pipeline_inputs()` | non-empty |

---

## Edge Schema

| Field         | Type        | Required | Description                                                    |
|---------------|-------------|----------|----------------------------------------------------------------|
| `edge_id`     | UUID string | yes      | Unique identifier for this edge                                |
| `source_node` | UUID string | yes      | `node_id` of the originating node                             |
| `target_node` | UUID string | yes      | `node_id` of the receiving node                               |
| `data_type`   | string      | yes      | Data type flowing on this edge; must be in vocabulary         |
| `validated`   | boolean     | yes      | Whether the engine has confirmed type compatibility            |

---

## Loop Definition Schema

| Field            | Type        | Required | Description                                                    |
|------------------|-------------|----------|----------------------------------------------------------------|
| `loop_id`        | UUID string | yes      | Unique identifier for this loop                                |
| `entry_node`     | UUID string | yes      | First node inside the loop                                     |
| `exit_node`      | UUID string | yes      | The Router or HITL node that controls termination              |
| `termination`    | object      | yes      | Termination condition (see below)                              |

### Termination object
| Field            | Type    | Required | Description                                                        |
|------------------|---------|----------|--------------------------------------------------------------------|
| `type`           | enum    | yes      | `"router_condition"` or `"hitl"` or `"max_iterations"`            |
| `max_iterations` | int     | no       | Hard cap on loop iterations; engine enforces this as a safety limit |
| `fallback`       | string  | no       | What to do when max_iterations is hit: `"hitl"` or `"abort"`      |

**Rule:** Every loop in the graph MUST have a corresponding `loop_definitions` entry. The executor treats any cycle without a loop definition as an error.

---

## Metadata Schema

| Field         | Type     | Required | Description                          |
|---------------|----------|----------|--------------------------------------|
| `description` | string   | no       | Human-readable description           |
| `tags`        | string[] | no       | e.g. `["concept-testing", "synthetic"]` |
| `author`      | string   | no       | User ID of the pipeline creator      |

---

## Validation Rules (enforced by `backend/engine/validator.py`)

1. Every edge's `data_type` must appear in the source node's `output_schema`
2. Every edge's `data_type` must appear in the target node's `input_schema`
3. Source nodes (`block_type = "source"`) must have zero incoming edges
4. Sink nodes (`block_type = "sink"`) must have zero outgoing edges
5. Every non-Source, non-Sink node must have at least one incoming and one outgoing edge (orphan check)
6. Every cycle in the graph must have a corresponding entry in `loop_definitions`
7. Every `loop_definitions` entry must reference valid `node_id` values present in `nodes`
8. `validated` on an edge must be `true` before the executor will run the pipeline

---

## Example: Segmentation node

```json
{
  "node_id": "3f7a2c1e-...",
  "block_type": "transform",
  "block_implementation": "segmentation_kmeans",
  "label": "K-Means Segmentation",
  "position": { "x": 400, "y": 200 },
  "config": {
    "n_clusters": 5,
    "features": ["spend_monthly", "frequency", "recency"],
    "scaling": "standard"
  },
  "input_schema": ["respondent_collection"],
  "output_schema": ["segment_profile_set"]
}
```

---

## Known Failure Modes

| Failure | Cause | Effect |
|---------|-------|--------|
| Edge `data_type` not in source's `output_schema` | Agent creates edge without checking node's declared outputs | Validator rejects at validation time |
| Edge `data_type` not in target's `input_schema` | Same; validator also catches this | Validator rejects at validation time |
| Loop in graph without `loop_definitions` entry | Agent adds back-edge without declaring the loop | Executor treats graph as DAG with a cycle → error or infinite loop |
| `block_implementation` not in registry | Agent references a block name that doesn't exist | Executor fails at node load time |
| `validated: false` on edge at run time | Pipeline saved before validation completed | Executor refuses to run |
| Reporting node not listing upstream non-adjacent inputs | Agent omits `declare_pipeline_inputs()` entries | Engine fails to resolve cross-pipeline references at execution |

---

## Design Decisions to Preserve

- **Position data in nodes**: Canvas layout is part of the pipeline definition, not a separate store. Enables save/load/share of visual layout.
- **Explicit loop declarations**: Loops are not inferred from graph topology. The engine needs explicit bounds and termination conditions.
- **Type vs. implementation separation**: `block_type` is the abstract category; `block_implementation` is the concrete class. This is what makes the block library extensible without breaking existing pipelines.
- **LLM-readability**: The schema must remain parseable and writable by an LLM (structured JSON, no binary encoding, no custom parsing required).
