# Insights IDE — Agent Constitution

## Project Overview

Visual pipeline IDE for insights professionals. Research workflows as node-and-edge graphs where the pipeline itself — not just the output — is the artifact. React + React Flow frontend, Python/FastAPI backend, SQLite (→ PostgreSQL in Phase 3+).

The platform lets researchers build, save, version, share, and reuse research designs. Three interaction modes — visual canvas, CLI, chat panel — all operate on the same underlying API and data structures.

**Current phase: Phase 2** (execution engine)

---

## Architecture Principles (non-negotiable)

- **API-FIRST**: Every frontend operation MUST have a corresponding API endpoint. No canvas-only functionality. CLI and chat panel consume the same API. If a feature works in the canvas but not via API, the architecture is broken.
- **BLOCK CONTRACTS**: All blocks implement BlockBase. Block type (abstract category) and block implementation (concrete class) are separate. `input_schemas` and `output_schemas` declare what connects to what.
- **TYPED EDGES**: Data flowing between blocks has a declared type identifier. The validator rejects connections where edge `data_type` is not in both source's `output_schemas` and target's `input_schemas`.
- **PIPELINE JSON IS THE ARTIFACT**: The pipeline definition schema is the most important data structure. It gets saved, versioned, shared, and eventually sold. Design it to be LLM-readable, LLM-writable, and schema-stable.
- **BLOCKS ARE INDEPENDENT**: Block implementations must not import from other block implementations. All shared base classes live in `blocks/base.py`.

---

## Conventions & Standards

### Backend
- Python 3.11+, FastAPI, Pydantic v2 for all request/response and data models
- File naming: `snake_case` for all Python files
- Block files: one file per implementation at `blocks/{type}/{implementation}.py`
- API routes: `/api/v1/pipelines`, `/api/v1/blocks`, `/api/v1/execution`, `/api/v1/hitl`
- All endpoints accept and return typed Pydantic models — no untyped `Dict` in or out

### Frontend
- React, TypeScript strict mode, React Flow for the canvas
- File naming: `kebab-case` for component files
- All canvas actions must call backend API endpoints; no local-only state mutations that bypass the API
- Pipeline state: Zustand store at `frontend/src/stores/pipeline.ts`

### Testing
- pytest for all backend tests
- Every block must pass generic contract tests (schema validity, config validation, output port completeness)
- Deterministic blocks (Transform): fixed input → assert exact output
- LLM-powered blocks: mock the API call, test prompt construction and response parsing
- Every block implementation must include `test_fixtures()` providing sample inputs/outputs

### Build & Run
- Backend: `cd backend && uvicorn main:app --reload`
- Frontend: `cd frontend && npm run dev`
- Tests: `cd backend && uv run pytest`
- Lint: `ruff check backend/`

### Branch Strategy
- `main`: stable
- `feature/{description}`: active work

---

## Block Types (10 base types)

| Type        | Inputs        | Outputs  | Key Behavior                                               |
|-------------|---------------|----------|------------------------------------------------------------|
| Source      | none          | data     | Entry point; execution starts here; no incoming edges      |
| Transform   | data          | data     | Deterministic, cacheable; same input → same output         |
| Generation  | data          | content  | Non-deterministic (LLM); version and seed tracking matter  |
| Evaluation  | 2+ (subject + criteria) | assess | Judges subject against criteria; requires multiple input types |
| Comparator  | N same-type   | compare  | Sync point; waits for all parallel branches to complete    |
| LLM Flex    | data          | varies   | User-defined prompt; configurable I/O shapes               |
| Router      | data          | branch   | Conditional edge activation; multiple output edges         |
| HITL        | data          | data     | Suspends execution; persists full pipeline state; resumes on external event |
| Reporting   | multi (named) | doc      | Draws on multiple upstream outputs (not just adjacent nodes); format-aware |
| Sink        | data          | none     | Terminal; persists final outputs; no outgoing edges        |

---

## Edge Data Types (current vocabulary)

