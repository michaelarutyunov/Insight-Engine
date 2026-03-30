# Planning Prompt — Phase 3: Block Library, Chat Panel & Research Advisor

Paste this prompt to the planning agent (recommended model: Opus).

---

You are a senior software architect planning Phase 3 of the Insight-Engine project.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

## Setup

Read in order:
1. `CLAUDE.md` — project constitution, conventions, Agent Trigger Table
2. `docs/initiation/insights-ide-technical-blueprint.md` — full build plan
3. `docs/block-catalog.md` — all existing blocks (do not duplicate these)
4. `.claude/context/block-contracts.md` — BlockBase interface all blocks must implement
5. `.claude/context/execution-engine.md` — how blocks are executed
6. `.claude/context/reasoning-layer.md` — dimensional model, progressive refinement stages, advisor/copilot boundary
7. `.claude/agents/reasoning-specialist/AGENT.md` — advisor architecture
8. `backend/blocks/base.py` — base classes including AnalysisBase, ReportingBase, ComparatorBase
9. `backend/chat/research_advisor.py` — existing ResearchAdvisor skeleton (placeholder methods to be replaced)
10. `backend/reasoning/` — existing dimensions, profiles, workflows modules
11. `reasoning_profiles/default/` — existing default profile and segmentation workflow
12. `backend/api/advise.py` — existing advise endpoints (skeleton, to be wired)
13. Run `bd list --status=closed` to understand what Phases 1, 2 and the reasoning layer foundations delivered

## Your Task

Create a complete set of beads for Phase 3. Every bead must have:
- Bounded, single-deliverable description
- Explicit acceptance criteria (`--acceptance`)
- `complexity` and `recommended_model` in notes (`--notes`)
- No deferred decisions

## Phase 3 Deliverables

### 1. Chat Infrastructure (shared foundation — build first)

One bead: **`backend/chat/context_builder.py`**

This module assembles LLM context for all three chat modes (assistant, copilot, advisor). Build it as a shared foundation before any of the three modes.

- `build_pipeline_context(pipeline_id) -> str` — serializes current pipeline JSON as readable context
- `build_block_catalog_context(block_type_filter=None) -> str` — formats block catalog (with descriptions, methodological_notes, dimensions) for LLM consumption
- `build_advisor_context(profile: ReasoningProfile, candidates: List[MethodCandidate] = None) -> str` — assembles reasoning profile preferences + any candidate methods + relevant practitioner workflows for advisor stages
- Uses `engine.registry.list_blocks()` and `reasoning.workflows.get_workflow_for_block()` internally
- No LLM calls in this module — pure context assembly

### 2. ResearchAdvisor LLM Implementation

Three beads, one per stage. Each replaces placeholder return in `backend/chat/research_advisor.py`.

**Bead A — Stage 1: `characterize_problem()`**
Replace placeholder with a real LLM call using `AsyncAnthropic`. System prompt includes: dimension definitions (from `reasoning/dimensions.py`), situational attribute vocabulary, instruction to return structured JSON. Parse response into `ProblemProfile` with both `dimensions: Dict[str, str]` (validated against allowed sets) and `situational_context: SituationalContext`. Use `claude-sonnet-4-6` as default, configurable.

**Bead B — Stage 2: `match_candidates()`**
Two-pass implementation:
1. Mechanical filter: call `engine.registry.list_blocks(type="analysis")`, filter by dimensional compatibility using the `ProblemProfile.dimensions` and the reasoning profile's `dimension_weights`
2. LLM ranking: pass filtered candidates + `ProblemProfile.situational_context` to LLM, ask it to rank and explain fit. Return `List[MethodCandidate]` (3–6 items) with `fit_score`, `fit_reasoning`, `tradeoffs`.

**Bead C — Stage 3: `recommend()`**
LLM call with: candidate list, constraints, and the relevant practitioner workflow (loaded via `reasoning.workflows.get_workflow_for_block()` for the top candidate). Returns `Recommendation` with `selected_method`, `rationale`, and `pipeline_sketch` (a rough node list with block types and connections — not a full pipeline JSON, just a shape).

**Advisor dependency note:** All three stage beads depend on the context_builder bead. Stages 2 and 3 depend on Stage 1 (sequential — output of one feeds next in the chain).

### 3. Advise API — Wire to Real Implementation

One bead: update `backend/api/advise.py` to call the real ResearchAdvisor methods instead of returning placeholders. Add `profile` query parameter support to all three POST endpoints. Verify end-to-end: `POST /api/v1/advise/characterize` with a real research question returns a populated `ProblemProfile`.

Depends on: all three ResearchAdvisor stage beads.

### 4. CLI: `insights advise` command

One bead: add `insights advise "<research question>"` to the existing Typer CLI. Calls `POST /api/v1/advise/characterize` then `POST /api/v1/advise/match`, prints ranked method candidates with fit reasoning. Optional `--recommend` flag runs Stage 3 and prints the full recommendation with pipeline sketch. This is the demo-ready entry point for agentic reasoning.

Depends on: advise API wire-up bead.

### 5. Chat Panel (backend + frontend)

**Context builder must exist before these beads.**

**Bead: Research assistant mode**
`POST /api/v1/chat` accepts `{message, pipeline_id?}`, uses `context_builder.build_pipeline_context()` + `build_block_catalog_context()` as system context, streams LLM response. Frontend: chat drawer component (slide-in panel, message history, input box).

