# Block Taxonomy Refactor — ADRs & Migration Guide

Three linked architectural changes to the block system, to be applied against the existing Phase 1–2 codebase. Sequenced to avoid breaking the execution engine during migration.

---

## ADR-001: Split Transform into Transform and Analysis

### Status
Accepted

### Context
The current `transform` block type covers both data preparation operations (filter, clean, recode, weight) and analytical operations (k-means segmentation, LCA, driver analysis). These have fundamentally different roles in pipeline composition:

- **Preparation** is demand-driven — selected because a downstream block requires data in a specific shape. Preserves the input data type (e.g. `respondent_collection → respondent_collection`).
- **Analysis** is question-driven — selected because the researcher wants to answer a specific question. Consumes input and produces a structurally new output type (e.g. `respondent_collection → segment_profile_set`).

Collapsing both into `transform` prevents an LLM agent from reasoning about pipeline composition in two distinct modes: "what do I want to learn?" (select Analysis) vs. "what does my data need to look like?" (infer Transforms from Analysis requirements).

### Decision
Introduce `analysis` as the 11th block type. Reclassify existing blocks accordingly.

### Reclassification

| Block | Current Type | New Type | Rationale |
|---|---|---|---|
| `filter_transform` | transform | **transform** | Row subsetting, preserves data type |
| `data_cleaning` | transform | **transform** | Prep operation, demand-driven |
| `weighting` | transform | **transform** | Prep, makes data suitable for analysis |
| `segmentation_kmeans` | transform | **analysis** | Answers "what segments exist?", produces new type |
| `segmentation_lca` | transform | **analysis** | Same — analytical, question-driven |
| `rfm_analysis` | transform | **analysis** | Produces customer value classification |

### Heuristic for future classification
A block is **Analysis** if and only if:
1. It produces an output data type that is structurally different from its input (not just filtered/modified), AND
2. It answers a research or methodological question on its own (a stakeholder would recognize its output as a "finding"), AND
3. Its selection is driven by the research question, not by downstream block requirements.

If any of these fail, it is a **Transform**.

### Consequences
- `block_type` enum gains `analysis` value
- `blocks/` directory gains `analysis/` subdirectory
- `blocks/transforms/segmentation_kmeans.py` moves to `blocks/analysis/segmentation_kmeans.py`
- `AnalysisBase` class created in `blocks/base.py`
- Frontend block palette gains an Analysis category
- Pipeline definitions using `block_type: "transform"` for reclassified blocks must be migrated
- Block catalog document updated
- Agent constitution (CLAUDE.md) block type table updated

---

## ADR-002: Embedded Block Descriptions and Methodological Notes

### Status
Accepted

### Context
The block catalog currently documents blocks externally. An LLM composing a pipeline or recommending blocks has no machine-readable way to understand *when* to use a block, *what it assumes* about inputs, or *what alternatives exist*. The "Use when" field in the catalog is a one-sentence afterthought rather than a structured reasoning aid.

For the block system to function as a reasoning vocabulary — not just an execution contract — each block must carry its own description and methodological guidance as part of its implementation.

### Decision
Add three required properties to `BlockBase`:

```python
@property
@abstractmethod
def description(self) -> str:
    """One-paragraph summary: what this block does and when to use it.
    Written for an LLM selecting blocks during pipeline composition.
    Should answer: 'If I need to [goal], is this the right block?'"""
    ...

@property
@abstractmethod
def methodological_notes(self) -> str:
    """Assumptions, limitations, data requirements, and alternatives.
    Written for an LLM reasoning about whether this block is appropriate
    for a specific dataset and research question.
    
    Should cover:
    - What the block assumes about input data (e.g. numeric features,
      no missing values, minimum sample size)
    - Known limitations or failure modes
    - When to use an alternative block instead
    - Methodological references if relevant
    """
    ...

@property
def tags(self) -> List[str]:
    """Searchable tags for catalog filtering.
    Convention: include method family, data requirements, output type.
    Example: ['clustering', 'numeric-features', 'unsupervised']"""
    return []
```

