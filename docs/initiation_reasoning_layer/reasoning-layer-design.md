# Reasoning Layer Design — From Block Catalog to Research Advisor

## Problem Statement

The block catalog provides a supply-side vocabulary: "here's what we can build." An LLM composing a pipeline from a research question needs demand-side reasoning: "here's what should happen given this question." The catalog tells the agent that k-means exists and takes numeric features. It does not tell the agent whether k-means is the right approach for a given research question. That domain knowledge — connecting research questions to analytical strategies — lives nowhere in the current system.

### The Rules vs. Reasoning Question

An initial framing proposed encoding cross-block methodological knowledge as decision rules (e.g., "customer needs question → qualitative exploration → thematic analysis"). This raised a valid concern: if the knowledge can be formalized as a decision tree, why is agentic reasoning necessary?

**Resolution:** Formalized knowledge and LLM reasoning solve different parts of the problem. Structured scaffolding narrows the search space from all possible methods to a small neighborhood of 3-6 candidates. The LLM reasons within that narrowed space, weighing contextual constraints (sample size, data characteristics, timeline, output format, team capabilities) that interact in ways too numerous to enumerate as rules. The test: if you find yourself writing more than ~100 rules and they still don't cover edge cases, you've hit the boundary where formalization stops working and reasoning takes over.

### Why Not Qual/Quant?

The traditional qualitative/quantitative dichotomy is too coarse for method selection. Methods grouped under "qual" differ significantly from each other on dimensions that matter for selection — IDIs and ethnography are both "qual" but have different collection adaptability, analytical depth, and inferential transparency profiles. The same is true within "quant." A more useful characterization maps methods against continuous dimensions that describe their character.

---

## Core Design: Dimensional Method Characterization

Instead of encoding "for problem X use method Y" (opinionated, fragile), each analytical method is characterized along ordinal dimensions that describe what kind of thing it does. The LLM matches problem characteristics to method characteristics rather than following a lookup table.

### Candidate Dimensions for Analysis Blocks

| Dimension | Low end | High end | What it captures |
|---|---|---|---|
| Exploratory ↔ Confirmatory | Discovering unknown structure | Testing hypothesized structure | Whether the researcher has priors |
| Assumption weight | Minimal constraints on data | Strong distributional/structural assumptions | How much the method imposes on the data |
| Output interpretability | Requires expert translation | Directly stakeholder-readable | Who can act on the results |
| Sample sensitivity | Works with small N (5-20) | Requires large N (500+) | Data volume requirements |
| Reproducibility | Analyst-dependent variation | Same input → same output | Consistency across executions |
| Data structure affinity | Unstructured text / rich media | Structured numeric / categorical | What kind of input it operates on |

### Key Properties of This Approach

**Descriptive, not prescriptive.** Saying "this inquiry is highly exploratory" is a description, not a judgment. Saying "k-means assumes known cluster count and continuous features" is a fact about the method. The matching is where the LLM adds contextual value.

**Grounded in established methodology.** The dimensions map to recognized concepts: exploratory vs. confirmatory (Tukey 1977, EDA), sample sensitivity (statistical power, qualitative saturation), reproducibility (inter-rater reliability, replicability), assumption weight (parametric vs. non-parametric).

**Not numerical scoring.** Dimensions use ordinal labels (low/medium/high or qualitative descriptors), not precise numbers. The LLM reasons better over natural language descriptions than numerical coordinates.

**Pluralistic, not dogmatic.** Different researchers or agencies can weight dimensions differently or even score methods differently. One agency's view of LLM-powered coding reproducibility may differ from another's. Both are legitimate. The dimensions are the shared language; the scores are the dialect.

---

## Situational Context: What the Dimensions Don't Capture

Validation against 26 pipelines across three research question types (NPS diagnosis, unmet needs discovery, brand repositioning) confirmed that the dimensions successfully differentiate analytical methods. However, the same validation revealed that **pipeline selection depends on situational attributes of the problem, not just the dimensional character of the methods.**

