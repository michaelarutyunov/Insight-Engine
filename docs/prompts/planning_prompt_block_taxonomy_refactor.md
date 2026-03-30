You are a senior software architect planning the Block Taxonomy Refactor for the Insight-Engine project.
Working directory: /home/mikhailarutyunov/projects/Insight-Engine

## Your task

Read the following, in order:
1. `CLAUDE.md` — project constitution and conventions
2. `docs/updates/block-taxonomy-refactor.md` — the three ADRs driving this refactor (ADR-001, ADR-002, ADR-003) and the 10-step migration plan
3. `backend/blocks/base.py` — current BlockBase and all base classes
4. `backend/engine/registry.py` — block discovery and info serialization
5. `backend/schemas/blocks.py` — BlockInfoResponse and BlockListResponse
6. `backend/api/blocks.py` — catalog endpoints
7. All 14 block implementations (scan for what exists):
   - `backend/blocks/transforms/` — filter_transform.py, segmentation_kmeans.py
   - `backend/blocks/sources/` — csv_loader.py, csv_source.py
   - `backend/blocks/generation/` — llm_generation.py
   - `backend/blocks/evaluation/` — concept_evaluator.py, rubric_evaluation.py
   - `backend/blocks/comparison/` — side_by_side_comparator.py
   - `backend/blocks/hitl/` — approval_gate.py
   - `backend/blocks/llm_flex/` — prompt_flex.py
   - `backend/blocks/reporting/` — markdown_report.py
   - `backend/blocks/routing/` — conditional_router.py, threshold_router.py
   - `backend/blocks/sinks/` — json_sink.py
8. Run `bd list --status=open` and `bd list --status=closed` to understand current project state

Then create a complete set of beads for this refactor using `bd create`.

## Requirements for the bead set

- One epic bead for the refactor overall
- Individual task beads for each deliverable, granular enough for a single sub-agent to implement in one session
- Wire up all dependencies with `bd dep add` — the migration sequence in the ADR is the canonical ordering
- Every bead must have:
  - Clear, bounded description (one deliverable, one concern)
  - Explicit acceptance criteria (`--acceptance`)
  - Complexity and recommended_model metadata (`--notes`)
  - No deferred decisions — all architectural choices are already made in the ADRs; beads only need to capture what to implement and how to verify it

## Deliverables to cover (following the ADR migration sequence)

**Step 1 — BlockBase properties (non-breaking baseline)**
Add `methodological_notes` (str, concrete default) and `tags` (List[str], concrete default `[]`) to `BlockBase` in `backend/blocks/base.py`. `description` already exists with a default — verify it's there and consistent with ADR-002. All existing tests must continue to pass.

**Step 2 — Add descriptions to all 14 existing blocks**
For each of the 14 block implementations, add meaningful `description`, `methodological_notes`, and `tags` properties. Each `methodological_notes` must cover: assumptions, data requirements, known limitations, and alternatives. The k-means example in ADR-002 is the quality benchmark. This is one bead per block (14 beads), each independently implementable.

**Step 3 — Expose new fields in registry and catalog API**
Update `engine/registry.py` to include `methodological_notes` and `tags` in the `_INFO` dict. Update `schemas/blocks.py` (`BlockInfoResponse`) to include these fields. Update `api/blocks.py` to support `?tags=<tag>` query parameter filtering. The existing `?type=` filter must continue to work.

**Step 4 — IntegrationMixin**
Create `backend/blocks/integration.py` containing `IntegrationMixin`, `IntegrationError`, `IntegrationTimeoutError`, `IntegrationRateLimitError`. Implement `get_credentials()`, `call_external()` (httpx, exponential backoff, retries), and `poll_for_result()` as specified in ADR-003. `is_external_service`, `service_name`, `estimated_latency`, `cost_per_call` properties included. No existing blocks use it yet — purely additive.

**Step 5 — AnalysisBase and analysis block type**
Add `"analysis"` to the block type enum (wherever it lives — check `backend/schemas/` for a `block_types.py` or equivalent; if none exists, create `backend/schemas/block_types.py` with a `BlockType` string enum). Create `AnalysisBase(BlockBase)` in `backend/blocks/base.py` with `block_type = "analysis"` and `preserves_input_type = False`. Create `backend/blocks/analysis/__init__.py`.

**Step 6 — Reclassify segmentation_kmeans**
Move `backend/blocks/transforms/segmentation_kmeans.py` → `backend/blocks/analysis/segmentation_kmeans.py`. Rename class `KMeansTransform` → `KMeansAnalysis`. Change base class to `AnalysisBase`. Verify `input_schemas = ["respondent_collection"]` and `output_schemas = ["segment_profile_set"]` are still correct. Registry must discover the block at its new location and register it as `block_type: "analysis"`.

**Step 7 — Migrate existing pipeline fixtures/test pipelines**
Audit all test fixtures and saved pipeline JSON files for references to `segmentation_kmeans` with `block_type: "transform"`. Update them to `block_type: "analysis"`. If a migration script is warranted, write it (see ADR migration plan Step 7 for the script template).

**Step 8 — Frontend block palette: Analysis category**
Add "Analysis" as a new category in the frontend block palette. Give it distinct visual styling. Reclassified blocks appear under Analysis, not Transform. Category order: Source → Transform → Analysis → Generation → Evaluation → Comparator → LLM Flex → Router → HITL → Reporting → Sink (11 categories).

**Step 9 — Documentation and agent context updates**
Update the following files to reflect 11 block types, AnalysisBase, IntegrationMixin, and the new description/methodological_notes contract:
- `CLAUDE.md` (constitution) — block type table: 10 → 11, add Analysis row
- `.claude/context/block-contracts.md` — new base classes, properties
- `.claude/agents/block-developer/AGENT.md` — if it exists

**Step 10 — Make description and methodological_notes abstract (final enforcement)**
Once all 14 blocks have real implementations (Step 2 complete): remove the temporary concrete defaults from `BlockBase`, mark `description` and `methodological_notes` as `@abstractmethod`. Any block missing these will fail at import time. All tests must pass.

## Constraints
- Backend: Python 3.11+, FastAPI, Pydantic v2, uv
- HTTP client for IntegrationMixin: httpx (async)
- No breaking changes to existing API contract until Step 3 is ready
- Steps 1 and 4 are purely additive — zero risk of breaking existing tests
- Steps 2 (block descriptions) are independent of each other — safe to parallelize across sub-agents
- Step 6 (reclassify kmeans) depends on Step 5 (AnalysisBase must exist first)
- Step 10 (make abstract) depends on Step 2 (all blocks must have real descriptions)

## After creating all beads

1. Run `bd dep add` to wire the dependency chain matching the ADR migration sequence
2. Run `/check_bd` to review beads for ambiguity and missing acceptance criteria
3. Present a dependency graph summary showing the critical path and which steps can be parallelized