### Design rationale

**Why properties on the class, not external metadata?**
Keeps description co-located with implementation. When a developer writes a block, they write its reasoning guidance in the same file. Prevents drift between what a block does and what the catalog says it does.

**Why `methodological_notes` separate from `description`?**
Different consumption contexts. `description` is for catalog browsing and quick selection — an agent scanning all Analysis blocks. `methodological_notes` is for deep reasoning — an agent deciding between k-means and LCA for a specific dataset. Loading all methodological notes into context when you only need a catalog listing wastes tokens.

**Why `tags` is not abstract (has a default)?**
Tags are useful but not critical. Blocks should work without them. The empty default means existing blocks don't break when the property is added to the base class.

### Example: K-Means Segmentation

```python
class KMeansAnalysis(AnalysisBase):

    @property
    def description(self) -> str:
        return (
            "Clusters respondents into segments using K-Means algorithm. "
            "Use when you need a simple, interpretable segmentation of "
            "respondents based on numeric behavioral or attitudinal features. "
            "Produces segment profiles with centroid-based descriptions."
        )

    @property
    def methodological_notes(self) -> str:
        return (
            "Assumes spherical clusters of roughly equal size. Sensitive to "
            "outliers — consider outlier removal or robust scaling in upstream "
            "Transform blocks. Requires all features to be numeric; categorical "
            "features must be encoded upstream. Feature scaling (standard or "
            "minmax) is strongly recommended and configurable. "
            "\n\n"
            "Cluster count (n_clusters) must be specified; the block does not "
            "perform automatic selection. Consider running multiple times with "
            "different k values and using a Comparator block downstream to "
            "evaluate solutions via silhouette score or business interpretability. "
            "\n\n"
            "Alternatives: Use LCA (segmentation_lca) when features are "
            "categorical or mixed, or when probabilistic segment membership "
            "is needed. Use RFM (rfm_analysis) for transaction-based "
            "customer value segmentation where the framework is predetermined."
        )

    @property
    def tags(self) -> List[str]:
        return [
            "clustering", "segmentation", "unsupervised",
            "numeric-features", "requires-scaling"
        ]
```

### Consequences
- `BlockBase` gains `description`, `methodological_notes`, and `tags` properties
- All existing block implementations must add `description` and `methodological_notes`
- Block registry exposes these fields via `GET /api/v1/blocks` catalog endpoint
- Chat panel context builder includes block descriptions when assembling LLM context
- Block catalog document (`block-catalog.md`) can be generated from registry at build time rather than maintained manually

---

## ADR-003: Integration Mixin for External Service Blocks

### Status
Accepted

### Context
Some blocks execute their logic by calling third-party APIs (sample providers, qual analysis platforms, syndicated data services). These blocks share infrastructure concerns — credential management, HTTP error handling, retries, rate limiting, response caching, long-running job polling — that are orthogonal to their analytical role.

Making Integration a block type would leak infrastructure into the conceptual taxonomy. The agent should reason about *what* a block does (Analysis, Transform, etc.), not *how* it executes.

### Decision
Create `IntegrationMixin` as a mixin class that block implementations optionally inherit alongside their primary type base class.

