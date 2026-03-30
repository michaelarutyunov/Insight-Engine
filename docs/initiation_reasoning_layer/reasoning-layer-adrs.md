# Architectural Decision Records — Reasoning Layer

These ADRs follow from the design discussion on methodology selection and agent reasoning. They extend the existing ADR series (ADR-001: Analysis block type, ADR-002: Embedded block descriptions, ADR-003: Integration mixin).

---

## ADR-004: Dimensional Method Characterization

### Status
Accepted

### Context
The block catalog provides execution contracts (inputs, outputs, config) but not the domain knowledge an LLM agent needs to select appropriate analytical methods from research questions. The methodological_notes field (ADR-002) operates at the block level ("when to use k-means vs. LCA") but does not support higher-level reasoning that connects research question types to analytical strategy families.

A decision-tree approach was considered and rejected: research methodology is too subjective and contested for prescriptive rules, and the space of contextual constraints (sample size, data characteristics, timeline, output requirements) produces combinatorial complexity that resists enumeration.

### Decision
Introduce ordinal dimensional metadata on Analysis blocks that characterizes the *nature* of each method without prescribing when to use it. Dimensions describe method character (exploratory vs. confirmatory, assumption weight, output interpretability, etc.), enabling the LLM to match problem characteristics against method characteristics.

### Dimensions (initial set, subject to validation)

| Dimension | Values | Captures |
|---|---|---|
| `exploratory_confirmatory` | `exploratory` / `mixed` / `confirmatory` | Whether the method discovers or tests structure |
| `assumption_weight` | `low` / `medium` / `high` | How many constraints the method imposes on data |
| `output_interpretability` | `low` / `medium` / `high` | Whether output is directly stakeholder-readable |
| `sample_sensitivity` | `low` / `medium` / `high` | Minimum data volume for reliable results |
| `reproducibility` | `low` / `medium` / `high` | Consistency across analysts and executions |
| `data_structure_affinity` | `unstructured_text` / `categorical` / `ordinal` / `numeric_continuous` / `mixed` | What kind of input the method operates on |

### Design Properties
- **Ordinal labels, not numeric scores** — avoids false precision and mechanistic appearance
- **Descriptive, not prescriptive** — dimensions characterize methods, not dictate usage
- **Pluralistic** — different reasoning profiles can weight dimensions differently or provide alternative scorings for the same block
- **Grounded in established methodology** — dimensions map to recognized concepts (EDA, statistical power, inter-rater reliability, parametric/non-parametric)

### Consequences
- `AnalysisBase` gains `dimensions` property returning `Dict[str, str]`
- Empty default ensures backward compatibility
- Block registry API (`GET /api/v1/blocks`) exposes dimensional metadata
- Dimension vocabulary defined in `reasoning/dimensions.py` as an enum set
- Validation: score 15-20 analysis methods and verify profiles differentiate usefully. If they don't, revise dimensions before committing

---

## ADR-005: Progressive Refinement for Method Selection

### Status
Accepted

### Context
The initial critique assumed the agent must go from research question to specific method in one reasoning step. This mirrors a decision-tree model and fails because: (a) the final method choice is legitimately subjective, and (b) a single-step approach either requires exhaustive rules or gives the LLM too large an unconstrained space.

Researchers actually narrow progressively: question type → approach family → specific method. The last step is where professional judgment, training, and preference legitimately enter.

### Decision
Method selection proceeds as a multi-stage prompt chain, not a single LLM call. Each stage uses different knowledge artifacts and has different subjectivity characteristics.

Stage 1 produces two kinds of output: dimensional coordinates (analytical character of the problem) and situational context (practical circumstances). Dimensions enable mechanical filtering in Stage 2. Situational context guides the LLM's contextual reasoning about which filtered candidates actually fit the circumstances.

| Stage | Input | Output | Knowledge Used | Subjectivity |
|---|---|---|---|---|
| 1. Characterize | Research question + data context + brief | `ProblemProfile` (dimensions + situational context) | Dimension definitions, situational attribute vocabulary | Low |
| 2. Match | `ProblemProfile` + block registry | `List[MethodCandidate]` (3-6 methods) | Block dimensional metadata (mechanical filter) + situational context (LLM reasoning) | Medium |
| 3. Select | Candidates + constraints | Selected method + rationale | Practitioner workflows, reasoning profile preferences | High |
| 4. Build | Selected method + source schema | Pipeline definition | Block contracts, input/output schemas | Low |

