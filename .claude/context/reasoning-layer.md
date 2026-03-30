# Reasoning Layer — Context Reference

## Purpose

The reasoning layer bridges a research question → method recommendation → pipeline composition. It does not execute pipelines — that is the execution engine. It does not modify pipelines — that is the copilot. It characterizes research problems and recommends analytical methods.

Load this document when modifying `backend/reasoning/`, `backend/chat/research_advisor.py`, `backend/api/advise.py`, `reasoning_profiles/`, or any `AnalysisBase.dimensions` implementation.

---

## Core Concepts

### Two Complementary Knowledge Artifacts

Stage 2 of the method selection pipeline uses two different things for two different purposes:

| Artifact | Where it lives | How used | Subjectivity |
|---|---|---|---|
| `dimensions` | On each Analysis block (class property) | **Mechanical filtering** — narrows all Analysis blocks to compatible candidates | Low — objectively characterizes method |
| `SituationalContext` | Inferred by Stage 1 LLM from research brief | **LLM contextual reasoning** — navigates within filtered candidates | Low-Medium — describes circumstances, not judgment |

**Do not conflate these.** Dimensions are formal structured metadata on blocks. Situational context is structured natural language inferred from the research question. Both feed Stage 2, but differently.

---

## Dimensional Model

### Six Dimensions

| Dimension | Allowed Values | Captures |
|---|---|---|
| `exploratory_confirmatory` | `exploratory` / `mixed` / `confirmatory` | Whether the method discovers unknown structure or tests hypothesized structure |
| `assumption_weight` | `low` / `medium` / `high` | How many distributional or structural constraints the method imposes on data |
| `output_interpretability` | `low` / `medium` / `high` | Whether output is directly stakeholder-readable without expert translation |
| `sample_sensitivity` | `low` / `medium` / `high` | Minimum data volume for reliable results (low = works at N < 20; high = needs N > 300) |
| `reproducibility` | `low` / `medium` / `high` | Consistency of output across analysts and executions |
| `data_structure_affinity` | `unstructured_text` / `categorical` / `ordinal` / `numeric_continuous` / `mixed` | What type of input the method operates on |

### Design Properties
- **Ordinal labels only** — not numeric scores; avoids false precision
- **Descriptive, not prescriptive** — dimensions characterize methods, not dictate when to use them
- **Pluralistic** — different reasoning profiles can weight dimensions differently; same method can be scored differently by different methodological schools
- **Grounded**: `exploratory_confirmatory` ← Tukey EDA; `sample_sensitivity` ← statistical power + qualitative saturation; `reproducibility` ← inter-rater reliability + replicability

---

## Method Classification Reference

Validated across 32 analytical methods. Use these scores when implementing `dimensions` on Analysis blocks or writing tests.

| Method | exploratory_confirmatory | assumption_weight | output_interpretability | sample_sensitivity | reproducibility | data_structure_affinity |
|---|---|---|---|---|---|---|
| K-means clustering | exploratory | medium | medium | medium | high | numeric_continuous |
| Hierarchical clustering (Ward) | exploratory | medium | medium | low | high | numeric_continuous |
| Gaussian Mixture Models (GMM) | exploratory | high | medium | medium | medium | numeric_continuous |
| Latent Class Analysis (LCA) | mixed | high | high | high | medium | categorical |
| DBSCAN | exploratory | medium | medium | low | medium | numeric_continuous |
| PCA | exploratory | medium | medium | medium | high | numeric_continuous |
| Exploratory Factor Analysis (EFA) | exploratory | high | medium | high | medium | numeric_continuous |
| Confirmatory Factor Analysis (CFA) | confirmatory | high | medium | high | medium | numeric_continuous |
| MDS | exploratory | medium | medium | medium | medium | mixed |
| MCA | exploratory | medium | medium | medium | high | categorical |
| OLS regression (driver analysis) | confirmatory | high | high | medium | high | numeric_continuous |
| Logistic regression | confirmatory | high | medium | medium | high | mixed |
| Relative weights / Shapley drivers | mixed | medium | high | medium | medium | mixed |
| PLS regression (drivers) | mixed | medium | medium | medium | medium | numeric_continuous |
| SEM | confirmatory | high | medium | high | medium | mixed |
| A/B testing | confirmatory | medium | high | medium | high | mixed |
| Conjoint (CBC) | confirmatory | high | medium | high | high | mixed |
| MaxDiff | mixed | medium | high | medium | high | ordinal |
| Discrete Choice Experiment (DCE) | confirmatory | high | medium | high | medium | mixed |
| Marketing Mix Modelling (MMM) | confirmatory | high | medium | high | medium | numeric_continuous |
| Interrupted Time Series | confirmatory | high | medium | high | medium | numeric_continuous |
| Thematic analysis | exploratory | low | high | low | low | unstructured_text |
| Framework analysis | mixed | medium | high | low | medium | unstructured_text |
| Grounded theory coding | exploratory | low | medium | low | low | unstructured_text |
| Ethnography / contextual inquiry | exploratory | low | high | low | low | mixed |
| Diary study | exploratory | low | high | low | low | mixed |
| Manual content analysis | mixed | medium | high | low | medium | unstructured_text |
| Topic modelling (LDA) | exploratory | high | low | medium | high | unstructured_text |
| Topic modelling (BERTopic / embeddings) | exploratory | medium | medium | low | medium | unstructured_text |
| Sentiment analysis (lexicon-based) | mixed | medium | medium | low | high | unstructured_text |
| LLM-assisted coding (HITL) | mixed | medium | high | low | medium | unstructured_text |
| Synthetic respondents (persona simulation) | exploratory | high | medium | low | low | mixed |

