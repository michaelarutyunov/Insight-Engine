# Implementation Spec: Reasoning Layer Foundations

**Purpose:** Lay architectural foundations for the reasoning layer. No LLM logic yet — schema definitions, base classes, directory structure, and one proof-of-concept practitioner workflow.

**Reference documents:** Read `reasoning-layer-design.md` and `reasoning-layer-adrs.md` for design context. Read existing `block-catalog.md` and `insights-ide-technical-blueprint.md` for current architecture.

---

## Task 1: Create reasoning package

Create `backend/reasoning/` package with three modules.

### Files to create

**`backend/reasoning/__init__.py`**
- Empty init

**`backend/reasoning/dimensions.py`**
- Define `MethodDimension` enum with values: `EXPLORATORY_CONFIRMATORY`, `ASSUMPTION_WEIGHT`, `OUTPUT_INTERPRETABILITY`, `SAMPLE_SENSITIVITY`, `REPRODUCIBILITY`, `DATA_STRUCTURE_AFFINITY`
- Define allowed values for each dimension as a dict:
  - `EXPLORATORY_CONFIRMATORY`: `["exploratory", "mixed", "confirmatory"]`
  - `ASSUMPTION_WEIGHT`: `["low", "medium", "high"]`
  - `OUTPUT_INTERPRETABILITY`: `["low", "medium", "high"]`
  - `SAMPLE_SENSITIVITY`: `["low", "medium", "high"]`
  - `REPRODUCIBILITY`: `["low", "medium", "high"]`
  - `DATA_STRUCTURE_AFFINITY`: `["unstructured_text", "categorical", "ordinal", "numeric_continuous", "mixed"]`
- Define `DimensionalProfile` as a Pydantic model with optional fields for each dimension (all `Optional[str]`, validated against allowed values)
- Define `validate_dimensions(dimensions: dict) -> bool` function that checks all keys are valid dimensions and all values are in allowed sets

**`backend/reasoning/profiles.py`**
- Define `ReasoningProfile` Pydantic model:
  - `name: str`
  - `version: str`
  - `description: str`
  - `dimension_weights: Dict[str, float]` — keys are dimension names, values are 0.0-1.0
  - `preferences: ProfilePreferences` (nested model with `default_stance: str`, `transparency_threshold: str`, `prefer_established: bool`)
  - `practitioner_workflows_dir: str`
- Define `load_profile(profile_path: Path) -> ReasoningProfile` — loads from YAML file
- Define `list_profiles(profiles_dir: Path) -> List[str]` — returns available profile names

**`backend/reasoning/workflows.py`**
- Define `load_workflow(workflow_path: Path) -> str` — reads markdown file, returns content as string
- Define `get_workflow_for_block(block_implementation: str, profile: ReasoningProfile) -> Optional[str]` — looks up workflow file in profile's workflow directory, returns content or None
- Workflow file naming convention: `{analysis_family}.md` (e.g., `segmentation.md`, `driver_analysis.md`)

### Dependencies
- `pyyaml` for profile loading
- Pydantic v2 for models (already in project)

---

## Task 2: Extend AnalysisBase with dimensional metadata

Modify `backend/blocks/base.py`.

### Changes to BlockBase
Add three properties with empty defaults (backward compatible):

```python
@property
def dimensions(self) -> Dict[str, str]:
    """Dimensional characterization for reasoning layer. Override in Analysis blocks."""
    return {}

@property
def practitioner_workflow(self) -> Optional[str]:
    """Path to practitioner workflow document, if any."""
    return None
```

### Create AnalysisBase
If `AnalysisBase` does not exist yet, create it inheriting from `BlockBase`:

```python
class AnalysisBase(BlockBase):
    """Base for question-driven analytical blocks that produce new output types."""

    @property
    def block_type(self) -> str:
        return "analysis"

    @property
    @abstractmethod
    def dimensions(self) -> Dict[str, str]:
        """Required for Analysis blocks. Return dimensional profile.
        Keys must be valid MethodDimension names.
        Values must be in the allowed set for that dimension.
        """
        ...
```

### Validation
Import `validate_dimensions` from `reasoning.dimensions` and call it in `AnalysisBase.__init_subclass__` or as a test fixture to ensure all Analysis block implementations declare valid dimensions.

