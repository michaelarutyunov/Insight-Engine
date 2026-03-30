# Orchestration Prompt — Reasoning Layer Foundations (ADR-004/005/006/007)

Paste this prompt to the orchestrator agent (recommended model: Opus).

---

You are an orchestration agent for the Insight-Engine project.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

## Setup

Before starting, read in order:
1. `CLAUDE.md` — project constitution, conventions, and Agent Trigger Table
2. `docs/initiation_reasoning_layer/reasoning-layer-design.md` — design rationale (especially the dimensions vs situational context distinction and the 4-stage progressive refinement model)
3. `docs/initiation_reasoning_layer/reasoning-layer-adrs.md` — ADR-004 through ADR-007
4. `docs/initiation_reasoning_layer/method_classification_draft.md` — 32 methods pre-scored on all 6 dimensions (reference for sub-agents implementing dimensions)
5. `.claude/agents/reasoning-specialist/AGENT.md` — the specialist agent for this module
6. `backend/blocks/base.py` — confirm what AnalysisBase currently has (taxonomy refactor may have delivered it)
7. `docs/test_commands.md` — how to run tests

## Your Role

You drive this epic to completion. You do not write code yourself — you dispatch each bead to a sub-agent, verify the result, and track progress.

## Recovery (run this first if resuming an interrupted session)

1. `bd list --status=in_progress` — find beads from a prior session
2. For each in_progress bead:
   - `bd show <id>` + inspect codebase to assess actual state
   - Implementation exists and tests pass → `bd close <id>`
   - Partially implemented → re-dispatch with instruction to complete, not restart
   - Nothing written → `bd update <id> --status=open` to reset
3. Proceed with main loop

## Dependency Graph and Parallelism

```
gdc (Task 1: reasoning package)   ← start here, no deps
 ├── 8qn (Task 2: AnalysisBase extensions)
 │    └── 9g2 (Task 3: score kmeans) ─────────────┐
 ├── 7fj (Task 5: ResearchAdvisor skeleton)        │
 │    └── wos (Task 6: advise API) ────────┐       │
 │          └── x8z (Task 4: default       │       │
 │                   profile) ─────────────┤       │
 └── 8ro (Task 7: extend block catalog)    │       │
                                           │       │
           wo3 (Task 8: tests) ← depends on ALL of: 8qn, 9g2, 7fj, 8ro, x8z, gdc
           0jt (Task 9: docs) ← last, after wo3 closes
```

**Parallel waves:**
- Wave 1: `gdc` alone (no dependencies)
- Wave 2 (after gdc): `8qn`, `7fj` in parallel
- Wave 3 (after 8qn): `9g2` and `8ro` in parallel; `x8z` can start after `9g2`
- Wave 4 (after 7fj + x8z): `wos`
- Wave 5 (after all above): `wo3`
- Wave 6 (after wo3): `0jt`

## Loop

Repeat until `bd list --status=open` returns empty:

### 1. Find ready work
```bash
bd ready
```

### 2. Check for parallelism
Use the graph above. When a wave completes, immediately check `bd ready` for newly unblocked beads.

### 3. Dispatch each ready bead as a sub-agent

Use the bead's `recommended_model` from the NOTES section:
- `haiku` → model: haiku (Task 3 only)
- `sonnet` → model: sonnet (Tasks 1, 2, 5, 6, 7, 8, 9)

**Sub-agent prompt template:**

```
You are implementing a single bead for Insight-Engine.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

Read CLAUDE.md before writing any code.

Context documents to load before touching specific files:
- Modifying backend/reasoning/*.py → read .claude/context/reasoning-layer.md
- Modifying backend/chat/research_advisor.py → read .claude/context/reasoning-layer.md
- Modifying backend/blocks/base.py → read .claude/context/block-contracts.md
- Modifying backend/engine/registry.py or backend/schemas/blocks.py → read .claude/context/reasoning-layer.md

Agent spec relevant to this bead:
[PASTE FULL CONTENT OF .claude/agents/reasoning-specialist/AGENT.md HERE
 OR .claude/agents/block-developer/AGENT.md if bead touches blocks/base.py]

Bead to implement:
[PASTE FULL bd show OUTPUT HERE]

Implementation rules:
- Implement exactly what the bead describes. No more, no less.
- Follow all conventions in CLAUDE.md (uv, ruff, pytest, Pydantic v2).
- When done: run `ruff check . --fix && ruff format .` from the repo root,
  then `cd backend && uv run pytest` and confirm all tests pass.
- Do NOT close the bead — the orchestrator handles that.
- Return: DONE or FAILED with a one-paragraph summary of what was built
  and any non-obvious decisions made.
```

### 4. After each sub-agent returns

**If DONE:**
```bash
cd backend && uv run pytest
```
Tests pass → `bd close <id>`
Tests fail → retry once with a sonnet sub-agent providing the failure output. Two consecutive failures → stop and report to user.

**If FAILED:**
Retry once with the failure details. Two consecutive failures → stop and report to user.

### 5. After closing each bead
```bash
bd ready
```
Continue the loop with newly unblocked beads.

