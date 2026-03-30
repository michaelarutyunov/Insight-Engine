# Block Contracts Specification

## Overview

All blocks implement `BlockBase`. The contract lives in `backend/blocks/base.py`. Type-specific base classes extend `BlockBase` with behavioral requirements specific to each block type. Block implementations inherit from the appropriate type-specific base.

Blocks that call external services also use `IntegrationMixin` from `backend/blocks/integration.py`, IntegrationMixin is a mixin -- it does not affect `block_type`. A block using it mixin is still an Analysis, Transform, Source, etc. from the engine's perspective.

---

11 block types: source, transform, analysis, generation, evaluation, comparator, llm_flex, router, hitl, reporting, sink.

---

## BlockBase (all blocks)

```python
from abc import ABC, abstractmethod
from typing import Any

class BlockBase(ABC):
    """Abstract base for all blocks in the Insights IDE block library."""

    @property
    @abstractmethod
    def block_type(self) -> str:
        """
        Abstract category of this block.
        Must be one of: source, transform, analysis, generation, evaluation,
        comparator, reporting, llm_flex, router, hitl, sink
        """
        ...
    @property
    @abstractmethod
    def input_schemas(self) -> list[str]:
        """
        List of accepted input data type identifiers.
        Source blocks return [].
        Each identifier must be in the edge data type vocabulary.
        """
        ...
    @property
    @abstractmethod
    def output_schemas(self) -> list[str]:
        """
        List of produced output data type identifiers.
        Sink blocks return [].
        Each identifier must be in the edge data type vocabulary.
        """
        ...
    @property
    @abstractmethod
    def config_schema(self) -> dict:
        """
        JSON Schema dict describing valid configuration for this block.
        Used to auto-generate the configuration UI and validate input.
        Must be consistent with validate_config().
        """
        ...
    @property
    @abstractmethod
    def description(self) -> str:
        """
        Natural language description for the block catalog.
        What this block does, when to use it, what it assumes about inputs.
        Used by the frontend palette and block discovery features.
        """
        ...
    @property
    @abstractmethod
    def methodological_notes(self) -> str:
        """
        Methodological guidance for block selection and usage.
        Explains when this block type is appropriate and any caveats.
        """
        ...
    @property
    def tags(self) -> list[str]:
        """
        Searchable tags for catalog filtering.
        Default: empty list. Override in implementations that
        benefit from categorization.
        """
        return []
    @abstractmethod
    def validate_config(self, config: dict) -> bool:
        """
        Returns True if the provided config is valid for this block.
        Must be consistent with config_schema — if config_schema marks a
        field as required, validate_config must reject configs missing it.
        """
        ...
    @abstractmethod
    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        """
        Execute this block.
        Args:
            inputs: Dict keyed by input port name. Values are data objects
                    matching the types declared in input_schemas.
            config:  Validated configuration dict. Assume validate_config()
                    has already been called.
        Returns:
            Dict keyed by output port name. MUST include every port declared
            in output_schemas. Extra keys are ignored by the engine.
        """
        ...
    def test_fixtures(self) -> dict:
        """
        Returns sample inputs, config, and expected outputs for contract tests.
        Required for all implementations. Used by the generic test suite.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement test_fixtures()")
```

---

## Type-Specific Base Classes

### SourceBase
```python
class SourceBase(BlockBase):
    """Base for all Source blocks. Entry points; no meaningful inputs."""
    @property
    def block_type(self) -> str:
        return "source"
    @property
    def input_schemas(self) -> list[str]:
        return []  # Sources have no inputs — sealed by base class
```
### TransformBase
```python
class TransformBase(BlockBase):
    """
    Base for deterministic data processing blocks.
    Given same inputs and config, output must be reproducible.
    The engine may cache Transform outputs.
    """
    @property
    def block_type(self) -> str:
        return "transform"
```
### AnalysisBase
```python
class AnalysisBase(BlockBase):
    """
    Base for question-driven analytical blocks.
    Analysis blocks consume input data and produce a structurally
    new output type that answers a research question. Their selection
    is driven by what the researcher wants to learn, not by what
    downstream blocks require.
    Key distinction from Transform:
    - Transform: input type preserved, demand-driven (data prep)
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
### GenerationBase
```python
class GenerationBase(BlockBase):
    """
    Base for non-deterministic content generation blocks (typically LLM-powered).
    Output varies across runs. Include version and seed tracking in config_schema.
    """
    @property
    def block_type(self) -> str:
        return "generation"