---

## Task 3: Reclassify segmentation_kmeans as Analysis

Move `backend/blocks/transforms/segmentation_kmeans.py` to `backend/blocks/analysis/segmentation_kmeans.py`.

### Create directory
- `backend/blocks/analysis/__init__.py`

### Update the block class
- Change parent class from `TransformBase` (or `BlockBase`) to `AnalysisBase`
- Add `dimensions` property:

```python
@property
def dimensions(self) -> Dict[str, str]:
    return {
        "exploratory_confirmatory": "exploratory",
        "assumption_weight": "medium",
        "output_interpretability": "medium",
        "sample_sensitivity": "high",
        "reproducibility": "high",
        "data_structure_affinity": "numeric_continuous",
    }
```

- Add `description` and `methodological_notes` properties (from ADR-002):
  - description: "Clusters respondents into segments using K-Means algorithm. Use when you need a simple, interpretable segmentation of respondents based on numeric behavioral or attitudinal features."
  - methodological_notes: "Assumes spherical clusters of roughly equal size. Sensitive to outliers — consider outlier removal or robust scaling in upstream Transform blocks. Requires all features to be numeric; categorical features must be encoded upstream. Feature scaling (standard or minmax) strongly recommended. Cluster count must be specified; does not perform automatic selection. Consider running multiple times with different k values and using a Comparator block to evaluate solutions. Alternatives: LCA for categorical/mixed features or probabilistic membership. RFM for transaction-based customer value segmentation."

- Add `tags` property: `["clustering", "segmentation", "unsupervised", "numeric-features", "requires-scaling"]`

- Set `practitioner_workflow` to `"segmentation.md"`

### Update registry
If `backend/engine/registry.py` uses directory-based discovery, ensure it scans `blocks/analysis/`.

### Update block_type enum
In `backend/schemas/block_types.py`, add `"analysis"` to the block type enum.

---

## Task 4: Create default reasoning profile

### Create directory structure
```
backend/reasoning_profiles/
├── default/
│   ├── profile.yaml
│   └── practitioner_workflows/
│       └── segmentation.md
```

### Write profile.yaml
```yaml
name: "Default Research Methodology"
version: "1.0"
description: "Balanced methodological stance for general insights work"

dimension_weights:
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

### Write segmentation.md practitioner workflow
```markdown
# Segmentation — Practitioner Workflow

## Pre-analysis checks
1. Verify feature variance — drop near-constant columns before clustering
2. Assess multicollinearity among clustering features — consider PCA or feature selection if VIF > 5 for multiple pairs
3. Check for outliers — flag observations beyond 3 SD on key features and decide handling (remove, cap, or note) before clustering
4. Verify sample size adequacy — minimum approximately 50 observations per expected cluster for stable solutions
5. Confirm all features are on comparable scales — if not, ensure a scaling transform is upstream

## Method selection guidance within segmentation family
- All numeric features, no strong priors about segment structure → k-means
- Categorical or mixed features → Latent Class Analysis (LCA)
- Transaction data with known value dimensions → RFM analysis
- Need probabilistic segment membership → LCA or Gaussian Mixture Model
- Very high dimensionality (50+ features) → consider dimensionality reduction before clustering

## Execution steps
6. Run with multiple cluster counts (e.g., k = 3 through k = 8 for k-means)
7. Evaluate each solution on both statistical criteria (silhouette score, within-cluster sum of squares) and business interpretability
8. Profile the selected solution on variables NOT used in clustering — segment validity depends on discrimination on external variables
9. Name segments using dominant profile characteristics, not cluster numbers

