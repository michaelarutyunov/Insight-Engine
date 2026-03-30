# Orchestration Prompt — Phase 3: Block Library, Chat Panel & Research Advisor

Paste this prompt to the orchestrator agent (recommended model: Opus).

---

You are an orchestration agent for the Insight-Engine project.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

## Setup

Before starting, read in order:
1. `CLAUDE.md` — project constitution, conventions, and Agent Trigger Table
2. `docs/prompts/planning_prompt_ph3.md` — Phase 3 deliverables reference (use for context when bead descriptions are ambiguous)
3. `.claude/context/reasoning-layer.md` — dimensional model, 32-method classification table
4. `.claude/context/chat-architecture.md` — three chat modes, context_builder role, streaming patterns, ownership map
5. `.claude/context/block-contracts.md` — BlockBase contract, AnalysisBase dimensions requirement
6. `.claude/agents/reasoning-specialist/AGENT.md` — advisor stages, context_builder spec
7. `.claude/agents/block-developer/AGENT.md` — block contract rules, dimensions property, IntegrationMixin
8. `.claude/agents/llm-integration/AGENT.md` — AsyncAnthropic, streaming, prompt construction, test mocking
9. `.claude/agents/canvas-specialist/AGENT.md` — React Flow patterns, Zustand store, chat panel, streaming frontend
10. `docs/test_commands.md` — how to run tests

## Your Role

You drive Phase 3 to completion. You do not write code yourself — you dispatch each bead to a sub-agent, verify the result, and track progress.

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
13o (context_builder)                         ← Wave 1: start here, no deps
 ├── pqt (Advisor Stage 1: characterize)      ← Wave 2
 │    └── 8dn (Advisor Stage 2: match)        ← Wave 3
 │         ├── p18 (Advisor Stage 3: recommend) ← Wave 4
 │         └── (p18 also depends on 13o)
 │              └── 28m (Advise API wire-up)  ← Wave 5
 │                   └── 2gt (CLI: advise)   ← Wave 6
 ├── hfp (Chat: research assistant)           ← Wave 2 (parallel with pqt)
 └── 3dv (Chat: co-pilot)                     ← Wave 2 (parallel with pqt)

Block library (all independent — run across all waves):
  py6  db_source
  l0g  sample_provider_source
  ee7  segmentation_lca
  azw  rfm_analysis
  g6e  data_cleaning
  9pd  weighting
  0i2  column_recoding
  oup  concept_drafter
  0f5  discussion_guide
  yre  stimulus_creator
  3ro  pdf_report
  na9  narrative_report
  kxt  presentation_outline
  thf  api_push_sink
  laq  notification_sink

CLI / Frontend (independent — run across all waves):
  gni  CLI expansion (blocked by 1pj pipeline templates)
  fgt  Frontend: richer config panel ← NOTE: likely already done (see bead-specific notes)
  1pj  Pipeline templates
  9hr  Frontend: template picker (blocked by 1pj)

Epic: dni (Phase 3 overall)
```

**Parallel waves:**
- Wave 1: `13o` alone (critical path blocker)
- Wave 2 (after 13o): `pqt`, `hfp`, `3dv` in parallel; also start block library beads
- Wave 3 (after pqt): `8dn`; continue block library
- Wave 4 (after 8dn): `p18`; continue block library; dispatch `1pj` (pipeline templates)
- Wave 5 (after p18): `28m` (advise API wire-up); after `1pj`: `gni`, `9hr`
- Wave 6 (after 28m): `2gt` (CLI advise)

**The critical demo path is**: `13o → pqt → 8dn → p18 → 28m → 2gt`
Keep this chain moving. Block library beads fill in around it.

## Loop

Repeat until `bd list --status=open` returns only the epic `dni`:

### 1. Find ready work
```bash
bd ready
```

### 2. Check for parallelism

**Parallelism rules — read these before dispatching anything:**

- **Do NOT use `isolation: "worktree"`** for sub-agents. All agents work directly on the main working directory. Block library beads modify entirely different files with zero overlap — isolation adds branch-merging complexity with no benefit.
- **Cap concurrent agents at 4**. More than 4 simultaneous agents risks confusing yourself and makes it hard to track failures. Dispatch 4, wait for them all, then dispatch the next batch.
- **Critical path beads** (`13o`, `pqt`, `8dn`, `p18`, `28m`, `2gt`) must be dispatched **sequentially** — each waits for the previous to fully close before you dispatch the next. Do not parallelize the critical path.
- **Block library beads** are safe to run 4 at a time. They each write to a single new file in a different `blocks/` subdirectory.
- **Do not run `run_in_background: true`** for any sub-agent. You need the result before deciding next steps.

### 3. Dispatch each ready bead as a sub-agent

Use the bead's `recommended_model` from the NOTES section:
- `haiku` → model: haiku
- `sonnet` → model: sonnet
- `opus` → model: opus
- Unspecified → default to sonnet

**Sub-agent prompt template:**

```
You are implementing a single bead for Insight-Engine.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

