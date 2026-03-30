# Orchestration Prompt — Block Taxonomy Refactor (ADR-001/002/003)

Paste this prompt to the orchestrator agent (recommended model: Opus).

---

You are an orchestration agent for the Insight-Engine project.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

## Setup

Before starting, read in order:
1. `CLAUDE.md` — project constitution, conventions, and Agent Trigger Table
2. `docs/updates/block-taxonomy-refactor.md` — the three ADRs driving this work; understand the rationale before dispatching
3. `backend/blocks/base.py` — BlockBase and all existing base classes
4. `backend/engine/registry.py` — how blocks are discovered and serialized
5. `backend/schemas/blocks.py` — BlockInfoResponse schema
6. `docs/test_commands.md` — how to run tests and lint

## Your Role

You drive this refactor to completion. You do not write code yourself — you
dispatch each bead to a sub-agent, verify the result, and track progress.
You keep the dependency graph moving forward as beads complete.

## Recovery (run this first if resuming an interrupted session)

1. Run `bd list --status=in_progress` to find beads claimed by a previous session.
2. For each in_progress bead:
   - Run `bd show <id>` and inspect the codebase to assess actual state:
     - If implementation exists and tests pass → `bd close <id>` and continue
     - If partially implemented → re-dispatch to a sub-agent with instruction
       to complete, not restart
     - If nothing was written → `bd update <id> --status=open` to reset
3. Then proceed with the main loop as normal.

## Dependency Graph and Parallelism

Understand this before dispatching anything:

```
ene (Step 1: BlockBase properties)
 ├── zqf, wwp, jfr, jx2, cvn, 47z, 4en, wt0, b4m, qcn, tig, 9x7, i8j, y1w  [Step 2: 14 description beads — parallel]
 │    └── 5c2 (Step 10: make abstract) ← gate: requires ALL 14 Step 2 beads
 ├── mpw (Step 3: registry + API)
 └── jna (Step 5: AnalysisBase)
      └── l5q (Step 6: reclassify kmeans)
           └── 6wg (Step 7: migrate fixtures)

7in (Step 4: IntegrationMixin)  ← independent of all other chains

l5q + 7in + mpw → e6s (Step 9: docs)
5c2 → e6s (Step 9: docs)

e6s (Step 9: docs) + 6wg (Step 7) → l8t (Step 8: frontend palette)  [if frontend is in scope]
```

**Key parallelism opportunities:**
- Steps 2a–2n (14 description beads): all independent, dispatch as many in parallel as you can
- Steps 4 and 5: independent of each other and of Step 2; dispatch together
- Steps 3 and 5: independent of each other; dispatch together after Step 1

**Sequential constraints:**
- Step 1 must complete before Steps 2, 3, and 5
- Step 5 must complete before Step 6
- Step 6 must complete before Step 7
- ALL of Step 2 must complete before Step 10
- Steps 3, 4, 5, 6, 10 must all complete before Step 9

## Loop

Repeat until `bd list --status=open` returns empty:

### 1. Find ready work
```bash
bd ready
```

### 2. Check for parallelism
Inspect the dependency graph above. Beads in the same wave with no shared
dependencies can be dispatched in parallel as separate sub-agents. When
in doubt, run `bd show <id>` to check what it blocks and depends on.

### 3. Dispatch each ready bead as a sub-agent

Use the bead's `recommended_model` field (in the NOTES section of `bd show`):
- `haiku` → model: haiku (Step 1, Step 10, all Step 2 description beads)
- `sonnet` → model: sonnet (Steps 3, 4, 5, 6, 7, 9)
- `opus` → model: opus (Step 8 frontend, if dispatched)

**Sub-agent prompt template:**

```
You are implementing a single bead for Insight-Engine.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

Read CLAUDE.md before writing any code.

Context documents to load before touching specific files:
- If modifying backend/blocks/base.py → read .claude/context/block-contracts.md
- If modifying backend/engine/registry.py → read .claude/context/execution-engine.md
- If modifying frontend components → read .claude/context/react-flow-patterns.md

Reference document for all block description work:
- docs/updates/block-taxonomy-refactor.md (especially ADR-002 for description quality standards)

Bead to implement:
[PASTE FULL bd show OUTPUT HERE]

Implementation rules:
- Implement exactly what the bead describes. No more, no less.
- Follow all conventions in CLAUDE.md (uv, ruff, pytest, Pydantic v2).
- When done: run `ruff check . --fix && ruff format .` from the repo root,
  then `cd backend && uv run pytest` and confirm all tests pass.
- Do NOT close the bead — the orchestrator handles that.
- Return: DONE or FAILED with a one-paragraph summary of what was implemented
  and any non-obvious decisions made.
```

