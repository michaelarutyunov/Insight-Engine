# Codified Context — Implementation Guide for Insights IDE

Based on Vasilopoulos (2026), adapted for this project's architecture and phasing.

---

## What You're Building

A three-tier knowledge layer that lives in your repo and makes AI coding agents consistently effective across sessions. No package to install — it's structured markdown files, a routing convention, and an optional MCP retrieval server.

```
.claude/
├── CLAUDE.md                          # Tier 1: Constitution (always loaded)
├── agents/
│   ├── engine-specialist/AGENT.md     # Tier 2: Domain-expert agents
│   ├── block-developer/AGENT.md
│   ├── canvas-specialist/AGENT.md
│   ├── api-specialist/AGENT.md
│   ├── schema-specialist/AGENT.md
│   └── llm-integration/AGENT.md
└── context/
    ├── pipeline-schema.md             # Tier 3: Cold-memory knowledge base
    ├── block-contracts.md
    ├── execution-engine.md
    ├── data-objects.md
    ├── edge-type-system.md
    └── react-flow-patterns.md
```

---

## Step 1: Write the Constitution (Tier 1)

This is the single file that every agent session loads automatically. It must be compact (aim for 400–700 lines) and contain only what *every* session needs. Everything else goes in Tier 2/3.

Create `CLAUDE.md` (or `.claude/CLAUDE.md`) in your project root with these sections:

### 1a. Project Identity & Architecture Summary

```markdown
# Insights IDE — Agent Constitution

## Project Overview
Visual pipeline IDE for insights professionals. Research workflows as node-and-edge
graphs. React + React Flow frontend, Python/FastAPI backend, SQLite (→ PostgreSQL).

## Architecture Principles (non-negotiable)
- API-FIRST: Every frontend operation MUST have a corresponding API endpoint.
  No canvas-only functionality. CLI and chat panel consume the same API.
- BLOCK CONTRACTS: All blocks implement BlockBase. Type (abstract category) and
  implementation (concrete block) are separate. input_schemas and output_schemas
  declare what connects to what.
- TYPED EDGES: Data flowing between blocks has a declared type. The validator
  rejects incompatible connections.
- PIPELINE JSON IS THE ARTIFACT: The pipeline definition schema is the single
  most important data structure. It gets saved, shared, versioned, sold.
```

### 1b. Conventions & Standards

```markdown
## Conventions
- Backend: Python 3.11+, FastAPI, Pydantic v2 for all schemas
- Frontend: React, TypeScript strict mode, React Flow for canvas
- Testing: pytest, contract tests for all blocks, mocked LLM calls
- File naming: snake_case for Python, kebab-case for frontend components
- Block files: one file per block implementation in blocks/{type}/{implementation}.py
- API routes: /api/v1/pipelines, /api/v1/blocks, /api/v1/execution, /api/v1/hitl

## Build & Run
- Backend: cd backend && uvicorn main:app --reload
- Frontend: cd frontend && npm run dev
- Tests: cd backend && pytest
- Lint: ruff check backend/

## Branch Strategy
- main: stable
- feature/{description}: active work
```

### 1c. Block Taxonomy (quick reference)

```markdown
## Block Types (10 base types)
| Type        | Inputs | Outputs | Key Behavior                          |
|-------------|--------|---------|---------------------------------------|
| Source      | none   | data    | Entry point, execution starts here    |
| Transform   | data   | data    | Deterministic, cacheable              |
| Generation  | data   | content | Non-deterministic (LLM), version/seed |
| Evaluation  | 2+ in  | assess  | Judges subject against criteria       |
| Comparator  | N same | compare | Sync point, waits for all branches    |
| LLM Flex    | data   | varies  | User-defined prompt, configurable I/O |
| Router      | data   | branch  | Conditional edge activation           |
| HITL        | data   | data    | Suspends execution, persists state    |
| Reporting   | multi  | doc     | Pulls from multiple upstream nodes    |
| Sink        | data   | none    | Terminal, persists and closes          |
```

### 1d. Edge Data Type Vocabulary

```markdown
## Edge Data Types (current vocabulary)
- respondent_collection: survey/customer data rows
- segment_profile_set: cluster labels + profiles
- concept_brief_set: product/creative concept descriptions
- evaluation_set: scored assessments with criteria
- text_corpus: unstructured text documents
- persona_set: synthetic or real persona profiles
- generic_blob: fallback for untyped data

RULE: When adding a new data type, update this list AND schemas/data_objects.py.
```

### 1e. Agent Trigger Table

This is the routing logic that tells the orchestrator which specialist agent to invoke.