```
### EvaluationBase
```python
class EvaluationBase(BlockBase):
    """
    Base for blocks that judge a subject against criteria.
    Requires at least two input types: the subject and the evaluation criteria.
    """
    @property
    def block_type(self) -> str:
        return "evaluation"
```
### ComparatorBase
```python
class ComparatorBase(BlockBase):
    """
    Base for blocks that compare N same-typed inputs.
    Acts as a synchronization point — engine waits for all parallel branches
    to complete before calling execute().
    input_schemas declares a single type; the engine accepts N edges of that type.
    """
    @property
    def block_type(self) -> str:
        return "comparator"
```
### LLMFlexBase
```python
class LLMFlexBase(BlockBase):
    """
    Base for the generic programmable LLM block.
    Input/output shapes are user-configured, not preset.
    config_schema must include: prompt_template, input_port_names, output_port_names.
    """
    @property
    def block_type(self) -> str:
        return "llm_flex"
```
### RouterBase
```python
class RouterBase(BlockBase):
    """
    Base for conditional routing blocks.
    Controls graph traversal by activating specific output edges.
    Must implement resolve_route() in addition to execute().
    """
    @property
    def block_type(self) -> str:
        return "router"
    @abstractmethod
    def resolve_route(self, inputs: dict[str, Any]) -> list[str]:
        """
        Inspect inputs and return the list of output edge IDs to activate.
        The engine will only continue execution on edges in this list.
        All other output edges are deactivated for this run.
        """
        ...
```
### HITLBase
```python
class HITLBase(BlockBase):
    """
    Base for Human-In-The-Loop checkpoint blocks.
    When execute() reaches a HITL block, the engine:
      1. Calls render_checkpoint() to get data to show the human
      2. Persists full pipeline state to database
      3. Suspends execution and exits
      4. On POST /api/v1/hitl/{run_id}/respond, calls process_response()
      5. Resumes execution from this node's output
    """
    @property
    def block_type(self) -> str:
        return "hitl"
    @abstractmethod
    def render_checkpoint(self, inputs: dict[str, Any]) -> dict:
        """
        Prepare data to present to the human reviewer.
        Returns a dict that the frontend renders as the review interface.
        """
        ...
    @abstractmethod
    def process_response(self, human_input: dict) -> dict[str, Any]:
        """
        Handle the human's response and produce the block's output.
        human_input is the validated payload from POST /api/v1/hitl/{run_id}/respond.
        Returns a dict keyed by output port name (same contract as execute()).
        """
        ...
```
### ReportingBase
```python
class ReportingBase(BlockBase):
    """
    Base for blocks that assemble deliverables from multiple upstream outputs.
    Unlike other blocks, Reporting blocks can reference non-adjacent upstream nodes.
    The engine resolves these cross-pipeline references at execution time.
    config_schema must include output_format.
    """
    @property
    def block_type(self) -> str:
        return "reporting"
    @abstractmethod
    def declare_pipeline_inputs(self) -> list[str]:
        """
        Returns a list of upstream node IDs (not just adjacent predecessors)
        whose outputs this block needs.
        The engine uses this to collect the correct inputs before calling execute().
        """
        ...
```
### SinkBase
```python
class SinkBase(BlockBase):
    """Base for terminal blocks. Persists outputs; no downstream nodes."""
    @property
    def block_type(self) -> str:
        return "sink"
    @property
    def output_schemas(self) -> list[str]:
        return []  # Sinks have no outputs — sealed by base class
```
---
## IntegrationMixin (external service blocks)
```python
class IntegrationMixin:
    """
    Mixin for blocks that call external services.
    Provides common infrastructure for API-backed blocks: credential management,
    HTTP calls with exponential backoff, and long-running job polling.
    IntegrationMixin does NOT affect block_type. A block using this mixin
    is still an Analysis, Transform, Source, etc. from the engine's perspective.
    """
```
IntegrationMixin lives in `backend/blocks/integration.py` (not `base.py`).
Usage:
```python
class CintSampleSource(SourceBase, IntegrationMixin):
    @property
    def service_name(self) -> str:
        return "Cint Sample Exchange"
    ...
