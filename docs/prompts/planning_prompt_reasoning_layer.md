You are a senior software architect planning the Reasoning Layer foundations for the Insight-Engine project.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

## Your task

Read the following, in order:
1. `CLAUDE.md` — project constitution, conventions, Agent Trigger Table, and Key File Map
2. `docs/initiation_reasoning_layer/reasoning-layer-design.md` — full design rationale, dimensional model, progressive refinement architecture, practitioner workflows, software architecture
3. `docs/initiation_reasoning_layer/reasoning-layer-adrs.md` — ADR-004 (dimensional characterization), ADR-005 (progressive refinement), ADR-006 (reasoning profiles), ADR-007 (practitioner workflows)
4. `docs/initiation_reasoning_layer/reasoning-layer-implementation-spec.md` — 9-task implementation spec with exact code, file paths, and test requirements
5. `docs/initiation_reasoning_layer/method_classification_draft.md` — 32 methods pre-scored on all 6 dimensions (authoritative reference for dimension values)
6. `.claude/context/reasoning-layer.md` — context doc encoding the domain knowledge agents will need
7. `.claude/agents/reasoning-specialist/AGENT.md` — the specialist agent for this module
8. `backend/blocks/base.py` — current BlockBase and all base classes (AnalysisBase may already exist from the taxonomy refactor)
9. `backend/engine/registry.py` — block discovery and info serialization
10. `backend/schemas/blocks.py` — BlockInfoResponse schema (may already include description/methodological_notes/tags from taxonomy refactor)
11. `backend/chat/` directory — existing chat modules (assistant.py, copilot.py, context_builder.py, config_helper.py if present)
12. Run `bd list --status=open` and `bd list --status=closed` to understand current project state and what the taxonomy refactor already delivered

**Important:** The taxonomy refactor (ADR-001/002/003) may be partially or fully complete. Check what already exists before creating beads for things already done:
- Does `AnalysisBase` exist in `blocks/base.py`? (Step 5 of taxonomy refactor)
- Does `backend/blocks/analysis/` exist? (Step 5)
- Does `segmentation_kmeans` live in `blocks/analysis/`? (Step 6)
- Do `description`, `methodological_notes`, `tags` exist on BlockBase? (Steps 1–2)
- Does `backend/schemas/block_types.py` exist? (Step 5)

Only create beads for work that is genuinely outstanding.

Then create a complete set of beads for the reasoning layer foundations using `bd create`.

## Requirements for the bead set

- One epic bead for the reasoning layer foundations overall
- Individual task beads for each deliverable, granular enough for a single sub-agent to implement in one session
- Wire up all dependencies with `bd dep add`
- Every bead must have:
  - Clear, bounded description (one deliverable, one concern)
  - Explicit acceptance criteria (`--acceptance`)
  - Complexity and recommended_model metadata (`--notes`)
  - No deferred decisions — all architectural choices are made in the ADRs and implementation spec

## Deliverables to cover (from the implementation spec, Tasks 1–9)

**Task 1 — Create reasoning package**
New package `backend/reasoning/` with three modules:
- `dimensions.py`: `MethodDimension` enum (6 values), allowed values dict per dimension, `DimensionalProfile` Pydantic model (6 optional fields, validated against allowed sets), `validate_dimensions(dict) -> bool`
- `profiles.py`: `ProfilePreferences` and `ReasoningProfile` Pydantic models, `load_profile(Path) -> ReasoningProfile` (YAML), `list_profiles(Path) -> List[str]`
- `workflows.py`: `load_workflow(Path) -> str`, `get_workflow_for_block(block_implementation, profile) -> Optional[str]`
Dependency: `pyyaml` (add via `uv add pyyaml` if not present)

**Task 2 — Extend AnalysisBase with dimensional metadata**
If AnalysisBase does not yet have `dimensions` and `practitioner_workflow` properties, add them:
- `dimensions` property with `return {}` default on BlockBase (concrete, non-breaking)
- `dimensions` as `@abstractmethod` on AnalysisBase (required for all Analysis blocks)
- `practitioner_workflow` property with `return None` default on BlockBase (concrete, optional)
No-op if taxonomy refactor already added AnalysisBase with these.

**Task 3 — Score segmentation_kmeans dimensions**
Add `dimensions` property to KMeansAnalysis (wherever it lives after taxonomy refactor):
```python
{
    "exploratory_confirmatory": "exploratory",
    "assumption_weight": "medium",
    "output_interpretability": "medium",
    "sample_sensitivity": "high",
    "reproducibility": "high",
    "data_structure_affinity": "numeric_continuous",
}
```
Add `practitioner_workflow = "segmentation.md"`. Verify all existing block tests still pass.