### Architectural Implementation
- Stages 1-3 are the `ResearchAdvisor` module (`chat/research_advisor.py`)
- Stage 4 is the existing `copilot.py`, receiving advisor output as input context
- The boundary: advisor produces method selection + data requirements + pipeline sketch; copilot does mechanical wiring and validation

### Consequences
- New module `chat/research_advisor.py` with three async methods
- New package `reasoning/` with dimensions, profiles, and workflow loading
- Advisor output is a structured object consumed by copilot, not free text
- API endpoint `/api/v1/advise` exposes stages 1-2 for CLI and agent consumption
- HITL checkpoint available after stage 2 (present candidates to human) or after stage 3 (present recommendation for approval)

---

## ADR-006: Reasoning Profiles as Swappable Configuration

### Status
Accepted

### Context
Research methodology is not monolithic. Different agencies, academic traditions, and individual researchers have legitimate differences in how they approach method selection. The dimensional characterization (ADR-004) provides a shared coordinate system, but the *weights* and *preferences* applied during matching are inherently opinionated.

### Decision
Introduce reasoning profiles as a first-class configurable artifact. A reasoning profile bundles dimension weights, methodological preferences, and pointers to practitioner workflow documents. Profiles are swappable at the project or pipeline level.

### Profile Schema
```yaml
name: string                    # Human-readable name
version: string                 # Semver
description: string             # What perspective this profile represents

dimension_weights:              # Relative importance during matching
  exploratory_confirmatory: float
  assumption_weight: float
  output_interpretability: float
  sample_sensitivity: float
  reproducibility: float
  data_structure_affinity: float

preferences:
  default_stance: string        # "exploratory" | "confirmatory" | "balanced"
  transparency_threshold: string # Minimum inferential transparency
  prefer_established: bool      # Favor well-established methods

practitioner_workflows_dir: string  # Relative path to workflow documents
```

### Storage and Sharing
- Profiles stored as YAML files in `reasoning_profiles/` directory
- Same versioning infrastructure as pipeline templates
- Marketplace-ready: agencies can publish profiles as methodology packages
- A project or pipeline can reference a specific profile; default profile used when none specified

### Consequences
- New directory `reasoning_profiles/` with at least one `default/` profile
- `ResearchAdvisor` accepts profile at initialization
- Project-level setting for active reasoning profile
- Profile loading and validation in `reasoning/profiles.py`
- API support for listing and selecting profiles

---

## ADR-007: Practitioner Workflows as Agent Guides

### Status
Accepted

### Context
External validation (diff-diff library, Baker et al. 2025 framework): embedding practitioner reasoning workflows in AI-facing documentation improved agent performance by 85% on a causal inference task. The improvement came from encoding the analyst's reasoning sequence (check assumptions, test sensitivity, compare approaches, report robustly), not just the tool's mechanics.

The block catalog tells the agent how to run an analysis block. Practitioner workflows tell the agent how to *think about* running it — the disciplinary judgment that wraps around the mechanics.

### Decision
Practitioner workflows are structured markdown documents associated with Analysis blocks (or analysis families). They encode a step-by-step reasoning sequence for executing a particular analysis type competently. The agent loads the relevant workflow as context during pipeline construction and execution.

### Workflow Format
```markdown
# {Analysis Family} — Practitioner Workflow

## Pre-analysis checks
{numbered steps for validating data suitability}

## Method selection guidance
{decision factors within this analysis family}

## Execution steps
{numbered steps for running the analysis properly}

## Reporting requirements
{what must be included in output for methodological rigor}
```

### Attachment Model
- Workflows can attach at the family level (segmentation) or implementation level (k-means specifically)
- Implementation-level workflows override or extend family-level workflows
- Different reasoning profiles can point to different workflow documents for the same analysis
- Workflows are loaded by `reasoning/workflows.py` and injected into LLM context by `context_builder.py`

### Consequences
- New directory structure: `reasoning_profiles/{profile}/practitioner_workflows/`
- `AnalysisBase` gains optional `practitioner_workflow` property (path reference)
- `context_builder.py` updated to load and inject workflows when advisor or copilot is constructing analysis pipelines
- Workflows are human-readable markdown — reviewable, versioned, shareable
- Initial set: write workflows for proof-of-concept analysis blocks before testing agent pipeline composition