| Identifier              | Description                                        |
|-------------------------|----------------------------------------------------|
| `respondent_collection` | Survey or customer data rows                       |
| `segment_profile_set`   | Cluster labels with descriptive profiles           |
| `concept_brief_set`     | Product or creative concept descriptions           |
| `evaluation_set`        | Scored assessments with criteria and scores        |
| `text_corpus`           | Unstructured text documents                        |
| `persona_set`           | Synthetic or real persona profiles                 |
| `generic_blob`          | Fallback for untyped or experimental data          |

**Rule:** When adding a new data type, update this table AND `backend/schemas/data_objects.py`.

---

## Agent Trigger Table

| Files Being Modified                          | Invoke Agent        |
|-----------------------------------------------|---------------------|
| `backend/engine/*.py`                         | engine-specialist   |
| `backend/blocks/**/*.py`, `blocks/base.py`    | block-developer     |
| `frontend/src/components/canvas/**`           | canvas-specialist   |
| `backend/api/*.py`, `backend/schemas/*.py`    | api-specialist      |
| `backend/schemas/pipeline.py`, `schemas/data_objects.py` | schema-specialist |
| Any block importing or calling Anthropic API  | llm-integration     |

When uncertain which agent to use: check this table first.
When exploring unfamiliar code: consult the relevant context doc before making changes.

**Context docs to load on demand:**

| Topic | File | Load When |
|---|---|---|
| Pipeline definition schema | `.claude/context/pipeline-schema.md` | Modifying serialization, validation, or CRUD |
| Block contracts & base classes | `.claude/context/block-contracts.md` | Implementing or modifying any block |
| Execution engine | `.claude/context/execution-engine.md` | Modifying graph walker, layers, or state machine |
| HITL state machine | `.claude/context/hitl-state-machine.md` | Modifying HITL blocks or suspend/resume flow |
| Edge type system | `.claude/context/edge-type-system.md` | Adding data types or modifying validation |
| React Flow patterns | `.claude/context/react-flow-patterns.md` | Modifying canvas components |

---

## Key File Map

| File                                    | Role                                                  |
|-----------------------------------------|-------------------------------------------------------|
| `backend/blocks/base.py`                | All block base classes and contracts                  |
| `backend/engine/executor.py`            | Graph walker — the core execution loop                |
| `backend/engine/validator.py`           | Edge type checking, pipeline integrity validation     |
| `backend/engine/state.py`               | HITL suspend/resume state persistence                 |
| `backend/engine/registry.py`            | Block discovery and registration                      |
| `backend/engine/loop_controller.py`     | Loop tracking and termination logic                   |
| `backend/schemas/pipeline.py`           | Pipeline definition Pydantic models                   |
| `backend/schemas/data_objects.py`       | Research data object schemas                          |
| `backend/api/pipelines.py`              | Pipeline CRUD endpoints                               |
| `backend/api/execution.py`              | Pipeline run trigger and status polling               |
| `backend/api/blocks.py`                 | Block catalog endpoint (feeds frontend palette)       |
| `backend/api/hitl.py`                   | HITL response submission and resume                   |
| `frontend/src/stores/pipeline.ts`       | Frontend pipeline state (Zustand)                     |

---

## Context Documents (Tier 3 — load on demand)

| Topic                        | File                               | Load When                                      |
|------------------------------|------------------------------------|------------------------------------------------|
| Pipeline definition schema   | `.claude/context/pipeline-schema.md` | Modifying serialization, validation, or CRUD |
| Block contracts & base classes | `.claude/context/block-contracts.md` | Implementing or modifying any block         |
| Execution engine             | `.claude/context/execution-engine.md` | Modifying graph walker or state machine     |
| Edge type system             | `.claude/context/edge-type-system.md` | Adding data types or modifying validation   |
| React Flow patterns          | `.claude/context/react-flow-patterns.md` | Modifying canvas components              |
| Research data objects        | `.claude/context/data-objects.md`   | Modifying data object schemas              |