```
### Mixin properties
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `is_external_service` | `bool` | auto (always `True`) | Marker for execution planning; registry metadata |
| `service_name` | `str` | **yes** | Human-readable name of the external service |
| `estimated_latency` | `str` or no | Response time category: `'fast'` (<5s), `'moderate'` (5-60s), `'slow'` (1-10min), `'async'` (>10min) |
| `cost_per_call` | `dict` | no | Cost metadata, e.g. `{'unit': 'USD', 'estimate': 0.02, 'basis': 'per_row'}` |
### Mixin methods
| Method | Description |
|--------|-------------|
| `get_credentials(config)` | Extract credential keys from block config. Default: reads keys prefixed with `credential_`. |
| `call_external(endpoint, method, payload, headers, timeout, retries)` | HTTP call with exponential backoff. Returns parsed JSON. Raises `IntegrationTimeoutError`, `IntegrationRateLimitError`, or `IntegrationError`. |
| `poll_for_result(job_url, poll_interval, max_wait, headers)` | Poll a long-running job until completion. Raises `IntegrationTimeoutError` or `IntegrationError`. |
### Error classes
- `IntegrationError` — base exception for all external service failures
- `IntegrationTimeoutError(IntegrationError)` — Timeout after all retries
- `IntegrationRateLimitError(IntegrationError)` — Persistent 429 response; carries `retry_after` field
---
## Config Schema Conventions
All `config_schema` dicts must be valid JSON Schema (draft-07 compatible):
```python
# Minimal example for a Transform block
{
    "type": "object",
    "properties": {
        "n_clusters": {
            "type": "integer",
            "minimum": 2,
            "maximum": 20,
            "description": "Number of segments to create"
        },
        "features": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "Column names to use as segmentation features"
        }
    },
    "required": ["n_clusters", "features"],
    "additionalProperties": false
}
```
Rules:
- `"required"` must list every field that `validate_config()` rejects when missing
- `"additionalProperties": false` to prevent silent config drift
- Every property must have a `"description"` (used by catalog API and frontend UI)
- For LLM Flex blocks: include `prompt_template`, `input_port_names`, `output_port_names` in `"required"`
---
## test_fixtures Pattern
```python
def test_fixtures(self) -> dict:
    return {
        "inputs": {
            "respondent_data": [
                {"customer_id": "c1", "spend_monthly": 120, "frequency": 4, "recency": 7},
                {"customer_id": "c2", "spend_monthly": 45, "frequency": 1, "recency": 30},
            ]
        },
        "config": {
            "n_clusters": 2,
            "features": ["spend_monthly", "frequency", "recency"],
            "scaling": "standard"
        },
        "outputs": {
            "segmented_data": [
                {"customer_id": "c1", "segment_id": 0, "segment_label": "High Value"},
                {"customer_id": "c2", "segment_id": 1, "segment_label": "Low Engagement"},
            ]
        }
    }
```
The generic contract test suite calls `test_fixtures()` and checks:
1. `validate_config(fixtures["config"])` returns `True`
2. `input_schemas` is non-empty (unless Source)
3. `output_schemas` is non-empty (unless Sink)
4. `execute(fixtures["inputs"], fixtures["config"])` returns a dict
5. All keys in `fixtures["outputs"]` are present in the return value
---
## Invariants the Engine Relies On
 Invariant | Consequence if violated |
|-----------|------------------------|
| `execute()` returns all declared output ports | Engine fails to route outputs; downstream nodes starve |
| `validate_config()` consistent with `config_schema` | Config passes schema validation but fails `validate_config()`, or vice versa |
| `block_type` matches the actual base class | Registry assigns wrong executor behavior |
| `input_schemas`/`output_schemas` match actual I/O | Validator passes but runtime type mismatch |
| `description` is all implementations | Empty descriptions break catalog search and block discovery |
| `methodological_notes` in all implementations | Missing notes cause incorrect block selection |
| `tags` for filtering | Empty tags list is acceptable but filtering to fail silently |
| No imports from sibling block files | Cross-block coupling breaks registry isolation |
| `execute()` is `async` | Calling code `await`s it; synchronous implementation causes TypeError |
