# Insights IDE — Technical Blueprint & Phasing Plan

## Tech Stack

### Frontend
- **React** — primary framework
- **React Flow** — node graph editor library (most mature option for the canvas interaction model)
- **TypeScript** — recommended for type safety across block configurations and pipeline definitions

### Backend
- **Python / FastAPI** — leverages existing Python proficiency; natural fit for data science blocks (pandas, scikit-learn, statsmodels), LLM API calls, and sample provider integrations
- **SQLite** (Phase 1–2) → **PostgreSQL via Cloud SQL** (Phase 3+)
- **Docker** — containerized deployment from Phase 2 onward

### Cloud Infrastructure (Google Cloud)
- **Cloud Run** — containerized FastAPI backend; scales to zero during development; no server management
- **Cloud SQL (PostgreSQL)** — pipeline definitions, user data, pipeline state persistence (Phase 3+)
- **Cloud Storage** — datasets, generated reports, uploaded files, block artifacts
- **Cloud Run Jobs / Cloud Tasks** — asynchronous pipeline execution; API enqueues job and returns immediately, frontend polls for status; natural fit for HITL suspend/resume pattern

### LLM Integration
- **Anthropic API (Claude)** — primary LLM for Generation, Evaluation, and LLM Flex blocks
- **Chat panel** — LLM-powered assistant embedded in the IDE; uses pipeline state and block registry as context
- Architecture should support swappable LLM providers per block configuration

## Core Data Structure: Pipeline Definition Schema

The pipeline definition is the single most important data structure in the platform. It is the file format for research workflows — what gets saved, loaded, shared, and eventually sold in the marketplace.

```json
{
  "pipeline_id": "uuid",
  "name": "Concept Pre-Screen & Validation",
  "version": "1.0",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "nodes": [
    {
      "node_id": "uuid",
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
  ],
  "edges": [
    {
      "edge_id": "uuid",
      "source_node": "node-uuid-1",
      "target_node": "node-uuid-2",
      "data_type": "segment_profile_set",
      "validated": true
    }
  ],
  "loop_definitions": [
    {
      "loop_id": "uuid",
      "entry_node": "node-uuid-concept-gen",
      "exit_node": "node-uuid-router",
      "termination": {
        "type": "router_condition",
        "max_iterations": 10,
        "fallback": "hitl"
      }
    }
  ],
  "metadata": {
    "description": "Pre-screen concepts using synthetic personas, then validate with real fieldwork",
    "tags": ["concept-testing", "synthetic", "cpg"],
    "author": "user-id"
  }
}
```

Key design decisions embedded here:
- **Nodes declare their input/output schemas** — enables connection validation
- **Loop definitions are explicit** — the engine knows where loops exist and how they terminate
- **Block type vs. block implementation** — type is the abstract category (transform), implementation is the specific block (segmentation_kmeans). This separation is what makes the block library extensible
- **Position data stored with nodes** — the visual layout is part of the pipeline definition, not a separate concern

## Backend Directory Structure