For example, "Why did NPS drop?" can lead to fundamentally different pipelines depending on:
- Whether you have survey data, verbatims, operational data, or all three
- Whether you trust existing measurement instruments
- Whether there is a suspected causal event
- Whether you need an answer in days or weeks
- Whether leadership expects a quantified board-ready answer or an exploratory landscape

These are not method characteristics — they are problem context. The method dimensions filter from 32 methods to ~12 candidates. The situational context is what distinguishes between fundamentally different analytical strategies within that filtered set.

### Situational Attributes

Unlike method dimensions (which are formalized and scored on blocks), situational attributes are **inferred by the LLM from the research brief** and stored as structured natural language. They don't need the same level of formalization because the LLM reasons over them contextually rather than matching them mechanically.

| Attribute | Example values | What it captures |
|---|---|---|
| `available_data` | "NPS survey with verbatims, no operational data" | What the researcher can work with |
| `hypothesis_state` | "no prior hypothesis" / "suspected cause" / "known event, unknown mechanism" | How much is already known |
| `time_constraint` | "days" / "weeks" / "months" | Practical urgency |
| `epistemic_stance` | "trust existing frameworks" / "suspect unknown unknowns" / "question measurement validity" | Whether existing instruments and categories are trusted |
| `deliverable_expectation` | "board-ready quantified answer" / "exploratory landscape" / "actionable intervention" | What the output needs to look like |

### How Dimensions and Situational Context Work Together

Dimensions do the mechanical filtering (Stage 2, first pass): "given this problem's analytical character, which methods are structurally compatible?" Situational context guides the LLM's contextual reasoning (Stage 2, second pass): "of these compatible methods, which ones make sense given you have verbatim data but no operational metrics and need results in a week?"

The dimensions narrow the space. The situational context navigates within it.

---

## Architecture: Progressive Refinement (Not Single-Pass Selection)

Method selection is not a single reasoning step. It proceeds in stages, with different knowledge artifacts and different degrees of subjectivity at each stage.

### Stage 1: Problem Characterization
The LLM interprets the research question and produces two outputs: a dimensional profile of the inquiry (what kind of analytical character does this problem have?) and a situational context (what practical circumstances constrain the approach?). No method has been selected — just the shape of the problem and the conditions under which it must be solved.

- **Input:** Research question + available data context + research brief (if available)
- **Knowledge used:** Dimension definitions (stable, not opinionated); situational attribute vocabulary
- **Output:** `ProblemProfile` — dimensional coordinates + situational context
- **Subjectivity:** Low — "this is exploratory" and "we have survey data with verbatims" are mostly factual

### Stage 2: Neighborhood Matching
The dimensional profile filters the Analysis block catalog to a broad candidate set. The situational context then guides the LLM in reasoning about which candidates make sense given the practical circumstances — available data, hypothesis state, time constraints, deliverable expectations. The combined output is a ranked shortlist of 3-6 methods.

- **Input:** `ProblemProfile` (dimensions + situational context) + block registry with dimensional metadata
- **Knowledge used:** Block dimensional scores (may vary by reasoning profile); situational context for contextual reasoning
- **Output:** `List[MethodCandidate]` — ranked candidates with tradeoff reasoning
- **Subjectivity:** Medium — which methods "fit" depends on dimensional weights and situational judgment

### Stage 3: Method Selection
The platform presents candidates with tradeoff reasoning. Selection is made by the human researcher (canvas/CLI) or by the LLM with reasoning (agent-as-composer mode).

- **Input:** Candidate set + constraints (timeline, budget, team skills)
- **Knowledge used:** Practitioner workflows, reasoning profile preferences
- **Output:** Selected method + rationale
- **Subjectivity:** High — this is where professional judgment legitimately enters

### Stage 4: Pipeline Construction
The copilot takes the selected method and builds the pipeline — inferring transforms from analysis block requirements, wiring blocks, validating connections.

- **Input:** Selected analysis method + source data schema
- **Knowledge used:** Block contracts, input/output schemas, practitioner workflows
- **Output:** Complete pipeline definition
- **Subjectivity:** Low — mostly mechanical given method selection

---