```python
from typing import Optional, Dict, Any

class IntegrationMixin:
    """Mixin for blocks that call external services.
    Provides common infrastructure for API-backed blocks.
    
    Does NOT affect block_type — a block using this mixin is still
    an Analysis, Transform, Source, etc. from the agent's perspective.
    """

    @property
    def is_external_service(self) -> bool:
        """Always True for IntegrationMixin blocks.
        Exposed in block registry metadata for execution planning."""
        return True

    @property
    def service_name(self) -> str:
        """Human-readable name of the external service.
        Example: 'Cint Sample Exchange', 'Amazon Reviews API'"""
        raise NotImplementedError

    @property
    def estimated_latency(self) -> Optional[str]:
        """Expected response time category: 'fast' (<5s), 'moderate' (5-60s),
        'slow' (1-10min), 'async' (>10min, requires polling).
        Used by engine for execution planning and timeout configuration."""
        return None

    @property
    def cost_per_call(self) -> Optional[Dict[str, Any]]:
        """Optional cost metadata for execution planning.
        Example: {'unit': 'USD', 'estimate': 0.02, 'basis': 'per_row'}
        Returns None if free or cost is not meaningfully estimable."""
        return None

    def get_credentials(self, config: Dict) -> Dict[str, str]:
        """Retrieve credentials for the external service.
        Default: reads from config keys prefixed with 'credential_'.
        Override for custom credential resolution (env vars, vault, etc.)."""
        return {
            k.replace("credential_", ""): v
            for k, v in config.items()
            if k.startswith("credential_")
        }

    async def call_external(
        self,
        endpoint: str,
        method: str = "POST",
        payload: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 30,
        retries: int = 3,
    ) -> Dict[str, Any]:
        """HTTP call with retry logic, rate limiting, and error normalization.
        Blocks call this instead of raw httpx/aiohttp.
        
        Raises:
            IntegrationError: on non-retryable failure after exhausting retries
            IntegrationTimeoutError: on timeout after all retries
        """
        # Implementation: exponential backoff, structured error responses,
        # rate limit header parsing, response logging for audit trail
        raise NotImplementedError("Implement in infrastructure layer")

    async def poll_for_result(
        self,
        job_url: str,
        poll_interval: int = 5,
        max_wait: int = 600,
    ) -> Dict[str, Any]:
        """Poll a long-running external job until completion.
        Used for async API patterns where the service returns a job ID."""
        raise NotImplementedError("Implement in infrastructure layer")
```

### Usage pattern

```python
class CintSampleSource(SourceBase, IntegrationMixin):
    """Fetches sample from Cint Sample Exchange API."""

    @property
    def block_type(self) -> str:
        return "source"

    @property
    def service_name(self) -> str:
        return "Cint Sample Exchange"

    @property
    def estimated_latency(self) -> str:
        return "async"  # sample fulfillment takes hours/days

    @property
    def description(self) -> str:
        return (
            "Connects to Cint Sample Exchange to recruit survey respondents "
            "matching specified demographic and behavioral quotas. Returns "
            "completed survey responses as a respondent_collection."
        )

    async def execute(self, inputs, config):
        creds = self.get_credentials(config)
        # Use self.call_external() for API calls
        # Use self.poll_for_result() for async fulfillment
        ...
```

### Block registry metadata
The registry exposes integration metadata alongside block descriptions:

```json
{
    "block_implementation": "cint_sample_source",
    "block_type": "source",
    "description": "Connects to Cint Sample Exchange...",
    "is_external_service": true,
    "service_name": "Cint Sample Exchange",
    "estimated_latency": "async",
    "cost_per_call": {"unit": "USD", "estimate": 0.50, "basis": "per_respondent"}
}
```

The agent uses `is_external_service`, `estimated_latency`, and `cost_per_call` for execution planning (e.g. warning before placing an expensive API block inside a loop), but NOT for pipeline composition logic. The block's `block_type`, `description`, and `methodological_notes` drive composition.

### Consequences
- New file: `blocks/integration.py` containing `IntegrationMixin` and exception classes
- External-service blocks inherit from both their type base and `IntegrationMixin`
- Block registry serialization includes integration metadata when present
- Frontend can display cost/latency indicators on external-service blocks
- Engine can apply different timeout and retry behavior to integration blocks
- No change to block type enum — Integration is not a type

---

## Migration Plan

Sequenced to keep the execution engine and existing pipelines working throughout.

### Step 1: Add new properties to BlockBase (non-breaking)