```
backend/
├── main.py                          # FastAPI app entry point
├── api/
│   ├── pipelines.py                 # CRUD endpoints for pipeline definitions
│   ├── execution.py                 # Pipeline run triggers, status polling
│   ├── blocks.py                    # Block catalog endpoint (feeds frontend palette)
│   └── hitl.py                      # HITL response submission and resume
├── engine/
│   ├── executor.py                  # Graph walker — traverses and runs pipelines
│   ├── state.py                     # Pipeline state persistence (suspend/resume)
│   ├── registry.py                  # Discovers and registers available blocks
│   ├── validator.py                 # Edge type checking, pipeline integrity
│   └── loop_controller.py           # Loop tracking, termination logic
├── blocks/
│   ├── base.py                      # Abstract base classes per block type
│   ├── sources/
│   │   ├── csv_loader.py
│   │   ├── database_connector.py
│   │   └── api_connector.py
│   ├── transforms/
│   │   ├── segmentation_kmeans.py
│   │   ├── segmentation_lca.py
│   │   ├── data_cleaning.py
│   │   └── weighting.py
│   ├── generation/
│   │   ├── synthetic_persona.py
│   │   └── concept_drafter.py
│   ├── evaluation/
│   │   ├── concept_evaluator.py
│   │   └── quality_scorer.py
│   ├── comparison/
│   │   └── multi_input_comparator.py
│   ├── reporting/
│   │   ├── report_pdf.py
│   │   ├── report_narrative.py
│   │   ├── presentation_builder.py
│   │   └── podcast_script.py
│   ├── llm_flex/
│   │   └── custom_prompt.py
│   ├── routing/
│   │   ├── convergence_router.py
│   │   └── threshold_router.py
│   ├── hitl/
│   │   └── approval_checkpoint.py
│   └── sinks/
│       ├── project_save.py
│       ├── api_push.py
│       └── notify_and_close.py
├── schemas/
│   ├── pipeline.py                  # Pipeline definition Pydantic models
│   ├── block_types.py               # Block type enums and contracts
│   └── data_objects.py              # Research data object schemas
├── db/
│   ├── models.py                    # Database models
│   └── connection.py                # DB connection management
├── cli/
│   ├── main.py                      # CLI entry point (Typer app)
│   ├── pipeline_commands.py         # pipeline list, run, status, validate
│   └── block_commands.py            # block list, inspect
├── chat/
│   ├── context_builder.py           # Assembles pipeline state for LLM context
│   ├── assistant.py                 # Research assistant mode (domain Q&A)
│   ├── copilot.py                   # Pipeline co-pilot mode (graph modification)
│   └── config_helper.py             # Block configuration helper mode
└── tests/
    ├── test_executor.py
    ├── test_validator.py
    └── test_blocks/
```

## Block Interface Contract

Every block implements a base class corresponding to its block type. The minimal contract:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BlockBase(ABC):
    """Abstract base for all blocks."""

    @property
    @abstractmethod
    def block_type(self) -> str:
        """One of: source, transform, generation, evaluation,
        comparator, reporting, llm_flex, router, hitl, sink"""
        ...

    @property
    @abstractmethod
    def input_schemas(self) -> List[str]:
        """List of accepted input data type identifiers."""
        ...

    @property
    @abstractmethod
    def output_schemas(self) -> List[str]:
        """List of produced output data type identifiers."""
        ...

    @property
    @abstractmethod
    def config_schema(self) -> Dict:
        """JSON Schema for this block's configuration options."""
        ...

    @abstractmethod
    def validate_config(self, config: Dict) -> bool:
        """Check if provided configuration is valid."""
        ...

    @abstractmethod
    async def execute(self, inputs: Dict[str, Any], config: Dict) -> Dict[str, Any]:
        """
        Run the block.
        - inputs: keyed by input port name, values are data objects
        - config: block configuration parameters
        - returns: keyed by output port name, values are data objects
        """
        ...
