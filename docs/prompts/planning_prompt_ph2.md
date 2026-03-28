You are a senior software architect planning Phase 2 of the Insight-Engine project.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

## Your task

Read the following, in order:
1. CLAUDE.md (project constitution and conventions)
2. docs/initiation/insights-ide-technical-blueprint.md (full build plan)
3. docs/initiation/codified-context-guide.md
4. .claude/context/ — all context documents (execution engine, block contracts, edge types, pipeline schema)
5. backend/engine/ — existing skeleton files (executor.py, validator.py, state.py, registry.py)
6. backend/blocks/base.py — BlockBase contract
7. Run `bd list --status=closed` to understand what Phase 1 delivered

Then create a complete set of beads for Phase 2 using `bd create`.

## Requirements for the bead set

- One epic bead for Phase 2 overall
- Individual task beads for each deliverable (granular enough for a single sub-agent to implement in one session)
- Wire up all dependencies with `bd dep add`
- Every bead must have:
- Clear, bounded description (one thing, one deliverable)
- Explicit acceptance criteria (`--acceptance`)
- complexity and recommended_model metadata (`--notes`)
- No deferred decisions — architecture choices made now, not at implementation time

## Phase 2 deliverables to cover (from the blueprint)

1. Graph walker / execution engine — traverses pipeline definition, executes blocks in dependency order, handles parallel branches
2. Async execution — job queue pattern; POST /api/v1/execution/run returns run_id immediately, frontend polls GET /api/v1/execution/{run_id}/status
3. HITL suspend/resume — state persistence when execution hits a HITL block; POST /api/v1/hitl/{run_id}/respond to resume
4. Execution status frontend — per-node progress indicator on canvas, polling loop
5. 8 concrete block implementations (one bead each):
    - CSVSource, KMeansTransform, PersonaGeneration (LLM), ConceptEvaluation (LLM), PromptFlex, ThresholdRouter, ApprovalGate (HITL), JSONSink
6. CLI foundation — Typer CLI wrapping existing API: pipeline list/run/status, block list/inspect

## Constraints
- Backend: FastAPI, Pydantic v2, aiosqlite, uv
- LLM blocks: Anthropic API (claude-sonnet-4-6 default, configurable per block)
- Async execution: use asyncio + background tasks (no external queue in Phase 2; job queue is a Phase 3 concern)
- CLI: Typer, installed as `insights` command via pyproject.toml entry point
- No frontend framework changes — extend existing React Flow canvas from Phase 1

After creating all beads, run `/check_bd` to review them for ambiguity, then present a dependency graph summary showing the critical path