Read CLAUDE.md before writing any code.

Context documents to load before touching specific files:
- Modifying backend/chat/context_builder.py or backend/chat/research_advisor.py
  → read .claude/context/reasoning-layer.md AND .claude/context/chat-architecture.md
- Modifying backend/chat/assistant.py or backend/chat/copilot.py
  → read .claude/context/chat-architecture.md
- Modifying backend/blocks/**/*.py or backend/blocks/base.py
  → read .claude/context/block-contracts.md
- Any block with dimensions property
  → read .claude/context/reasoning-layer.md (method classification table)
- Modifying frontend/src/components/chat-panel/** or frontend/src/stores/chat.ts
  → read .claude/context/chat-architecture.md
- Modifying backend/api/*.py or backend/schemas/*.py
  → read .claude/context/pipeline-schema.md

Agent spec relevant to this bead:
[PASTE FULL CONTENT OF THE RELEVANT AGENT .md HERE — see Agent Trigger Table in CLAUDE.md]

Bead to implement:
[PASTE FULL bd show OUTPUT HERE]

Implementation rules:
- Implement exactly what the bead describes. No more, no less.
- Follow all conventions in CLAUDE.md (uv, ruff, pytest, Pydantic v2).
- When done: run `ruff check . --fix && ruff format .` from the repo root.
- Then run ONLY the tests relevant to what you wrote — NOT the full test suite:
    Block bead → pytest tests/blocks/test_<impl>.py
    Reasoning/chat bead → pytest tests/reasoning/ tests/chat/
    API bead → pytest tests/api/
    CLI bead → pytest tests/cli/
  (If a dedicated test file doesn't exist yet, create it as part of this bead.)
- Do NOT run `uv run pytest` (full suite) — the orchestrator handles that after each wave.
- Do NOT close the bead — the orchestrator handles that.
- Return: DONE or FAILED with a one-paragraph summary of what was built
  and any non-obvious decisions made.
```

**Which agent spec to paste:**

| Bead(s) | Agent spec to include |
|---------|----------------------|
| `13o` (context_builder), `pqt/8dn/p18` (advisor stages), `28m` (advise API) | `.claude/agents/reasoning-specialist/AGENT.md` |
| `hfp` (chat assistant), `3dv` (chat copilot), LLM generation blocks (`oup`, `0f5`, `yre`, `na9`, `kxt`) | `.claude/agents/llm-integration/AGENT.md` |
| `hfp`/`3dv` frontend portions, `fgt`, `9hr` | `.claude/agents/canvas-specialist/AGENT.md` |
| `py6`, `l0g`, `ee7`, `azw`, `g6e`, `9pd`, `0i2`, `3ro`, `thf`, `laq`, `1pj` | `.claude/agents/block-developer/AGENT.md` |
| `2gt`, `gni` | No specific agent — follow CLAUDE.md conventions |

For `hfp` and `3dv` (chat panel — backend + frontend): include **both** llm-integration and canvas-specialist agent specs.

### 4. After each sub-agent returns

**If DONE:**
Close the bead: `bd close <id>`
No need to run the full test suite after every single bead — the sub-agent ran scoped tests.

**If FAILED:**
Retry once with the failure details. Two consecutive failures → stop and report to user.

### 5. After closing a full wave of beads

After each **wave** (all beads in that wave are closed), run the full test suite once:
```bash
cd backend && uv run pytest
```
If tests fail after a wave: identify which bead broke them (check git diff), re-open it (`bd update <id> --status=open`), fix with a targeted sub-agent, re-close, re-run full suite.

### 6. After closing each bead
```bash
bd ready
```
Continue the loop with newly unblocked beads.

## Bead-Specific Notes

**13o (context_builder):**
Critical path blocker. Dispatch first. The module lives at `backend/chat/context_builder.py`. No LLM calls — pure context assembly. Three functions: `build_pipeline_context(pipeline_id)`, `build_block_catalog_context(block_type_filter=None)`, `build_advisor_context(profile, candidates=None)`. Uses `engine.registry.list_blocks()` and `reasoning.workflows.get_workflow_for_block()` internally. Must not import from `research_advisor.py`.

**pqt (Advisor Stage 1 — characterize_problem):**
Replaces the placeholder in `research_advisor.py`. Uses `AsyncAnthropic`. System prompt includes dimension definitions from `reasoning/dimensions.py` and situational attribute vocabulary. Response must be parsed into `ProblemProfile` with BOTH `dimensions: Dict[str, str]` AND `situational_context: SituationalContext` as separate fields — do not merge. Validate dimension values against allowed sets from `reasoning/dimensions.py`. Model default: `claude-sonnet-4-6`, configurable.

**8dn (Advisor Stage 2 — match_candidates):**
Two-pass: (1) mechanical filter via `engine.registry.list_blocks(type="analysis")` using `ProblemProfile.dimensions` and reasoning profile's `dimension_weights`; (2) LLM contextual ranking using `ProblemProfile.situational_context`. Returns `List[MethodCandidate]` (3–6 items) with `fit_score`, `fit_reasoning`, `tradeoffs`. Uses `context_builder.build_block_catalog_context()` for the LLM pass.

**p18 (Advisor Stage 3 — recommend):**
LLM call with: candidate list, constraints, and the practitioner workflow loaded via `reasoning.workflows.get_workflow_for_block()` for the top candidate. Use `context_builder.build_advisor_context(profile, candidates)`. Returns `Recommendation` with `selected_method`, `rationale`, and `pipeline_sketch` (a rough node list with block types — NOT a full pipeline JSON, just a human-readable shape description).

**28m (Advise API wire-up):**
Updates `backend/api/advise.py` to call real `ResearchAdvisor` methods instead of returning placeholders. Add `profile` query parameter support to all three POST endpoints. Default profile loads from `reasoning_profiles/default/profile.yaml`. Verify end-to-end: `POST /api/v1/advise/characterize` with a real research question returns a populated `ProblemProfile`.

**2gt (CLI: insights advise):**
Adds `insights advise "<research question>"` to the existing Typer CLI (do NOT create a new entry point — extend the existing one). Calls `POST /api/v1/advise/characterize` then `POST /api/v1/advise/match`, prints ranked method candidates with fit reasoning. Optional `--recommend` flag runs Stage 3 and prints full recommendation with pipeline sketch.

**hfp (Chat: research assistant):**
Backend: `POST /api/v1/chat` using `context_builder.build_block_catalog_context()` + optional `build_pipeline_context()`, streams LLM response via `StreamingResponse`. Frontend: chat drawer component (slide-in panel, message history, input box, streaming text display). Keep chat state in a new `useChatStore` Zustand store — not in `pipeline.ts`. `max_tokens=4096`.

**3dv (Chat: co-pilot):**
Backend: `POST /api/v1/chat/modify` using `context_builder.build_pipeline_context(pipeline_id)`. LLM returns a `PipelineDiff` (structured add/remove/modify nodes and edges). Backend validates diff against block contracts before returning. Frontend: shows confirmation modal before applying; calls `store.applyDiff(diff)` only on user confirmation. Never auto-apply.

**fgt (Frontend: richer config panel):**
**Check before dispatching.** Run: `grep -n "enum\|select\|checkbox\|tag" frontend/src/components/config-panel/config-panel.tsx | head -20`
If enum→select, boolean→checkbox, array→tag input are already implemented, close this bead immediately without dispatching: `bd close fgt --reason="Already implemented in config-panel.tsx"`

**ee7 (segmentation_lca):**
`AnalysisBase` block. Uses `prince` library for LCA — run `uv add prince` if not present. Dimensions from method_classification_draft.md: `mixed`, `high`, `high`, `high`, `medium`, `categorical`. Must have `dimensions` property with all 6 keys validated against `reasoning/dimensions.py` allowed sets. Requires `description` and `methodological_notes` (ADR-002 enforcement).

**azw (rfm_analysis):**
`AnalysisBase` block. Transaction data input, produces customer value segments. Dimensions: `confirmatory`, `medium`, `high`, `medium`, `high`, `numeric_continuous`. Input schema: `respondent_collection` (treat each row as a transaction record with at least `recency`, `frequency`, `monetary` columns or config-specified column names).

**3ro (pdf_report):**
`ReportingBase` block. Uses `weasyprint` (NOT reportlab). Run `uv add weasyprint` if not in `pyproject.toml`. Renders markdown → PDF. Must include `output_format` in `config_schema`. Sub-agent should confirm `weasyprint` is importable before implementing.

**l0g (sample_provider_source):**
Inherits `SourceBase + IntegrationMixin`. Models Cint/Lucid API shape — uses `call_external()` from `IntegrationMixin` for all HTTP. Returns `respondent_collection`. `service_name = "Sample Provider"`, `estimated_latency = "slow"`. This is a stub — it does not need a real API key to pass tests; mock `call_external()` in tests.

**1pj (Pipeline templates):**
Creates three JSON fixture files in `backend/templates/`:
1. `concept_prescreen.json`: `csv_source → filter_transform → concept_evaluator → threshold_router → markdown_report`
2. `discussion_guide.json`: `csv_source → filter_transform → llm_generation → prompt_flex → json_sink`
3. `segmentation_report.json`: `csv_source → segmentation_kmeans → markdown_report → json_sink`
Also add `GET /api/v1/templates` endpoint that lists available templates and `POST /api/v1/pipelines` with `template_id` support. Template JSON must be valid pipeline definitions matching the schema in `backend/schemas/pipeline.py`.

**9hr (Frontend: template picker):**
Dialog that opens when user clicks "New Pipeline". Calls `GET /api/v1/templates`, displays template name, description, and a bulleted node list. On selection, calls `POST /api/v1/pipelines` with `template_id` and loads the resulting pipeline into the canvas. Depends on `1pj`.

**gni (CLI expansion):**
Extends existing Typer CLI (not a new entry point):
- `insights pipeline validate <pipeline-file>` — loads JSON, calls `POST /api/v1/pipelines/validate`
- `insights pipeline create --from-template <name>` — calls `POST /api/v1/pipelines` with `template_id`
- `insights run resume <run-id> --hitl-response <file>` — loads JSON file, calls `POST /api/v1/hitl/{run_id}/respond`
Depends on `1pj` for the `--from-template` command.

## Completion

When `bd list --status=open` returns only the epic `dni`:

```bash
cd backend && uv run pytest
ruff check backend/
git add -A
git commit -m "feat: Phase 3 complete — block library, chat panel, ResearchAdvisor LLM

- backend/chat/context_builder.py: shared LLM context assembly foundation
- ResearchAdvisor: 3-stage LLM chain (characterize/match/recommend) wired
- /api/v1/advise/* endpoints: real implementations, profile support
- insights advise CLI: demo-ready agentic reasoning entry point
- Chat panel: research assistant (streaming) + co-pilot (pipeline diff)
- Block library: 15 new blocks (sources, transforms, analysis, generation, reporting, sinks)
- PDF report builder via weasyprint
- Pipeline templates: 3 built-in fixtures + template picker UI
- CLI expansion: validate, create-from-template, resume HITL

Co-Authored-By: Claude Code (Opus) <noreply@anthropic.com>"
git push
```

Then close the epic: `bd close dni`

Report to the user: Phase 3 complete.

## Safety Rules

- Never skip `uv run pytest` before closing a bead.
- Never close a bead the sub-agent marked FAILED.
- Never dispatch `28m` (advise API wire-up) until `pqt`, `8dn`, and `p18` are all closed.
- Never dispatch `2gt` (CLI advise) until `28m` is closed.
- Never dispatch `9hr` or `gni` until `1pj` is closed.
- Check `fgt` (config panel) before dispatching — it may already be implemented.
- Never dispatch `3dv` or `hfp` until `13o` is closed.
- `weasyprint` must be added via `uv add weasyprint` before implementing `3ro` — confirm it imports without error.
- `prince` must be added via `uv add prince` before implementing `ee7`.
- Block library beads with `dimensions` property: always validate values against `reasoning/dimensions.py` allowed sets — never invent values.
- Never close the epic until all member beads are closed.
- If three consecutive sub-agents fail on the same bead, stop and report to the user.
- `reasoning_profiles/` is at the repo root, not inside `backend/` — flag if a sub-agent tries to put it elsewhere.