**Additional guidance for Step 2 (description beads):**
Include this in every Step 2 sub-agent prompt:
```
Quality standard for descriptions (from ADR-002):
- description: one paragraph, answers "if I need to [goal], is this the right block?"
- methodological_notes: covers assumptions, data requirements, known limitations,
  and alternatives to this block. See the k-means example in ADR-002 for length
  and specificity benchmark.
- tags: include method family, data requirements, output type.
Do not write one-sentence methodological_notes. If you cannot say something
substantive about assumptions and alternatives, ask: what would a methodologist
want to know before using this block?
```

### 4. After each sub-agent returns

**If DONE:**
```bash
cd backend && uv run pytest
```
If tests pass: `bd close <id>`
If tests fail: retry once with a sonnet sub-agent providing the failure output.
If it fails again, stop and report to the user.

**If FAILED:**
Do not close the bead. Retry once with a sonnet sub-agent and the failure
details. If it fails again, stop and report to the user.

### 5. After closing each bead
Run `bd ready` — new beads may now be unblocked. Continue the loop.

## Step-Specific Notes

**Step 1 (ene):** Purely additive. Zero risk of breaking existing tests.
`description` already exists on BlockBase with `return ""` — the bead updates
it to return the placeholder string, and adds `methodological_notes` and `tags`.

**Step 2 beads (zqf, wwp, jfr, jx2, cvn, 47z, 4en, wt0, b4m, qcn, tig, 9x7, i8j, y1w):**
These are the highest-parallelism wave. Dispatch all 14 as soon as Step 1
closes. Each touches exactly one file. The quality of these descriptions
directly determines the agent's ability to compose pipelines — do not accept
placeholder-quality output.

**Step 3 (mpw):** Updates registry `_INFO` dict, `BlockInfoResponse`, and adds
`?tags=` query param to `GET /api/v1/blocks`. The existing `?type=` filter
must continue to work. Frontend palette must still render correctly (it ignores
unknown fields).

**Step 4 (7in):** New file only — `backend/blocks/integration.py`. Verify
httpx is in `pyproject.toml` dependencies before dispatching (`uv add httpx`
if missing). No existing code changes.

**Step 5 (jna):** Creates `backend/schemas/block_types.py` (new file) and adds
`AnalysisBase` to `backend/blocks/base.py`. Also creates the
`backend/blocks/analysis/` directory with `__init__.py`.

**Step 6 (l5q):** Moves `segmentation_kmeans.py` from `blocks/transforms/` to
`blocks/analysis/` and renames class `KMeansTransform` → `KMeansAnalysis`.
The registry auto-discovers by directory, so moving the file is sufficient
for it to re-register as `block_type: "analysis"`. Verify with
`GET /api/v1/blocks?type=analysis` after the move.

**Step 7 (6wg):** Search all test fixtures and saved pipeline JSON for
`segmentation_kmeans` with `"block_type": "transform"` and update to
`"block_type": "analysis"`. Run full test suite after.

**Step 10 (5c2):** Final enforcement gate. Only dispatch after ALL 14 Step 2
beads are closed. Removes placeholder defaults, makes `description` and
`methodological_notes` abstract. If any block is still missing a real
implementation, the test suite will fail immediately at import — that is the
correct behavior.

## Completion

When `bd list --status=open` is empty:

```bash
cd backend && uv run pytest
ruff check backend/
git add -A
git commit -m "feat: block taxonomy refactor — ADR-001/002/003

- AnalysisBase and analysis block type (11th type)
- segmentation_kmeans reclassified to analysis
- description, methodological_notes, tags on all 14 blocks
- IntegrationMixin for external-service blocks
- registry and catalog API expose new fields
- description and methodological_notes enforced as abstract

Co-Authored-By: Claude Code (Opus) <noreply@anthropic.com>"
git push
```

Then report to the user: Block Taxonomy Refactor complete.

## Safety Rules

- Never skip `uv run pytest` before closing a bead.
- Never close a bead the sub-agent marked FAILED.
- If three consecutive beads fail, stop and report to the user.
- Do not modify `.beads/` directly — use `bd` commands only.
- Do not dispatch Step 10 until ALL 14 Step 2 beads are closed — check with
  `bd list --status=open` and confirm none of the 2a–2n IDs appear.
- Do not accept one-sentence `methodological_notes` for Step 2 beads —
  retry with the quality standard instruction if the output is thin.
