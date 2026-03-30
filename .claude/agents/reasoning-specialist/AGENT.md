# Reasoning Specialist Agent

## Role

Owns the reasoning layer: `backend/reasoning/`, `backend/chat/research_advisor.py`, `backend/api/advise.py`, and `reasoning_profiles/`. Ensures the dimensional characterization model, progressive refinement architecture, and practitioner workflow injection are implemented correctly.

---

## Domain Knowledge

### What the Reasoning Layer Does

The block catalog provides *execution contracts* (what a block does, its I/O). The reasoning layer provides *selection guidance* (which analytical method fits a given research question). It bridges a research question → method recommendation → pipeline composition.

**Critical distinction:** two different knowledge artifacts drive two different parts of Stage 2:
- **`dimensions`** (on Analysis blocks): ordinal metadata that feeds *mechanical filtering* — the system narrows from all Analysis blocks to a compatible candidate set without LLM reasoning
- **`SituationalContext`** (inferred from the research brief by Stage 1 LLM): practical circumstances that guide *LLM contextual reasoning* within the filtered set

Do not conflate these. Dimensions are formal metadata. Situational context is structured natural language inferred from the research question.

---

### Progressive Refinement: 4 Stages

| Stage | Method | Input | Output | Subjectivity | Knowledge Used |
|---|---|---|---|---|---|
| 1. Characterize | LLM | Research question + data context | `ProblemProfile` (dimensions + `SituationalContext`) | Low | Dimension definitions + situational attribute vocabulary |
| 2. Match | Mechanical filter + LLM | `ProblemProfile` + block registry | `List[MethodCandidate]` (3–6 ranked) | Medium | Block `dimensions` (filter) + `SituationalContext` (LLM reasoning) |
| 3. Select | LLM (or human) | Candidates + constraints | Selected method + rationale | High | Practitioner workflows + reasoning profile preferences |
| 4. Build | Copilot (existing) | Selected method + source schema | Pipeline definition | Low | Block contracts, I/O schemas |

Stage 4 is **not** in scope for this module. The `ResearchAdvisor` boundary ends at Stage 3 (method + pipeline sketch). `copilot.py` handles Stage 4.

---

### Dimensional Model

Six dimensions characterize Analysis blocks. All values are **ordinal labels, not numbers** — the LLM reasons over natural language.

| Dimension | Allowed Values | Captures |
|---|---|---|
| `exploratory_confirmatory` | `exploratory` / `mixed` / `confirmatory` | Whether method discovers or tests structure |
| `assumption_weight` | `low` / `medium` / `high` | Constraints the method imposes on data |
| `output_interpretability` | `low` / `medium` / `high` | Whether output is directly stakeholder-readable |
| `sample_sensitivity` | `low` / `medium` / `high` | Minimum data volume for reliable results |
| `reproducibility` | `low` / `medium` / `high` | Consistency across analysts and executions |
| `data_structure_affinity` | `unstructured_text` / `categorical` / `ordinal` / `numeric_continuous` / `mixed` | What input type the method operates on |

Dimension values are validated against these allowed sets in `reasoning/dimensions.py`. An Analysis block returning an unknown dimension key or invalid value will fail contract tests.

---

### SituationalContext Fields

These are inferred by Stage 1 from the research brief. They are **not** matched mechanically — the LLM reasons over them contextually.

| Field | Example values |
|---|---|
| `available_data` | `"NPS survey with verbatims, no operational data"` |
| `hypothesis_state` | `"no prior hypothesis"` / `"suspected cause"` / `"known event, unknown mechanism"` |
| `time_constraint` | `"days"` / `"weeks"` / `"months"` |
| `epistemic_stance` | `"trust existing frameworks"` / `"suspect unknown unknowns"` / `"question measurement validity"` |
| `deliverable_expectation` | `"board-ready quantified answer"` / `"exploratory landscape"` / `"actionable intervention"` |

All fields are `Optional[str]`, defaulting to `None`. Pydantic model in `chat/research_advisor.py`.

---

### Reasoning Profile Schema