**Bead: Co-pilot mode**
`POST /api/v1/chat/modify` accepts `{instruction, pipeline_id}`, LLM reads pipeline JSON and returns a modified pipeline JSON diff, frontend validates and applies with user confirmation. Uses `context_builder.build_pipeline_context()`.

Both depend on: context_builder bead.

### 6. Block Library

New blocks — one bead each. All must pass generic contract tests and include `test_fixtures()`.

**Sources:**
- Database connector (`db_source`) — SQLite/Postgres query via connection string + SQL config; returns `respondent_collection`
- Sample provider stub (`sample_provider_source`) — inherits `SourceBase + IntegrationMixin`; models Cint/Lucid API shape; returns `respondent_collection`; uses `call_external()` from IntegrationMixin

**Transforms:**
- LCA segmentation (`segmentation_lca`) — `AnalysisBase`; categorical/mixed features; uses `prince` library; requires `dimensions` property (see method_classification_draft.md: `mixed`, `high`, `high`, `high`, `medium`, `categorical`)
- RFM scoring (`rfm_analysis`) — `AnalysisBase`; transaction data; produces customer value segments; `dimensions`: `confirmatory`, `medium`, `high`, `medium`, `high`, `numeric_continuous`
- Data cleaning (`data_cleaning`) — `TransformBase`; configurable missing value handling (drop/impute) and outlier treatment
- Weighting (`weighting`) — `TransformBase`; rim weighting to target marginals; uses `ipfn` or manual raking
- Column recoding (`column_recoding`) — `TransformBase`; value mapping and binning via config

**Generation:**
- Concept drafter (`concept_drafter`) — `GenerationBase`; LLM-powered; uses `_llm_client.py`
- Discussion guide generator (`discussion_guide`) — `GenerationBase`; LLM-powered
- Stimulus material creator (`stimulus_creator`) — `GenerationBase`; LLM-powered

**Reporting:**
- PDF report builder (`pdf_report`) — `ReportingBase`; use `weasyprint` (decided); renders markdown → PDF
- Narrative report writer (`narrative_report`) — `ReportingBase`; LLM-powered narrative synthesis
- Presentation outline generator (`presentation_outline`) — `ReportingBase`; LLM-powered

**Sinks:**
- API push (`api_push_sink`) — `SinkBase + IntegrationMixin`; POSTs output to configurable endpoint
- Notification sink (`notification_sink`) — `SinkBase`; logs to file or fires webhook

**New Analysis blocks must also have:**
- `description` and `methodological_notes` (ADR-002, enforced as abstract)
- `dimensions` dict with all 6 keys validated against `reasoning/dimensions.py` allowed sets
- Use `method_classification_draft.md` as reference for dimension values

### 7. CLI Expansion

Extend existing `insights` Typer CLI (one bead):
- `insights pipeline validate <pipeline-file>` — validate a local JSON file
- `insights pipeline create --from-template <name>` — scaffold from built-in template
- `insights run resume <run-id> --hitl-response <file>` — resume a suspended HITL run

### 8. Frontend Improvements (one bead each)

- Richer config panel: `enum` → select, `boolean` → checkbox, `array` → tag input
- Pipeline templates: template picker dialog on "New Pipeline"

### 9. Pipeline Templates

Three built-in template JSON fixtures in `backend/templates/` (one bead):
1. Concept pre-screen: `csv_source → filter_transform → concept_evaluator → threshold_router → markdown_report`
2. Discussion guide builder: `csv_source → filter_transform → llm_generation → prompt_flex → json_sink`
3. Segmentation report: `csv_source → segmentation_kmeans → markdown_report → json_sink`

## Dependency Constraints

- `context_builder` bead must complete before chat assistant, chat copilot, and all advisor stage beads
- ResearchAdvisor stages are sequential: Stage 1 → Stage 2 → Stage 3
- Advise API wire-up depends on all three ResearchAdvisor stage beads
- `insights advise` CLI depends on advise API wire-up
- LCA and RFM blocks depend on nothing new — `AnalysisBase` already exists
- LLM generation blocks depend on: `_llm_client.py` (stable from Phase 2)
- PDF report builder: `weasyprint` must be added via `uv add weasyprint`
- Sample provider stub: `IntegrationMixin` already exists in `blocks/integration.py`
- Pipeline templates depend on the blocks they reference being implemented
- Frontend improvements are independent of all backend beads

## Constraints

- New blocks: `blocks/{type}/{impl}.py`, full BlockBase contract, `test_fixtures()`
- New Analysis blocks: `dimensions` property required (abstract on `AnalysisBase`) — no Analysis block without it
- ResearchAdvisor: use `AsyncAnthropic`, model `claude-sonnet-4-6` default, configurable per call
- All advisor LLM responses must be parsed into typed Pydantic models — no free-text passthrough to callers
- Chat panel: `AsyncAnthropic`, streaming preferred for assistant mode, max_tokens 4096
- CLI: extend existing Typer app, do not create a new entry point
- No frontend framework changes
- `weasyprint` for PDF (not `reportlab`)

## After Creating Beads

1. Wire all dependencies with `bd dep add`
2. Run `/check_bd` to review for ambiguity
3. Present a dependency graph summary showing the critical path and which beads can be parallelised — pay particular attention to: (a) the context_builder → advisor stages → advise API → CLI chain as the critical demo path, and (b) the large parallel block library work that can run alongside it