```

Block-type-specific base classes add type-specific behavior:

- **RouterBase** adds `def resolve_route(self, inputs) -> List[str]` — returns which output edges to activate
- **HITLBase** adds `def render_checkpoint(self, inputs) -> Dict` — returns data to present to the human, and `def process_response(self, human_input) -> Dict` — handles the human's response
- **ComparatorBase** declares that `input_schemas` accepts N items of the same type
- **ReportingBase** adds `def declare_pipeline_inputs(self) -> List[str]` — declares which upstream node outputs it needs (not just adjacent predecessors), and includes `output_format` in its config schema. The engine resolves these cross-pipeline references at execution time

## Execution Engine Design

### Graph Walking
1. Parse pipeline definition JSON
2. Topologically sort nodes (with special handling for declared loops)
3. For each node in order:
   - Wait for all required inputs to be available (relevant for multi-input blocks like Evaluation and Comparator)
   - Load block implementation from registry
   - Call `execute()` with inputs and configuration
   - Store outputs on the corresponding edges
   - For Routers: evaluate condition, activate selected output edges only
   - For HITL: persist full pipeline state, suspend execution, exit
4. For loops: track iteration count, check termination conditions via Router or HITL at the exit node

### State Persistence (for HITL and long-running pipelines)
Pipeline execution state includes:
- Current execution pointer (which node is active or next)
- Data on every edge (what each block has produced so far)
- Loop iteration counters
- Block-level internal state (if any)

State serialized to database as JSON. On HITL resume, engine reloads state and continues from the suspended node.

### Asynchronous Execution
- API endpoint receives "run pipeline" request
- Creates an execution job record in the database
- Enqueues job to Cloud Run Jobs / Cloud Tasks
- Returns job ID immediately
- Frontend polls `/execution/{job_id}/status` for progress
- Status includes: which node is currently executing, which nodes are complete, whether a HITL checkpoint is waiting for input

## Multi-Modal Access Architecture

The platform supports three interaction modes that all operate on the same underlying API and data structures. This is a core architectural principle, not an add-on: **no operation should exist only in one mode.**

### Visual Canvas (Phase 1)
The React Flow graph editor. Primary interface for designing pipelines, configuring blocks, and monitoring execution. All canvas actions translate to API calls against the FastAPI backend.

### CLI (Phase 2–3)
A Python CLI (Typer or Click) that wraps the same API endpoints the frontend uses. Enables programmatic pipeline management and is the foundation for agent integration.

```
insights pipeline list                          # List saved pipelines
insights pipeline show <pipeline-id>            # Display pipeline definition
insights pipeline run <pipeline-id>             # Trigger execution
insights pipeline status <run-id>               # Check progress, active node
insights pipeline validate <pipeline-file>      # Validate a pipeline JSON file
insights pipeline create --from-template <name> # Scaffold from template

insights block list                             # Show available blocks
insights block inspect <block-implementation>   # Show config schema, inputs, outputs
insights block list --type transform            # Filter by block type