---

## Progressive Refinement Stages

### Stage 1: Problem Characterization
- **Input:** Research question + data context + research brief (optional)
- **Output:** `ProblemProfile` — contains both `dimensions: Dict[str, str]` (analytical character) and `situational_context: SituationalContext` (practical circumstances)
- **Knowledge used:** Dimension definitions (from this doc) + situational attribute vocabulary
- **Subjectivity:** Low

### Stage 2: Neighborhood Matching
- **Input:** `ProblemProfile` + block registry (with dimensional metadata)
- **Output:** `List[MethodCandidate]` — 3–6 ranked candidates with fit reasoning
- **Process:** Dimensions filter mechanically first; `SituationalContext` guides LLM reasoning over filtered set
- **Subjectivity:** Medium

### Stage 3: Method Selection
- **Input:** Candidates + constraints (timeline, budget, team)
- **Output:** Selected method + rationale + pipeline sketch
- **Knowledge used:** Practitioner workflows + reasoning profile preferences
- **Subjectivity:** High

### Stage 4: Pipeline Construction
- **Handled by:** `copilot.py` — not `ResearchAdvisor`
- **Input:** Stage 3 output (method + sketch)
- **Output:** Full pipeline definition

---

## SituationalContext Structure

```python
class SituationalContext(BaseModel):
    available_data: Optional[str] = None
    # e.g. "NPS survey with verbatims, no operational data"

    hypothesis_state: Optional[str] = None
    # "no prior hypothesis" | "suspected cause" | "known event, unknown mechanism"

    time_constraint: Optional[str] = None
    # "days" | "weeks" | "months"

    epistemic_stance: Optional[str] = None
    # "trust existing frameworks" | "suspect unknown unknowns" | "question measurement validity"

    deliverable_expectation: Optional[str] = None
    # "board-ready quantified answer" | "exploratory landscape" | "actionable intervention"
```

All fields optional. These are natural language descriptions, not enums — the LLM reasons over them. Do not validate their values against a fixed allowed set.

---

## Reasoning Profile Schema

```yaml
name: "Default Research Methodology"
version: "1.0"
description: "Balanced methodological stance for general insights work"

dimension_weights:            # float values 0.0–1.0 (NOT ints — YAML parses 1 as int)
  exploratory_confirmatory: 1.0
  assumption_weight: 0.8
  output_interpretability: 1.0
  sample_sensitivity: 0.9
  reproducibility: 0.7
  data_structure_affinity: 1.0

preferences:
  default_stance: "exploratory"
  transparency_threshold: "medium"
  prefer_established: true

practitioner_workflows_dir: "./practitioner_workflows/"
```

Stored as `reasoning_profiles/{name}/profile.yaml`. Validated by `reasoning/profiles.py`.

---

## Practitioner Workflow Format

```markdown
# {Analysis Family} — Practitioner Workflow

## Pre-analysis checks
{numbered steps for validating data suitability before running}

## Method selection guidance within this family
{factors for choosing between related methods, e.g. k-means vs LCA}

## Execution steps
{numbered steps for running the analysis correctly}

## Reporting requirements
{what must appear in output for methodological rigor}
```

**File naming:** `{analysis_family}.md` — family-level, not per implementation. `segmentation.md` covers k-means, LCA, and RFM. Do not create `segmentation_kmeans.md`.

**Loading:** `reasoning/workflows.py` → `get_workflow_for_block(block_implementation, profile)` looks up the family from the block's `practitioner_workflow` property (set on `AnalysisBase` subclasses).

---

## AnalysisBase Extensions (from ADR-004)

Analysis blocks declare dimensions alongside existing ADR-002 properties:

```python
class AnalysisBase(BlockBase):
    @property
    def block_type(self) -> str:
        return "analysis"

    @property
    def preserves_input_type(self) -> bool:
        return False

    @property
    @abstractmethod
    def dimensions(self) -> Dict[str, str]:
        """Required. Keys from MethodDimension enum; values from allowed sets."""
        ...

    @property
    def practitioner_workflow(self) -> Optional[str]:
        """Override to return workflow filename, e.g. 'segmentation.md'."""
        return None
```

---

## Integration Points

| Component | How it uses the reasoning layer |
|---|---|
| `context_builder.py` | Loads practitioner workflow (via `workflows.py`) and injects into LLM context during Stage 3 |
| `copilot.py` | Receives Stage 3 output (method + pipeline sketch) as input context for pipeline construction |
| `engine/registry.py` | Exposes `dimensions` and `practitioner_workflow` in block catalog metadata |
| `api/advise.py` | Exposes all three advisor stages as REST endpoints |
| Canvas / CLI / Chat | Advisor stages surface in all three interaction modes |