## Practitioner Workflows: Encoding Disciplinary Judgment

Validated by external example: the `diff-diff` library's documentation-driven guardrails improved AI agent performance by 85% on Difference-in-Differences analysis by encoding an 8-step practitioner framework (Baker, Callaway, Cunningham, Goodman-Bacon & Sant'Anna 2025) into the library's AI-facing documentation.

**Implication for Insights IDE:** The difference between "agent has block catalog" and "agent has block catalog + practitioner workflows" is not incremental. Practitioner workflows encode the reasoning steps a competent analyst follows when executing a particular analysis type — check assumptions, run diagnostics, validate sensitivity, report robustly.

### Practitioner Workflow as an Artifact

Each Analysis block can have one or more associated practitioner workflows. A workflow is a structured sequence of reasoning steps the agent should follow when using that block. Different workflows for the same block can represent different methodological schools.

```
reasoning_profiles/
├── default/
│   ├── profile.yaml
│   └── practitioner_workflows/
│       ├── segmentation.md
│       ├── driver_analysis.md
│       └── thematic_coding.md
├── agency_x/
│   ├── profile.yaml
│   └── practitioner_workflows/
│       ├── segmentation.md       # their version
│       └── ...
```

### Practitioner Workflow Format (Example: Segmentation)

```markdown
# Segmentation — Practitioner Workflow

## Pre-analysis checks
1. Verify feature variance — drop near-constant columns
2. Assess multicollinearity — consider dimensionality reduction if VIF > 5
3. Check for outliers — flag and decide handling before clustering
4. Verify sample size adequacy — minimum ~50 observations per expected cluster

## Method selection guidance
- All numeric features, no strong priors → k-means
- Mixed or categorical features → LCA
- Transaction data with known value framework → RFM
- Need probabilistic membership → LCA or Gaussian mixture

## Execution steps
5. Run with multiple k values (or equivalent parameter range)
6. Evaluate solutions: silhouette score + business interpretability
7. Profile segments on variables NOT used in clustering
8. Name segments using profile characteristics

## Reporting requirements
9. Report solution diagnostics alongside segment descriptions
10. Include segment sizes and stability indicators
11. Present with and without outlier-sensitive observations
```

---

## Software Architecture

### New Module: ResearchAdvisor

Sits alongside existing chat modules as a peer to copilot and assistant.

```
backend/
├── chat/
│   ├── assistant.py           # Domain Q&A (existing)
│   ├── copilot.py             # Pipeline modification (existing)
│   ├── research_advisor.py    # NEW: question → method neighborhood
│   ├── config_helper.py       # Block configuration (existing)
│   └── context_builder.py     # Assembles LLM context (existing)
├── reasoning/                 # NEW: reasoning layer components
│   ├── dimensions.py          # Dimension definitions and matching logic
│   ├── profiles.py            # Reasoning profile loading and management
│   └── workflows.py           # Practitioner workflow loading and injection
```

### ResearchAdvisor Interface

```python
class ResearchAdvisor:
    def __init__(self, block_registry, reasoning_profile):
        self.registry = block_registry
        self.profile = reasoning_profile  # swappable

    async def characterize_problem(
        self, research_question: str, data_context: dict
    ) -> ProblemProfile:
        """Stage 1: research question → dimensional profile + situational context"""
        ...

    async def match_candidates(
        self, profile: ProblemProfile
    ) -> List[MethodCandidate]:
        """Stage 2: dimensions filter mechanically, situational context guides LLM reasoning"""
        ...

    async def recommend(
        self, candidates: List[MethodCandidate], constraints: dict
    ) -> Recommendation:
        """Stage 3 (optional): narrowed recommendation with reasoning"""
        ...
```

### Reasoning Profile Schema

```yaml
# reasoning_profiles/default/profile.yaml
name: "Default Research Methodology"
version: "1.0"
description: "Balanced methodological stance for general insights work"

dimension_weights:
  exploratory_confirmatory: 1.0    # equal weight
  assumption_weight: 0.8
  output_interpretability: 1.0
  sample_sensitivity: 0.9
  reproducibility: 0.7
  data_structure_affinity: 1.0

preferences:
  default_stance: "exploratory"    # when question is ambiguous
  transparency_threshold: "medium" # minimum inferential transparency
  prefer_established: true         # favor well-established over novel methods

practitioner_workflows_dir: "./practitioner_workflows/"
```