**Task 4 — Create default reasoning profile**
Create `reasoning_profiles/default/profile.yaml` and `reasoning_profiles/default/practitioner_workflows/segmentation.md`.
Profile YAML must use float values for `dimension_weights` (not ints — YAML parses `1` as int, causing Pydantic validation failure). Workflow document must cover all four sections: pre-analysis checks, method selection guidance within segmentation family, execution steps, reporting requirements. The segmentation workflow in the implementation spec is the quality benchmark.

**Task 5 — ResearchAdvisor skeleton**
Create `backend/chat/research_advisor.py` with all Pydantic models and the `ResearchAdvisor` class:
- Models: `SituationalContext`, `ProblemProfile`, `MethodCandidate`, `Recommendation`
- `ProblemProfile` contains both `dimensions: Dict[str, str]` and `situational_context: SituationalContext` — do not merge these
- All three advisor methods return structured placeholders (no LLM logic yet)
- Class docstring must clearly mark Phase 3 as the milestone for LLM implementation
The exact interface is specified in the implementation spec — follow it precisely.

**Task 6 — Advise API endpoints**
Create `backend/api/advise.py` with all five endpoints:
- `POST /api/v1/advise/characterize` → `ProblemProfile`
- `POST /api/v1/advise/match` → `List[MethodCandidate]`
- `POST /api/v1/advise/recommend` → `Recommendation`
- `GET /api/v1/reasoning-profiles` → list of names and descriptions
- `GET /api/v1/reasoning-profiles/{name}` → full `ReasoningProfile`
Create request/response schemas in `backend/schemas/advise.py`. Register router in `backend/main.py`.

**Task 7 — Extended block catalog API**
Update `backend/engine/registry.py` to include `dimensions` and `practitioner_workflow` in the `_INFO` dict (alongside existing `description`, `methodological_notes`, `tags` from taxonomy refactor). Update `backend/schemas/blocks.py` `BlockInfoResponse` to include these fields as optional (blocks that are not Analysis blocks will not have them). Only expose `dimensions` and `practitioner_workflow` if non-empty/non-None.

**Task 8 — Tests**
Write tests covering all four new modules:
- `tests/reasoning/test_dimensions.py` — valid/invalid dimension keys and values, empty dict passes
- `tests/reasoning/test_profiles.py` — default profile loads, invalid YAML fails, list_profiles works
- `tests/reasoning/test_workflows.py` — segmentation workflow loads, missing workflow returns None
- `tests/reasoning/test_research_advisor.py` — instantiation, all three methods return correct typed outputs, `ProblemProfile` has both `dimensions` and `situational_context`
- `tests/blocks/test_analysis_contract.py` — for every registered Analysis block: dimensions returns valid dict, all keys valid, all values in allowed sets, description non-empty, methodological_notes non-empty, tags non-empty list

**Task 9 — Documentation updates**
Update:
- `docs/initiation/insights-ide-technical-blueprint.md` — add `reasoning/`, `reasoning_profiles/`, and `chat/research_advisor.py` to the directory tree section
- Any block-catalog document — add Analysis section (if not already present from taxonomy refactor), add dimensional metadata to segmentation_kmeans entry

## Dependency ordering and parallelism

```
Task 1 (reasoning package)
 ├── Task 2 (AnalysisBase extensions) — depends on Task 1 for validate_dimensions
 │    └── Task 3 (score kmeans dimensions) — depends on Task 2
 │         └── Task 4 (default profile + segmentation workflow) — no code dep, but needs Task 3 for test coherence
 │              └── Task 8 (tests) — depends on Tasks 1–5 all present
 ├── Task 5 (ResearchAdvisor skeleton) — depends on Task 1 for ReasoningProfile import
 │    └── Task 6 (advise API) — depends on Task 5
 └── Task 7 (extended block catalog) — depends on Task 1 for dimension field types; depends on Task 2 for AnalysisBase.dimensions

Task 9 (docs) — depends on all other tasks; no code dependency, can go last
```

Tasks 3, 4, 5, 7 can run in parallel once Tasks 1 and 2 are done.

## Constraints
- Backend: Python 3.11+, FastAPI, Pydantic v2, uv
- YAML loading: `pyyaml` (not `ruamel.yaml`)
- No LLM calls in this phase — all advisor methods return structured placeholders
- `SituationalContext` fields are `Optional[str]` — do not validate values against a fixed enum
- `dimension_weights` in profile YAML must be floats (`1.0` not `1`) — note this explicitly in every relevant bead
- `reasoning_profiles/` lives at the repo root (`/home/mikhailarutyunov/projects/Insight-Engine/reasoning_profiles/`), not inside `backend/`

## After creating all beads

1. Run `bd dep add` to wire the dependency chain as specified above
2. Run `/check_bd` to review beads for ambiguity and missing acceptance criteria
3. Present a dependency graph summary showing the critical path and which tasks can be parallelized