```markdown
## Agent Trigger Table
| Files Being Modified              | Invoke Agent          |
|-----------------------------------|-----------------------|
| engine/*.py                       | engine-specialist     |
| blocks/**/*.py, blocks/base.py    | block-developer       |
| frontend/src/components/canvas/*  | canvas-specialist     |
| api/*.py, schemas/*.py            | api-specialist        |
| schemas/pipeline.py, data_objects | schema-specialist     |
| Any block using Anthropic API     | llm-integration       |

When uncertain which agent to use: check the trigger table first.
When exploring unfamiliar code: consult relevant context doc before making changes.
```

### 1f. Key File Map

```markdown
## Key Files
- backend/blocks/base.py           → All block base classes and contracts
- backend/engine/executor.py       → Graph walker, the core execution loop
- backend/engine/validator.py      → Edge type checking, pipeline integrity
- backend/schemas/pipeline.py      → Pipeline definition Pydantic models
- backend/schemas/data_objects.py  → Research data object schemas
- backend/engine/state.py          → HITL suspend/resume state persistence
- frontend/src/stores/pipeline.ts  → Frontend pipeline state (Zustand)
```

---

## Step 2: Create Specialist Agents (Tier 2)

Each agent is a markdown file with a focused persona, embedded domain knowledge, and tool permissions. Create these as you need them — not all at once.

### Start with two agents for Phase 1:

**`.claude/agents/api-specialist/AGENT.md`**

```markdown
# API Specialist Agent

## Role
Ensures all API endpoints follow conventions, validates that every frontend
operation has a backend endpoint, and maintains the API-first principle.

## Domain Knowledge
- FastAPI with Pydantic v2 for request/response models
- Endpoint pattern: /api/v1/{resource}
- Pipeline CRUD: GET/POST/PUT/DELETE /api/v1/pipelines
- Block catalog: GET /api/v1/blocks (feeds frontend palette)
- Execution: POST /api/v1/execution/{pipeline_id}/run
- HITL: POST /api/v1/hitl/{run_id}/respond

## Key Constraint
Before any frontend feature is merged, verify that:
1. The operation calls a backend API endpoint
2. The endpoint is documented in the route file
3. The request/response models are in schemas/

## Anti-patterns to flag
- Frontend state mutations that bypass the API
- Endpoints that accept untyped Dict instead of Pydantic models
- Missing error responses (always return structured error JSON)

## Context Documents
- Refer to: pipeline-schema.md for pipeline definition structure
- Refer to: block-contracts.md for block catalog response format
```

**`.claude/agents/block-developer/AGENT.md`**

```markdown
# Block Developer Agent

## Role
Implements new blocks and ensures all blocks conform to the BlockBase contract.

## Domain Knowledge
Every block MUST implement:
- block_type: one of the 10 base types
- input_schemas: list of accepted data type identifiers
- output_schemas: list of produced data type identifiers
- config_schema: JSON Schema for configuration options
- validate_config(config): returns bool
- execute(inputs, config): async, returns dict keyed by output port

Type-specific additions:
- RouterBase: resolve_route(inputs) → List[str] (which edges to activate)
- HITLBase: render_checkpoint(inputs) → Dict, process_response(human_input) → Dict
- ComparatorBase: input_schemas accepts N items of same type
- ReportingBase: declare_pipeline_inputs() → List[str] (cross-pipeline references)

## File Organization
- One file per implementation: blocks/{type}/{implementation}.py
- Example: blocks/transforms/segmentation_kmeans.py
- All imports from blocks/base.py

## Testing Requirements
- Every block must pass generic contract tests (schema validity, config validation)
- Deterministic blocks (Transform): test with fixed input, assert exact output
- LLM-powered blocks: mock the API call, test prompt construction + response parsing
- Include test_fixtures() providing sample inputs/outputs

## Anti-patterns to flag
- Blocks that import from other block implementations (blocks are independent)
- Missing input/output schema declarations
- execute() that doesn't return all declared output ports
- Config schemas that don't match validate_config() logic
```

### Add more agents as you enter Phase 2:

- **engine-specialist**: Graph walker logic, topological sort, loop handling, state persistence
- **canvas-specialist**: React Flow patterns, node rendering, edge validation UI
- **schema-specialist**: Pipeline definition evolution, data object types, versioning
- **llm-integration**: Prompt construction, API call patterns, response parsing, provider abstraction

---

## Step 3: Build the Knowledge Base (Tier 3)

These are detailed specification documents loaded on demand. Write them when agents make mistakes on a topic — not upfront.

### Minimum viable knowledge base for Phase 1:

**`.claude/context/pipeline-schema.md`**

Document the pipeline definition JSON structure in full, with examples. Include the node schema, edge schema, loop definitions, metadata. This is the reference an agent consults when modifying pipeline serialization.

**`.claude/context/block-contracts.md`**

The complete BlockBase interface, all type-specific base classes, config schema conventions, and the test_fixtures pattern. Agents consult this when implementing new blocks.

### Add as you build:

| When you hit this problem... | Create this context doc |
|------------------------------|------------------------|
| Agent mishandles executor state | execution-engine.md |
| Agent creates invalid edge connections | edge-type-system.md |
| Agent breaks React Flow patterns | react-flow-patterns.md |
| Agent misuses data object schemas | data-objects.md |
| Agent botches HITL suspend/resume | hitl-state-machine.md |
| Agent mishandles loop termination | loop-control.md |

### Format for context docs

Optimized for AI consumption — structured, not prose:

```markdown
# Pipeline Schema Specification

## Current Version: 1.0

## Node Schema
| Field               | Type          | Required | Description                    |
|---------------------|---------------|----------|--------------------------------|
| node_id             | UUID string   | yes      | Unique identifier              |
| block_type          | enum          | yes      | One of 10 base types           |
| block_implementation| string        | yes      | Specific block (e.g. segmentation_kmeans) |
| label               | string        | yes      | Display name                   |
| position            | {x, y}       | yes      | Canvas coordinates             |
| config              | object        | yes      | Block-specific configuration   |
| input_schema        | string[]      | yes      | Accepted input data types      |
| output_schema       | string[]      | yes      | Produced output data types     |

## Edge Schema
...

## Validation Rules
1. Every edge's data_type must match source node's output_schema
2. Every edge's data_type must match target node's input_schema
3. No orphan nodes (every node must have at least one edge, except Source/Sink)
4. Sources have no incoming edges
5. Sinks have no outgoing edges
...

## Known Failure Modes
- Agent creates edges with data_type not in either node's schema → validator rejects
- Agent adds loop without loop_definition entry → executor treats as DAG, infinite loop
```

---

## Step 4: Set Up MCP Retrieval (Optional, Phase 2+)

The MCP server lets agents query the knowledge base programmatically rather than loading everything into context. This matters when your context docs grow beyond what fits in a single prompt.

The companion repo provides a Python MCP server with these tools:
- `list_subsystems()` — lists available context documents
- `find_relevant_context(task_description)` — returns relevant docs for a task
- `search_context_docs(query)` — keyword search across knowledge base
- `suggest_agent(task_description)` — recommends which specialist agent to invoke

For Phase 1, you likely don't need this — your knowledge base will be small enough to reference directly. Add the MCP server when you have 10+ context documents and agent sessions start hitting context limits.

---

## Step 5: Add Validation (from session 1)

Create a simple script that checks cross-references on session start:

**`.claude/scripts/context-drift-check.py`**

This checks that:
- Every file referenced in the constitution actually exists
- Every agent spec references valid context documents
- Every block listed in the trigger table has a corresponding agent
- Key file paths in the constitution match actual file locations

Run this at session start or as a pre-commit hook. When references break, you know the knowledge layer has drifted from the codebase.

---

## Growth Pattern

The paper's key insight: **create documents when agents make mistakes, not as a planning exercise.**

Practical workflow:

1. Agent messes up execution engine state handling → you fix it manually
2. You write `.claude/context/execution-engine.md` documenting the correct behavior
3. You add a trigger rule: "when modifying engine/state.py, consult execution-engine.md"
4. Next session, the agent loads the right context and doesn't repeat the mistake

This means your context infrastructure grows organically with the project. After Phase 1 you might have 3-4 context docs. After Phase 2, 8-10. The ratio from the paper (~1 line of documentation per 4 lines of code) is a reasonable benchmark.

---

## Integration with Beads

Beads and codified context solve different problems and layer cleanly:

| Layer | Tool | Answers |
|-------|------|---------|
| What to do next | Beads | "Which task is unblocked and ready?" |
| How to do it correctly | Codified Context | "What conventions and patterns apply here?" |
| What went wrong before | Both | Beads tracks issues; context docs encode lessons |

Workflow: Beads assigns a task → agent loads the constitution → trigger table routes to specialist agent → agent consults relevant context docs → agent completes the task → Beads marks it done.

---

## Phase-Aligned Checklist

### Phase 1 (do now)
- [ ] Write CLAUDE.md constitution (sections 1a–1f above)
- [ ] Create api-specialist and block-developer agents
- [ ] Create pipeline-schema.md and block-contracts.md context docs
- [ ] Add context-drift-check.py validation script
- [ ] Initialize Beads, file Phase 1 epics and tasks

### Phase 2 (when execution engine starts)
- [ ] Add engine-specialist agent
- [ ] Add execution-engine.md context doc (after first executor bugs)
- [ ] Add llm-integration agent (when LLM blocks are built)
- [ ] Consider MCP retrieval server if context docs exceed ~10 files
- [ ] Add hitl-state-machine.md after first HITL suspend/resume issues

### Phase 3+ (as needed)
- [ ] Add canvas-specialist agent
- [ ] Add react-flow-patterns.md
- [ ] Add reporting-blocks.md
- [ ] Add schema-specialist agent for pipeline versioning
- [ ] Review and compact context docs that have grown too large
