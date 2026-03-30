# Codified Context Updates — Reasoning Layer

Addendum to the existing codified context guide. These updates integrate the reasoning layer into the three-tier knowledge infrastructure.

---

## Constitution Updates (CLAUDE.md)

Add to the block type table:

```markdown
| Analysis    | data   | new type | Question-driven, produces new output type |
```

Add to the agent trigger table:

```markdown
| Files Being Modified                     | Invoke Agent            |
|------------------------------------------|-------------------------|
| reasoning/*.py, reasoning_profiles/**    | reasoning-specialist    |
| chat/research_advisor.py                 | reasoning-specialist    |
```

Add to key files:

```markdown
- backend/reasoning/dimensions.py     → Dimension definitions and validation
- backend/reasoning/profiles.py       → Reasoning profile schema and loading
- backend/reasoning/workflows.py      → Practitioner workflow loading
- backend/chat/research_advisor.py    → Question → method recommendation
- backend/reasoning_profiles/default/ → Default reasoning profile + workflows
```

---

## New Specialist Agent: reasoning-specialist

Create `.claude/agents/reasoning-specialist/AGENT.md`:

```markdown
# Reasoning Specialist Agent

## Role
Maintains the reasoning layer — dimensions, profiles, practitioner workflows,
and the ResearchAdvisor module. Ensures dimensional metadata on Analysis blocks
is valid and consistent. Reviews practitioner workflows for methodological accuracy.

## Domain Knowledge
The reasoning layer implements progressive refinement for method selection:
1. Characterize problem → dimensional profile (low subjectivity)
2. Match candidates → 3-6 analysis methods (medium subjectivity)
3. Recommend → selected method with rationale (high subjectivity)

Key design principles:
- Dimensions are DESCRIPTIVE, not prescriptive
- Ordinal labels (low/medium/high), never numeric scores
- Reasoning profiles are SWAPPABLE — different agencies can have different profiles
- Practitioner workflows encode REASONING SEQUENCE, not just tool mechanics
- The advisor NARROWS the space; it does not make the final call in default mode

## Validation Responsibilities
- Every Analysis block must declare valid dimensions
- All dimension keys must be in the MethodDimension enum
- All dimension values must be in the allowed set for that dimension
- Practitioner workflows must follow the standard format:
  Pre-analysis checks → Method selection guidance → Execution steps → Reporting requirements
- Reasoning profiles must pass ReasoningProfile schema validation

## Anti-patterns to flag
- Numeric scores on dimensions (must be ordinal labels)
- Prescriptive rules ("always use X when Y") in practitioner workflows
- Dimension values that conflate two different concepts
- Practitioner workflows that describe mechanics without reasoning
- Missing dimensions on Analysis blocks
- Advisor logic that bypasses the progressive stages

## Context Documents
- Refer to: reasoning-layer-design.md for full architecture
- Refer to: reasoning-layer-adrs.md for decision rationale (ADR-004 through ADR-007)
```

---

## New Context Documents (Tier 3)

Create when agents make mistakes on these topics:

| When this goes wrong... | Create this context doc |
|---|---|
| Agent assigns wrong dimension values to a block | `.claude/context/dimension-vocabulary.md` |
| Agent writes prescriptive practitioner workflow | `.claude/context/practitioner-workflow-guide.md` |
| Agent breaks the progressive refinement stages | `.claude/context/advisor-stages.md` |
| Agent confuses reasoning profiles with pipeline templates | `.claude/context/reasoning-profiles.md` |

---

## Integration with Beads

New epics and tasks for the reasoning layer:

### Epic: Reasoning Layer Foundations (Phase 1-2)
- Task: Create `reasoning/` package (dimensions, profiles, workflows modules)
- Task: Extend `AnalysisBase` with dimensional metadata
- Task: Reclassify `segmentation_kmeans` as Analysis block with dimensions
- Task: Create default reasoning profile with segmentation practitioner workflow
- Task: Create `ResearchAdvisor` skeleton with placeholder methods
- Task: Add `/api/v1/advise` endpoints
- Task: Update block catalog API to expose dimensional metadata
- Task: Write contract tests for Analysis block dimensions
- Task: Update project documentation (catalog, blueprint, constitution)

### Epic: Reasoning Layer Implementation (Phase 3)
- Task: Implement `characterize_problem` with LLM prompt chain
- Task: Implement `match_candidates` with dimensional matching + LLM reasoning
- Task: Implement `recommend` with practitioner workflow context injection
- Task: Write practitioner workflows for all Analysis blocks
- Task: Score all Analysis blocks on dimensions
- Task: Wire advisor into chat panel
- Task: Wire advisor into CLI (`insights advise` command)
- Task: Measure: agent pipeline composition with vs. without practitioner workflows