**Files to modify:** `backend/blocks/base.py`

1. Add `description` and `methodological_notes` as abstract properties on `BlockBase`
2. Add `tags` as a concrete property with empty list default on `BlockBase`
3. Temporarily provide default implementations that return placeholder strings, so existing blocks don't immediately break:

```python
# Temporary — remove after all blocks are updated
@property
def description(self) -> str:
    return f"{self.block_type} block: {self.__class__.__name__}. Description pending."

@property
def methodological_notes(self) -> str:
    return "Methodological notes pending."
```

4. Make these non-abstract initially (concrete with defaults). They become abstract once all blocks have real implementations.

**Verify:** All existing tests pass unchanged.

### Step 2: Add descriptions to all existing blocks

**Files to modify:** Every file in `backend/blocks/*/`

For each existing block implementation, add meaningful `description`, `methodological_notes`, and `tags` properties. Prioritize:
1. Blocks that are currently used in test pipelines or demo workflows
2. Analysis-candidate blocks (segmentation_kmeans, etc.) — these need the richest methodological notes

Use the k-means example in ADR-002 as the quality benchmark. Every `methodological_notes` should cover: assumptions, data requirements, limitations, and alternatives.

**Verify:** Run the full test suite. Run any saved demo pipelines.

### Step 3: Expose descriptions in the block catalog API

**Files to modify:** `backend/api/blocks.py`, `backend/engine/registry.py`

1. Update the registry to include `description`, `methodological_notes`, and `tags` when serializing block metadata
2. Update `GET /api/v1/blocks` response schema to include the new fields
3. Add query parameter support: `GET /api/v1/blocks?tags=clustering` for filtered catalog queries

**Verify:** Call the blocks endpoint, confirm new fields appear. Frontend block palette still renders correctly (it should ignore unknown fields).

### Step 4: Create the IntegrationMixin (non-breaking, additive)

**New file:** `backend/blocks/integration.py`

1. Implement `IntegrationMixin` as specified in ADR-003
2. Implement `call_external()` and `poll_for_result()` with a real HTTP client (httpx recommended for async)
3. Define exception classes: `IntegrationError`, `IntegrationTimeoutError`, `IntegrationRateLimitError`
4. No existing blocks use it yet — this is purely additive

**Verify:** Import the mixin, instantiate a test class that inherits from `SourceBase` and `IntegrationMixin`, confirm no conflicts.

### Step 5: Introduce the Analysis block type

**Files to modify:** `backend/blocks/base.py`, `backend/schemas/block_types.py`

1. Add `"analysis"` to the block type enum in `schemas/block_types.py`
2. Create `AnalysisBase(BlockBase)` in `blocks/base.py`:

```python
class AnalysisBase(BlockBase):
    """Base for question-driven analytical blocks.
    
    Analysis blocks consume input data and produce a structurally 
    new output type that answers a research question. Their selection
    is driven by what the researcher wants to learn, not by what 
    downstream blocks require.
    
    Key distinction from Transform:
    - Transform: input type preserved, demand-driven (prep)
    - Analysis: new output type produced, question-driven (insight)
    """

    @property
    def block_type(self) -> str:
        return "analysis"

    @property
    def preserves_input_type(self) -> bool:
        """Analysis blocks produce new types by definition."""
        return False
```

3. Create directory: `backend/blocks/analysis/`
4. Add `__init__.py` to the new directory

**Verify:** Block type enum accepts "analysis". AnalysisBase can be instantiated in tests.

### Step 6: Reclassify existing blocks

**Files to move and modify:**
- `backend/blocks/transforms/segmentation_kmeans.py` → `backend/blocks/analysis/segmentation_kmeans.py`
- (same for any other analysis blocks: segmentation_lca, etc.)