insights run log <run-id>                       # Execution history, edge data
insights run resume <run-id> --hitl-response <file>  # Resume from HITL checkpoint
```

The CLI is architecturally important beyond developer convenience. An agent in "pipeline executor" mode is calling these commands. An agent in "pipeline composer" mode calls `block list`, reasons about compatibility, assembles a pipeline JSON, runs `pipeline validate`, then `pipeline run`. The CLI makes platform capabilities machine-accessible without the visual UI.

### Chat Panel (Phase 3)
An LLM-powered assistant panel embedded in the IDE, with full access to the current pipeline state. Serves three distinct functions:

**Research assistant** — answers domain questions with pipeline context. The user asks "which segmentation method would work best for this dataset?" and the LLM can see the block configuration, data types, and workflow structure. Implementation: current pipeline JSON injected as context in the LLM prompt, along with the block registry documentation.

**Pipeline co-pilot** — modifies the pipeline via natural language. "Add a data cleaning step between the source and segmentation." "Split this into two parallel branches and add a comparator." The LLM reads the current pipeline JSON, generates a valid modified version, and the platform applies the diff. The typed block contracts make this tractable — the LLM knows what can connect to what. Implementation: LLM outputs a pipeline modification as JSON, frontend validates and applies it, user confirms or reverts.

**Block configuration helper** — assists with configuring individual blocks. "Write me a prompt that extracts brand sentiment themes from review text." The output goes directly into an LLM Flex block's configuration. Implementation: block's config schema provided as context, LLM generates valid configuration values.

### Design Principle: API as Single Source of Truth
All three modes — canvas, CLI, and chat panel — are consumers of the same FastAPI backend. The API is the authority on what operations are possible. This means:
- Every frontend button click corresponds to an API call
- The CLI is a thin wrapper around the same endpoints
- The chat panel's pipeline modifications go through the same validation as manual edits
- Any new capability added via any mode is automatically available to all three

This principle must be enforced from Phase 1 onward. If a feature works in the canvas but not via API, the architecture is broken.

## Five-Phase Build Plan

### Phase 1 — Graph Editor with Backend Skeleton (Target: 2 weeks)

**Frontend deliverables:**
- React Flow canvas with drag-and-drop block placement
- Block palette showing all ten block types with visual differentiation
- Edge connection with basic type validation (compatible types connect, incompatible types rejected)
- Block configuration panel (click a node, see its settings)
- Save / load pipeline definitions

**Backend deliverables:**
- FastAPI with two endpoint groups: pipeline CRUD and block catalog
- Pipeline definition schema (Pydantic models)
- Block type contracts (base classes, input/output schema declarations)
- SQLite storage for pipeline definitions
- Connection validation endpoint

**Not built yet:** Execution engine, LLM calls, external APIs, authentication, CLI, chat panel.

**Design constraint (enforced from this phase):** Every frontend operation must have a corresponding API endpoint. No canvas-only functionality. This is the foundation for CLI, chat panel, and agent integration in later phases.

**Demo capability:** Interactive graph builder where you can construct the concept test workflow visually, configure blocks, save and reload it. Nothing executes, but the research design is tangible and shareable.

---

### Phase 2 — Execution Engine (Target: 3–4 weeks)

**Deliverables:**
- Graph walker that traverses a pipeline definition and executes blocks in order
- 5–6 concrete block implementations:
  - Source: CSV loader
  - Transform: basic segmentation (k-means)
  - Generation: synthetic persona generator (LLM-powered)
  - Evaluation: concept evaluator (LLM-powered)
  - LLM Flex: custom prompt block
  - Router: simple threshold/iteration-count condition
  - HITL: basic approval checkpoint with state persistence
  - Sink: save output to project storage
- Pipeline state persistence and HITL suspend/resume
- Asynchronous execution (job queue pattern)
- Execution status display in frontend (progress indicator per node)
- CLI foundation: `pipeline list`, `pipeline run`, `pipeline status`, `block list`, `block inspect` commands wrapping the existing API

**Demo capability:** The concept test workflow runs end-to-end. Real LLM calls, real segmentation output, real synthetic personas. HITL blocks pause and resume. Pipelines can be triggered and monitored from the command line. The platform does something useful.

---

### Phase 3 — Block Library Expansion (Target: 6–8 weeks)

**Deliverables:**
- Additional Source blocks: database connectors, sample provider APIs (Cint, Lucid)
- Additional Transform blocks: LCA segmentation, RFM, data cleaning, weighting, recoding
- Additional Generation blocks: concept drafter, discussion guide generator, stimulus material creator
- Reporting blocks: PDF report builder, narrative report writer, presentation generator, podcast script writer
- Comparator block: multi-input comparison with structured output
- Additional Sink blocks: API push, notification and project closure
- Chat panel (research assistant mode): LLM with pipeline context for domain questions and block configuration help
- Chat panel (co-pilot mode): natural language pipeline modification — "add a cleaning step before segmentation"
- CLI expansion: `pipeline validate`, `pipeline create --from-template`, `run resume --hitl-response`
- Block configuration UI improvements (richer parameter editors)
- Pipeline templates: pre-built workflow templates for common research designs

**Demo capability:** Multiple distinct research workflows. Users can choose different segmentation methods, swap blocks, run parallel branches. The platform supports real methodological variety.

---

### Phase 4 — Multi-User SaaS (Target: 8–12 weeks)

**Deliverables:**
- User authentication and accounts
- Multi-tenancy (isolated pipeline storage per user/organization)
- Migration from SQLite to PostgreSQL (Cloud SQL)
- Collaboration: shared pipeline viewing (read-only initially)
- Pipeline template sharing (publish/import)
- Usage tracking and billing infrastructure
- Proper deployment pipeline (CI/CD, staging environment)

**Demo capability:** Live SaaS product. Users sign up, build and run pipelines, save their work, share templates with colleagues.

---

### Phase 5 — Marketplace (Target: ongoing after Phase 4)

**Deliverables:**
- Block publishing: agencies and third parties can package and publish custom blocks
- Pipeline template marketplace: reusable research designs as purchasable/shareable templates
- Versioned block specifications with backward compatibility
- Review/rating system for marketplace content
- Revenue sharing model for marketplace contributors

**Prerequisite:** Block interface contract must be stable and well-documented. Pipeline definition schema must support versioning. These must be designed in Phase 1–2 with marketplace in mind, even though the marketplace itself is built much later.

## Key Architectural Decisions Log

| Decision | Choice | Rationale | Revisit When |
|---|---|---|---|
| Frontend framework | React + React Flow | Most mature graph editor library; large ecosystem | Unlikely to change |
| Backend language | Python / FastAPI | Domain alignment (data science libraries); builder proficiency | Unlikely to change |
| Database (early) | SQLite | Zero setup; sufficient for single-user development | Phase 3–4 (migrate to PostgreSQL) |
| Database (production) | PostgreSQL via Cloud SQL | Relational queries, multi-tenancy, proven at scale | Unlikely to change once adopted |
| Cloud provider | Google Cloud (Cloud Run) | Simplest container hosting for solo developer; scales to zero; good Python SDK | If pricing or features become limiting |
| Pipeline definition format | JSON with typed nodes and edges | Human-readable, easy to serialize, frontend-native | If performance requires binary format |
| Execution model | Async job queue | Non-blocking API; natural HITL support; scalable | Unlikely to change |
| LLM provider | Anthropic (Claude) initially | Quality; builder familiarity | Block config should allow provider swapping |
| Block architecture | Registry-based, file-per-block | Easy to add new blocks; clear separation; marketplace-ready | Unlikely to change |
| Interaction modes | Canvas + CLI + Chat panel | Three modes serve different users (visual, programmatic, conversational) and enable agent integration | Unlikely to change |
| API-first principle | All operations through API; UI/CLI/chat are consumers | Prevents canvas-only features; enables agent integration; single source of truth | Must be enforced from Phase 1 |
| Agent-readiness | LLM-readable schemas, programmatic execution API | Pipeline JSON is already LLM-writable; block contracts must be machine-describable; supports future agent integration without retrofit | Validate when agent features are scoped (Phase 4–5) |

## Agent Integration — Architectural Implications

Agent integration is a Phase 4–5 feature, but it places specific requirements on decisions made in earlier phases. These are documented here so they inform current architecture without requiring current implementation.

### Requirements for Phase 1–2 that enable future agent integration

**Pipeline definition schema must be LLM-readable and LLM-writable.** The current JSON schema satisfies this — an LLM can parse a pipeline definition, understand its structure, and generate a valid new one. This should be preserved as the schema evolves. Avoid formats that require custom parsing or are ambiguous to an LLM.

**Block contracts must include machine-readable descriptions.** Each block's registry entry should include not just input/output schemas and config schemas, but a natural language description of what the block does, when to use it, and what it assumes about its inputs. This is metadata that a human reads for documentation and an agent reads for pipeline composition. Add this to the block base class in Phase 2.

**The execution API must support programmatic triggering.** From Phase 2 onward, pipelines should be runnable via API call, not just via UI button. This is good engineering practice regardless, but it's essential for agent-as-executor mode where an external agent monitors triggers and kicks off pipelines.

**Audit trail is inherent in the graph structure.** Every block execution produces typed output stored on edges. The full execution history of a pipeline is inspectable node by node. This provides the governance and explainability layer that businesses need to trust agentic AI. No additional audit infrastructure is needed — the pipeline graph *is* the audit trail.

### Three integration modes (Phase 4–5)

1. **Agent as Pipeline Executor** — external agent triggers predefined pipelines on schedule or event; pauses at HITL checkpoints. Requires: execution API, webhook/event triggers, HITL notification system.

2. **Agent as Pipeline Composer** — agent assembles pipelines from block library based on natural language goals. Requires: machine-readable block descriptions, pipeline validation API, HITL review of proposed pipelines before execution.

3. **Platform as Agent Workspace** — agent uses the pipeline graph as working memory and planning structure for ongoing business intelligence operations. Requires: all of the above plus multi-pipeline orchestration, persistent agent state, and monitoring dashboards.

## Open Questions for Phase 1

1. **Pipeline definition versioning** — how to handle schema evolution when the pipeline format changes between platform versions?
2. **Block configuration UI** — generic JSON form auto-generated from config schema, or custom UI per block type?
3. **Edge data types** — start with a small fixed vocabulary (respondent_collection, segment_profile_set, concept_brief_set, evaluation_set, text_corpus, generic_blob) or build a type registration system from the start?
4. **Loop representation** — are loops explicitly declared in the pipeline definition (current design) or inferred from the graph topology?
5. **Frontend state management** — React context, Zustand, or Redux for managing the graph editor state?