## Bead-Specific Notes

**gdc (Task 1 — reasoning package):**
First thing to check: run `uv pip show pyyaml` from the backend directory. If missing, run `uv add pyyaml` before dispatching. This bead has no code dependencies but is the critical blocker for most of the graph — dispatch it immediately.

**8qn (Task 2 — AnalysisBase extensions):**
Read `backend/blocks/base.py` before dispatching. The taxonomy refactor may have already added `AnalysisBase` with `block_type = "analysis"` and `preserves_input_type = False`. The sub-agent only needs to add `dimensions` (abstract on AnalysisBase, concrete `{}` default on BlockBase) and `practitioner_workflow` (concrete `None` default on BlockBase). Confirm with the sub-agent that it should not re-create AnalysisBase from scratch.

**9g2 (Task 3 — score kmeans):**
The bead description notes a discrepancy: implementation spec says `sample_sensitivity: "high"`, method_classification_draft.md says `"medium"`. The bead resolves this in favor of `"high"` (implementation spec is authoritative). Include this decision explicitly in the sub-agent prompt so it doesn't re-open the question. The block lives at `backend/blocks/analysis/segmentation_kmeans.py` after the taxonomy refactor.

**x8z (Task 4 — default profile + segmentation workflow):**
Two critical YAML pitfalls to include in the sub-agent prompt:
1. All `dimension_weights` values must be floats: write `1.0` not `1` — YAML parses bare integers as `int`, Pydantic rejects them as `float`
2. The profile lives at `reasoning_profiles/default/profile.yaml` (repo root, NOT inside `backend/`)
The segmentation practitioner workflow must cover all four sections: pre-analysis checks, method selection guidance within family, execution steps, reporting requirements. Include this quality requirement in the prompt.

**7fj (Task 5 — ResearchAdvisor skeleton):**
The sub-agent must create `backend/chat/` directory with `__init__.py` — it does not yet exist. Emphasize: `ProblemProfile` must have BOTH `dimensions: Dict[str, str]` AND `situational_context: SituationalContext` as separate fields. These must not be merged. No LLM calls — all three async methods return structured placeholders.

**wos (Task 6 — advise API):**
ResearchAdvisor instantiation detail: use `engine.registry` module as block_registry and `reasoning.profiles.load_profile(Path("reasoning_profiles/default/profile.yaml"))` as the default reasoning profile. All three POST endpoints (characterize, match, recommend) accept an optional `profile` query parameter to override the default. All five endpoints must return 200 with valid typed responses. Register router in `backend/main.py`.

**8ro (Task 7 — extend block catalog):**
`dimensions` and `practitioner_workflow` are optional fields in `BlockInfoResponse` — blocks that are not Analysis blocks will not have them. Only include these fields in `_INFO` and the response schema if non-empty/non-None. The existing `description`, `methodological_notes`, and `tags` fields (from taxonomy refactor) must not be broken.

**wo3 (Task 8 — tests):**
This is the verification gate. Dispatch only after ALL of gdc, 8qn, 9g2, 7fj, 8ro, and x8z are closed. The `test_analysis_contract.py` test must auto-discover all registered Analysis blocks via the registry — not a hardcoded list. Confirm all test files exist and all tests pass before closing.

**0jt (Task 9 — docs):**
Last to close. `insights-ide-technical-blueprint.md` directory tree needs `reasoning/`, `reasoning_profiles/`, and `chat/research_advisor.py`. Any block-catalog document needs an Analysis section if not already present from the taxonomy refactor.

## Completion

When `bd list --status=open` returns only the epic (`Insight-Engine-c7r`):

```bash
cd backend && uv run pytest
ruff check backend/
git add -A
git commit -m "feat: reasoning layer foundations — ADR-004/005/006/007

- backend/reasoning/ package: dimensions, profiles, workflows
- AnalysisBase extended with dimensions (abstract) and practitioner_workflow
- segmentation_kmeans dimensional profile scored
- default reasoning profile + segmentation practitioner workflow
- ResearchAdvisor skeleton (placeholder, Phase 3 for LLM)
- /api/v1/advise/* and /api/v1/reasoning-profiles/* endpoints
- block catalog API exposes dimensions and practitioner_workflow
- full test coverage across all new modules

Co-Authored-By: Claude Code (Opus) <noreply@anthropic.com>"
git push
```

Then close the epic: `bd close Insight-Engine-c7r`

Report to the user: Reasoning Layer Foundations complete.

## Safety Rules

- Never skip `uv run pytest` before closing a bead.
- Never close a bead the sub-agent marked FAILED.
- Never dispatch wo3 (Task 8: tests) until ALL of gdc, 8qn, 9g2, 7fj, 8ro, x8z are closed.
- Never close the epic until wo3 and 0jt are both closed.
- Do not modify `.beads/` directly — use `bd` commands only.
- If three consecutive sub-agents fail, stop and report to the user.
- `reasoning_profiles/` is at the repo root, not inside `backend/` — flag this if a sub-agent tries to put it elsewhere.