## Reporting requirements
10. Report solution diagnostics (fit metrics, stability) alongside segment descriptions
11. Include segment sizes as both counts and percentages
12. Present segment profiles as comparative tables or visualizations, not isolated descriptions
13. Note any segments with very small sizes (< 5% of sample) — these may not be actionable
14. Document the feature set, scaling method, and number of solutions evaluated
```

---

## Task 5: Create ResearchAdvisor skeleton

Create `backend/chat/research_advisor.py` with the interface but no LLM logic. Methods return placeholder outputs.

```python
"""Research advisor module — question-to-method reasoning.

Progressive refinement: characterize problem → match candidates → recommend.
LLM logic to be implemented in Phase 3. Current implementation returns
structured placeholders to validate the interface.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class SituationalContext(BaseModel):
    """Practical circumstances of the research problem.

    Unlike method dimensions (formalized, scored on blocks), these are
    inferred by the LLM from the research brief and stored as structured
    natural language. The LLM reasons over them contextually rather than
    matching them mechanically.
    """
    available_data: Optional[str] = None         # e.g. "NPS survey with verbatims, no operational data"
    hypothesis_state: Optional[str] = None       # "no prior hypothesis" | "suspected cause" | "known event, unknown mechanism"
    time_constraint: Optional[str] = None        # "days" | "weeks" | "months"
    epistemic_stance: Optional[str] = None       # "trust existing frameworks" | "suspect unknown unknowns" | "question measurement validity"
    deliverable_expectation: Optional[str] = None # "board-ready quantified answer" | "exploratory landscape" | "actionable intervention"


class ProblemProfile(BaseModel):
    """Characterization of a research inquiry.

    Two sections serve different purposes:
    - dimensions: feed Stage 2 mechanical filtering against block metadata
    - situational_context: guide LLM contextual reasoning in Stages 2-3
    """
    research_question: str
    dimensions: Dict[str, str]                    # dimension_name → value (for mechanical matching)
    situational_context: SituationalContext        # practical circumstances (for LLM reasoning)
    reasoning: str                                 # explanation of characterization


class MethodCandidate(BaseModel):
    """A candidate analytical method with fit reasoning."""
    block_implementation: str
    block_type: str
    fit_score: str              # "strong" | "moderate" | "weak"
    fit_reasoning: str
    tradeoffs: str
    dimensions: Dict[str, str]


class Recommendation(BaseModel):
    """Final method recommendation with rationale."""
    selected_method: str
    rationale: str
    pipeline_sketch: Optional[Dict[str, Any]] = None  # broad pipeline shape
    practitioner_workflow: Optional[str] = None


class ResearchAdvisor:
    """Guides method selection from research questions.

    Accepts a block registry and reasoning profile. Implements
    three-stage progressive refinement.

    Phase 3 implementation: each stage becomes an LLM prompt chain.
    Current implementation: returns structured placeholders.
    """

    def __init__(self, block_registry, reasoning_profile):
        self.registry = block_registry
        self.profile = reasoning_profile

    async def characterize_problem(
        self, research_question: str, data_context: Optional[dict] = None
    ) -> ProblemProfile:
        """Stage 1: Interpret research question as dimensional profile + situational context."""
        # Phase 3: LLM call with dimension definitions + situational attribute vocabulary as context
        return ProblemProfile(
            research_question=research_question,
            dimensions={},
            situational_context=SituationalContext(),
            reasoning="Not yet implemented — Phase 3"
        )

    async def match_candidates(
        self, profile: ProblemProfile
    ) -> List[MethodCandidate]:
        """Stage 2: Filter by dimensions, then reason over situational context."""
        # Phase 3: dimensional matching (mechanical) + LLM reasoning (contextual)
        return []

    async def recommend(
        self, candidates: List[MethodCandidate],
        constraints: Optional[dict] = None
    ) -> Recommendation:
        """Stage 3: Select from candidates given constraints."""
        # Phase 3: LLM reasoning with practitioner workflow context
        return Recommendation(
            selected_method="",
            rationale="Not yet implemented — Phase 3"
        )
```

---

## Task 6: Add advise endpoint to API

Create or update `backend/api/advise.py`.

### Endpoints

**`POST /api/v1/advise/characterize`**
- Body: `{"research_question": str, "data_context": dict?}`
- Returns: `ProblemProfile` (includes both `dimensions` and `situational_context`)

**`POST /api/v1/advise/match`**
- Body: `ProblemProfile` (dimensions used for mechanical filtering, situational_context used for LLM reasoning)
- Returns: `List[MethodCandidate]`

**`POST /api/v1/advise/recommend`**
- Body: `{"candidates": List[MethodCandidate], "constraints": dict?}`
- Returns: `Recommendation`

**`GET /api/v1/reasoning-profiles`**
- Returns: list of available reasoning profile names and descriptions

**`GET /api/v1/reasoning-profiles/{name}`**
- Returns: full reasoning profile details

### Register routes in `backend/main.py`.

---

## Task 7: Update block catalog API

Update `backend/api/blocks.py` to include new fields in the block catalog response.

### Extended block catalog entry
The `GET /api/v1/blocks` response for each block should now include:
- `description` (from ADR-002)
- `methodological_notes` (from ADR-002)
- `tags` (from ADR-002)
- `dimensions` (from ADR-004) — only present for Analysis blocks
- `practitioner_workflow` (from ADR-007) — path reference, only present if set

These fields come from the block's class properties. The registry reads them and includes them in the catalog response.

---

## Task 8: Tests

### Unit tests for reasoning package

**`tests/test_dimensions.py`**
- `test_valid_dimensions_pass` — valid dimension dict passes validation
- `test_invalid_dimension_key_fails` — unknown dimension name rejected
- `test_invalid_dimension_value_fails` — value outside allowed set rejected
- `test_empty_dimensions_pass` — empty dict is valid (backward compat)

**`tests/test_profiles.py`**
- `test_load_default_profile` — default profile loads from YAML without error
- `test_profile_schema_validation` — invalid profile YAML raises validation error
- `test_list_profiles` — lists available profiles in directory

**`tests/test_workflows.py`**
- `test_load_workflow` — segmentation.md loads as string
- `test_missing_workflow_returns_none` — nonexistent workflow returns None

**`tests/test_research_advisor.py`**
- `test_advisor_instantiation` — creates with registry and profile
- `test_characterize_returns_problem_profile` — placeholder returns valid structure with both dimensions and situational_context
- `test_problem_profile_has_situational_context` — SituationalContext fields are present and default to None
- `test_situational_context_accepts_values` — SituationalContext can be populated with string values
- `test_match_returns_candidate_list` — placeholder returns empty list
- `test_recommend_returns_recommendation` — placeholder returns valid structure

### Contract tests for Analysis blocks

**`tests/test_blocks/test_analysis_contract.py`**
- For each registered Analysis block:
  - `dimensions` property returns dict
  - All dimension keys are valid `MethodDimension` names
  - All dimension values are in allowed sets
  - `description` is non-empty string
  - `methodological_notes` is non-empty string
  - `tags` is non-empty list of strings

---

## Task 9: Update project documentation

### Update `block-catalog.md`
- Add Analysis section (between Transforms and Generation)
- Move `segmentation_kmeans` from Transforms to Analysis
- Add dimensional metadata to its catalog entry
- Add note about practitioner workflow availability

### Update backend directory structure in `insights-ide-technical-blueprint.md`
Add to the directory tree:
```
├── reasoning/
│   ├── dimensions.py
│   ├── profiles.py
│   └── workflows.py
├── reasoning_profiles/
│   └── default/
│       ├── profile.yaml
│       └── practitioner_workflows/
│           └── segmentation.md
```

Add to chat/ directory:
```
├── chat/
│   ├── ...
│   ├── research_advisor.py    # Research question → method recommendation
```

### Update CLAUDE.md constitution (if it exists)
- Add `analysis` to block type table (11th type)
- Add `reasoning/` to key files section
- Add trigger rule: "when modifying reasoning/*.py or reasoning_profiles/ → consult reasoning-layer-design.md"

---

## Verification checklist

After implementation, verify:
- [ ] `backend/reasoning/` package imports without error
- [ ] `DimensionalProfile` validates valid dimensions, rejects invalid
- [ ] `SituationalContext` accepts optional string fields, defaults to None
- [ ] `ProblemProfile` includes both `dimensions` and `situational_context`
- [ ] Default reasoning profile loads from YAML
- [ ] Segmentation practitioner workflow loads as string
- [ ] `segmentation_kmeans` is now an Analysis block with valid dimensions
- [ ] Block registry includes `analysis` type and exposes dimensional metadata
- [ ] `ResearchAdvisor` instantiates and returns placeholder outputs with situational context
- [ ] `/api/v1/advise/characterize` returns 200 with valid ProblemProfile including situational_context
- [ ] `/api/v1/blocks` response includes dimensions for Analysis blocks
- [ ] All tests pass
- [ ] Block catalog doc reflects Analysis section and dimensional metadata