For each reclassified block:
1. Move the file to `blocks/analysis/`
2. Change the base class from `TransformBase` to `AnalysisBase`
3. Update `block_type` return value to `"analysis"`
4. Verify `input_schemas` and `output_schemas` are correct (Analysis blocks should have different input and output types)

**Verify:** Registry discovers blocks in new location. Existing test pipelines that reference these blocks still load (may need pipeline definition updates — see Step 7).

### Step 7: Migrate existing pipeline definitions

**Files to modify:** Any saved pipeline JSON files, database records, test fixtures

Any saved pipeline that references a reclassified block with `"block_type": "transform"` must be updated to `"block_type": "analysis"`.

Options:
- **If few saved pipelines:** manual update
- **If many:** write a migration script:

```python
"""Migration: update block_type for reclassified blocks."""

RECLASSIFIED = {
    "segmentation_kmeans": "analysis",
    "segmentation_lca": "analysis",
    # add others as reclassified
}

def migrate_pipeline(pipeline_json: dict) -> dict:
    for node in pipeline_json.get("nodes", []):
        impl = node.get("block_implementation")
        if impl in RECLASSIFIED:
            node["block_type"] = RECLASSIFIED[impl]
    return pipeline_json
```

**Verify:** All saved pipelines load and validate. Execution engine runs them without errors.

### Step 8: Update frontend block palette

**Files to modify:** Frontend components that render the block palette/sidebar

1. Add "Analysis" as a new category in the block palette
2. Give it distinct visual styling (color, icon) that differentiates it from Transform
3. Reclassified blocks appear under Analysis, not Transform
4. Ordering suggestion: Source → Transform → Analysis → Generation → Evaluation → Comparator → LLM Flex → Router → HITL → Reporting → Sink

**Verify:** Palette shows 11 categories. Dragging an Analysis block onto canvas creates correct node. Connecting an Analysis block respects type validation.

### Step 9: Update documentation and agent context

**Files to modify:**
- `block-catalog.md` — add Analysis section, move reclassified blocks, add description/methodological_notes for all blocks
- `.claude/CLAUDE.md` (constitution) — update block type table from 10 to 11 types, add Analysis row
- `.claude/agents/block-developer/AGENT.md` — update to reference AnalysisBase, IntegrationMixin, description requirements
- `.claude/context/block-contracts.md` — update with new base classes and properties
- `insights-ide-technical-blueprint.md` — update block taxonomy, directory structure, base class contract
- `insights-ide-vision.md` — update block taxonomy section (10 → 11 types)

### Step 10: Make description and methodological_notes abstract

**Files to modify:** `backend/blocks/base.py`

Once all blocks have real implementations (confirmed in Step 2):
1. Remove the temporary default implementations from Step 1
2. Mark `description` and `methodological_notes` as `@abstractmethod`
3. Any block without these properties will now fail at import time — this is the desired enforcement

**Verify:** Full test suite passes. Any block missing descriptions fails loudly.

---

## Post-Migration Validation Checklist

- [ ] Block type enum has 11 values (source, transform, analysis, generation, evaluation, comparator, llm_flex, router, hitl, reporting, sink)
- [ ] `AnalysisBase` exists in `blocks/base.py` and is importable
- [ ] `IntegrationMixin` exists in `blocks/integration.py` and is importable
- [ ] All blocks have non-placeholder `description` and `methodological_notes`
- [ ] `GET /api/v1/blocks` returns `description`, `methodological_notes`, `tags` for each block
- [ ] `GET /api/v1/blocks` returns `is_external_service`, `service_name`, `estimated_latency`, `cost_per_call` for integration blocks
- [ ] Existing saved pipelines load and validate after migration
- [ ] Existing saved pipelines execute without regression
- [ ] Frontend palette shows 11 block categories with correct blocks in each
- [ ] No block imports from another block's implementation file
- [ ] No block returns a placeholder description string
- [ ] Agent constitution reflects 11 block types
- [ ] Block developer agent spec references AnalysisBase, IntegrationMixin, and description requirements
