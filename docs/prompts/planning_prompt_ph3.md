# Planning Prompt — Phase 3: Block Library Expansion

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
6. `backend/blocks/base.py` — base classes including ReportingBase, ComparatorBase
7. Run `bd list --status=closed` to understand what Phases 1 and 2 delivered

## Your Task

Create a complete set of beads for Phase 3. Every bead must have:
- Bounded, single-deliverable description
- Explicit acceptance criteria (`--acceptance`)
- `complexity` and `recommended_model` in notes (`--notes`)
- No deferred decisions

## Phase 3 Deliverables (from blueprint)

### Block Library

New blocks to add (one bead each):

**Sources:** database connector (SQLite/Postgres query), sample provider stub (Cint/Lucid API shape)

**Transforms:** LCA segmentation, RFM scoring, data cleaning (missing values/outliers), weighting, column recoding

**Generation:** concept drafter, discussion guide generator, stimulus material creator

**Reporting:** PDF report builder, narrative report writer, presentation outline generator

**Comparator:** already have `side_by_side_comparator` — assess if additional variants needed

**Sinks:** API push (POST to external endpoint), notification sink (log/webhook)

### Chat Panel (backend + frontend)

Two modes, two beads:
- **Research assistant mode**: `POST /api/v1/chat` accepts `{message, pipeline_id?}`, injects current pipeline JSON + block catalog as context, returns LLM response. Frontend: chat drawer component.
- **Co-pilot mode**: `POST /api/v1/chat/modify` accepts `{instruction, pipeline_id}`, LLM reads pipeline JSON, returns a modified pipeline JSON diff, frontend validates and applies it with user confirmation.

### CLI Expansion

Extend the existing `insights` CLI (Typer):
- `insights pipeline validate <pipeline-file>` — validate a local JSON file against the schema
- `insights pipeline create --from-template <name>` — scaffold from a built-in template
- `insights run resume <run-id> --hitl-response <file>` — resume a suspended run from CLI

### Frontend Improvements

- Richer config panel: support `enum` → select, `boolean` → checkbox, `array` → tag input (extends Phase 1 config panel which only handled `string`/`integer`)
- Pipeline templates: template picker dialog on "New Pipeline"

### Pipeline Templates

Define 3 built-in templates as JSON fixtures stored in `backend/templates/`:
1. Concept pre-screen (CSVLoader → KMeansTransform → ConceptEvaluation → ThresholdRouter → MarkdownReport)
2. Discussion guide builder (CSVLoader → FilterTransform → LLMGeneration → PromptFlex → JSONSink)
3. Segmentation report (CSVLoader → KMeansTransform → MarkdownReport → JSONSink)

## Dependency Constraints

- All new blocks depend on: existing `BlockBase` contract (stable — no changes needed)
- LLM-powered generation blocks depend on: `_llm_client.py` (stable from Phase 2)
- Chat panel backend depends on: existing pipeline CRUD API + block catalog API
- Chat co-pilot depends on: chat research assistant (shares API foundation)
- CLI expansion depends on: existing Phase 2 CLI foundation
- Frontend config panel improvements depend on: existing Phase 1 config panel bead
- Pipeline templates depend on: new blocks they reference being implemented

## Constraints

- New blocks: same conventions as Phase 2 (one file per impl, `blocks/{type}/{impl}.py`, full BlockBase contract)
- PDF report builder: use `reportlab` or `weasyprint` — decide and commit in the bead description
- Chat panel: backend uses `AsyncAnthropic`, pipeline JSON injected as system context, max_tokens 4096
- CLI: extend existing Typer app, do not create a new entry point
- No frontend framework changes

## After Creating Beads

1. Wire all dependencies with `bd dep add`
2. Run `/check_bd` to review for ambiguity
3. Present a dependency graph summary showing the critical path and which beads can be parallelised
