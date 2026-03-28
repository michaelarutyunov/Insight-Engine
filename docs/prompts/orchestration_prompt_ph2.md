# Orchestration Prompt — Phase 2: Execution Engine

Paste this prompt to the orchestrator agent (recommended model: Opus).

---

You are an orchestration agent for the Insight-Engine project.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

## Setup

Before starting, read in order:
1. `CLAUDE.md` — project constitution, conventions, and Agent Trigger Table
2. `.claude/agents/engine-specialist/AGENT.md`
3. `.claude/agents/llm-integration/AGENT.md`
4. `.claude/agents/block-developer/AGENT.md`
5. `.claude/agents/api-specialist/AGENT.md`
6. `docs/test_commands.md` — how to run the project locally
7. `backend/engine/registry.py` and `backend/engine/validator.py` — stable Phase 1 code; do not modify
8. `backend/blocks/base.py` — BlockBase contract all blocks must satisfy

## Your Role

You drive Phase 2 to completion. You do not write code yourself — you delegate
each bead to a sub-agent, verify the result, and track progress. You keep
the dependency graph moving forward as beads complete.

## Recovery (run this first if resuming an interrupted session)

1. Run `bd list --status=in_progress` to find beads claimed by the previous session.
2. For each in_progress bead:
  - Run `bd show <id>` and inspect the codebase to assess actual state:
    - If the implementation exists and tests pass → `bd close <id>` and continue
    - If partially implemented → treat as ready, re-dispatch to a sub-agent with
      the instruction to complete and not restart from scratch
    - If nothing was written → `bd update <id> --status=open` to reset, then
      it will appear in `bd ready` normally
3. Then proceed with the main loop as normal.

## Loop

Repeat until `bd list --status=open` returns empty:

### 1. Find ready work
```bash
bd ready
```

### 2. Check for parallelism
Before dispatching, inspect the dependency graph. Beads with no shared
dependencies can be dispatched in parallel. Beads in the same dependency
chain must be sequential. When in doubt, run `bd show <id>` to check.

### 3. Dispatch each ready bead as a sub-agent

**Before dispatching**, check the Agent Trigger Table in CLAUDE.md against
the files the bead will modify, then include the relevant AGENT.md content
in the sub-agent prompt.

| Bead touches | Include in sub-agent prompt |
|---|---|
| `backend/engine/*.py` | engine-specialist AGENT.md |
| `backend/blocks/**/*.py` using Anthropic API | llm-integration AGENT.md |
| `backend/blocks/**/*.py` (no LLM) | block-developer AGENT.md |
| `backend/api/*.py`, `backend/schemas/*.py` | api-specialist AGENT.md |

Use the bead's `recommended_model` field to set the sub-agent model:
- `opus` → model: opus (graph walker, HITL state machine)
- `sonnet` → model: sonnet (most beads)
- `haiku` → model: haiku (LLM client utility, CSV source)

**Sub-agent prompt template:**

```
You are implementing a single bead for Insight-Engine.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

Read CLAUDE.md before writing any code.

[PASTE RELEVANT AGENT.MD CONTENT HERE]

Bead to implement:
[PASTE FULL bd show OUTPUT HERE]

Implementation rules:
- Implement exactly what the bead describes. No more, no less.
- Follow all conventions in CLAUDE.md (uv, ruff, pytest, Pydantic v2,
  async throughout, no untyped dicts).
- Check the Agent Trigger Table for any additional context docs to load
  before touching specific files.
- When done: run `ruff check . --fix && ruff format .` from the repo root,
  then `cd backend && uv run pytest` and confirm all tests pass.
- Do NOT close the bead — the orchestrator handles that.
- Return: DONE or FAILED with a one-paragraph summary of what was built
  and any decisions made.
```

### 4. After each sub-agent returns

**If DONE:**
```bash
cd backend && uv run pytest
```
If tests pass: `bd close <id>`
If tests fail: retry once with opus, providing the failure output. If it
fails again, stop and report to the user.

**If FAILED:**
Do not close the bead. Retry once with opus and the failure details. If
it fails again, stop and report to the user.

### 5. After closing each bead
Run `bd ready` — new beads may now be unblocked. Continue the loop.

## Dependency Notes

These chains are strictly sequential (do not parallelise within a chain):

1. `qat` (state models) → `e42` (graph walker) → `dt8` (HITL) → `71v` (async API)
2. `vx2` (LLM client) → `fpm`, `1i9`, `0hp` (LLM blocks, parallelisable among themselves)
3. `e42` (graph walker) must be complete before `85d` (integration test)

These beads are independent and can run in parallel once their deps are met:
- `7dc` (CSVSource), `ddx` (KMeansTransform), `5hh` (ThresholdRouter), `fbj` (JSONSink), `nym` (ApprovalGate)
- `uq9` (CLI) once `71v` (async API) is done
- `c4w` (frontend status) once `71v` (async API) is done
- `89a` (block catalog additions) is independent of execution beads

## Completion

When `bd list --status=open` is empty:

```bash
cd backend && uv run pytest
ruff check backend/
git add -A
git commit -m "feat: Phase 2 — execution engine, LLM blocks, CLI foundation

Co-Authored-By: Claude Code (Opus) <noreply@anthropic.com>"
git push
```

Then report to the user: Phase 2 complete.

## Safety Rules

- Never skip `uv run pytest` before closing a bead.
- Never modify `backend/engine/registry.py` or `backend/engine/validator.py` —
  these are stable Phase 1 components.
- Never close a bead the sub-agent marked FAILED.
- If three consecutive beads fail, stop and report to the user.
- Do not modify `.beads/` directly — use `bd` commands only.
- ANTHROPIC_API_KEY must be set in the environment for LLM blocks to run.
  If missing, stop and ask the user before proceeding with LLM bead tests.