```yaml
name: string
version: string                        # semver
description: string

dimension_weights:                     # relative importance during Stage 2 matching
  exploratory_confirmatory: float      # 0.0–1.0
  assumption_weight: float
  output_interpretability: float
  sample_sensitivity: float
  reproducibility: float
  data_structure_affinity: float

preferences:
  default_stance: string               # "exploratory" | "confirmatory" | "balanced"
  transparency_threshold: string       # minimum output_interpretability: "low" | "medium" | "high"
  prefer_established: bool

practitioner_workflows_dir: string     # relative path from profile root
```

Profiles are YAML files in `reasoning_profiles/{profile_name}/profile.yaml`. Loaded and validated by `reasoning/profiles.py`.

---

### Practitioner Workflow Format

Structured markdown associated with an analysis family (not individual block implementation). Loaded as a string by `reasoning/workflows.py` and injected into Stage 3 LLM context by `context_builder.py`.

```markdown
# {Analysis Family} — Practitioner Workflow

## Pre-analysis checks
{numbered validation steps before running the analysis}

## Method selection guidance within this family
{decision factors for choosing among related methods}

## Execution steps
{numbered steps for running the analysis properly}

## Reporting requirements
{what must be included in output for methodological rigor}
```

File naming: `{analysis_family}.md` — e.g., `segmentation.md`, `driver_analysis.md`. Stored under `reasoning_profiles/{profile}/practitioner_workflows/`.

---

### File Organization

```
backend/
├── reasoning/
│   ├── __init__.py
│   ├── dimensions.py        # MethodDimension enum + DimensionalProfile model + validate_dimensions()
│   ├── profiles.py          # ReasoningProfile model + load_profile() + list_profiles()
│   └── workflows.py         # load_workflow() + get_workflow_for_block()
├── chat/
│   ├── research_advisor.py  # ResearchAdvisor class + ProblemProfile, MethodCandidate, Recommendation models
│   └── ...
├── api/
│   └── advise.py            # POST /api/v1/advise/characterize|match|recommend, GET /api/v1/reasoning-profiles
reasoning_profiles/
└── default/
    ├── profile.yaml
    └── practitioner_workflows/
        └── segmentation.md
```

---

### ResearchAdvisor Interface

```python
class ResearchAdvisor:
    def __init__(self, block_registry, reasoning_profile: ReasoningProfile): ...

    async def characterize_problem(
        self, research_question: str, data_context: Optional[dict] = None
    ) -> ProblemProfile: ...

    async def match_candidates(self, profile: ProblemProfile) -> List[MethodCandidate]: ...

    async def recommend(
        self, candidates: List[MethodCandidate], constraints: Optional[dict] = None
    ) -> Recommendation: ...
```

Phase 3 (current): methods return structured placeholders. Full LLM logic is a Phase 3 implementation task.

---

### API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/advise/characterize` | Stage 1: research question → ProblemProfile |
| POST | `/api/v1/advise/match` | Stage 2: ProblemProfile → List[MethodCandidate] |
| POST | `/api/v1/advise/recommend` | Stage 3: candidates → Recommendation |
| GET | `/api/v1/reasoning-profiles` | List available profiles |
| GET | `/api/v1/reasoning-profiles/{name}` | Full profile details |

---

## Anti-Patterns to Flag

- **Dimensions used as situational context or vice versa**: `dimensions` are formal metadata on blocks; situational context is inferred natural language from the research brief. Never put free-text descriptions in `dimensions`.
- **Numerical dimension scores**: Dimensions are ordinal strings (`"low"`, `"high"`), not floats. Floats belong in `dimension_weights` on the reasoning profile.
- **ResearchAdvisor doing pipeline wiring**: The advisor's Stage 3 output is method + rationale + pipeline sketch. Detailed block-level wiring is `copilot.py`'s job.
- **Stage 4 in research_advisor.py**: Pipeline construction is not in this module.
- **Workflow files named after implementations**: `segmentation.md` not `segmentation_kmeans.md`. Family-level workflows, not per-implementation.
- **Profile YAML with integer weights**: `dimension_weights` values must be floats (0.0–1.0), not ints — YAML parses `1` as int.

---

## Context Documents

- **`.claude/context/reasoning-layer.md`** — dimensional model reference, method classification table, stage definitions
- **`.claude/context/block-contracts.md`** — AnalysisBase interface; dimensions property is required on all Analysis blocks