### Block Metadata Extensions

Analysis blocks gain structured dimensional metadata alongside existing fields:

```python
class AnalysisBase(BlockBase):

    @property
    @abstractmethod
    def description(self) -> str: ...          # ADR-002

    @property
    @abstractmethod
    def methodological_notes(self) -> str: ... # ADR-002

    @property
    @abstractmethod
    def tags(self) -> List[str]: ...           # ADR-002

    @property
    @abstractmethod
    def dimensions(self) -> dict:
        """Dimensional characterization for reasoning layer matching.

        Returns dict with ordinal values: 'low', 'medium', 'high'
        or descriptive strings for non-ordinal dimensions.
        """
        # Example:
        # {
        #     "exploratory_confirmatory": "exploratory",
        #     "assumption_weight": "medium",
        #     "output_interpretability": "medium",
        #     "sample_sensitivity": "high",     # needs large N
        #     "reproducibility": "high",         # deterministic
        #     "data_structure_affinity": "numeric_continuous"
        # }
        ...

    @property
    def practitioner_workflow(self) -> Optional[str]:
        """Path to practitioner workflow document, if any."""
        return None
```

### Integration with Interaction Modes

| Mode | How the advisor surfaces |
|---|---|
| Canvas | Guided flow when starting new pipeline: "Describe your research question" → presents method candidates → user selects → copilot builds pipeline |
| CLI | `insights advise "why did NPS drop in the midwest"` → returns method recommendations with reasoning |
| Chat panel | Natural conversation: user describes goal, advisor characterizes and recommends, copilot builds on selection |
| Agent-as-composer | Advisor is first stage of autonomous pipeline composition; HITL checkpoint after method selection before pipeline construction |

### Interaction with Existing Architecture

- **Block registry** gains dimensional metadata fields — backward compatible, empty defaults
- **Context builder** (`context_builder.py`) assembles advisor context from block registry + reasoning profile + practitioner workflows
- **Copilot** receives advisor output as input context when building pipelines
- **API** gains `/api/v1/advise` endpoint for programmatic access (CLI and agent consumption)
- **Reasoning profiles** stored alongside pipeline templates — same versioning and sharing infrastructure

---

## Phasing

### Phase 1-2 (Current): Lay foundations
- Add `dimensions` property to `AnalysisBase` with empty default
- Define dimension vocabulary in `reasoning/dimensions.py`
- Define reasoning profile YAML schema in `reasoning/profiles.py`
- Write 1-2 practitioner workflows for proof-of-concept analysis blocks

### Phase 3: Implement advisor
- Build `ResearchAdvisor` with 3-stage prompt chain
- Wire into chat panel and CLI
- Write practitioner workflows for all Analysis blocks
- Score all Analysis blocks on dimensions
- Create default reasoning profile
- Add `/api/v1/advise` endpoint

### Phase 4-5: Marketplace and customization
- Reasoning profiles as shareable/sellable artifacts
- Agency-specific practitioner workflows
- Fine-tuned model variants as premium reasoning profiles
- Community-contributed dimension scorings

---

## Open Questions

1. **Dimension count:** 5-8 is the hypothesis. Needs validation by scoring 15-20 analysis methods and checking whether profiles differentiate usefully.
2. **Advisor-copilot boundary:** Does the advisor output just a method selection, or also a broad pipeline shape? The latter is probably better (advisor produces method + data requirements + pipeline sketch; copilot does mechanical wiring).
3. **Practitioner workflow granularity:** One workflow per analysis family (segmentation) or per implementation (k-means, LCA, RFM separately)? Probably both — family-level workflow with implementation-specific appendices.
4. **Dimension scoring authority:** Who scores new blocks on dimensions? Block developer? Platform review? Community consensus? Needs governance model for marketplace.
