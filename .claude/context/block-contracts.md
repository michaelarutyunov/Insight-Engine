# Block Contracts Specification

## Overview

All blocks implement `BlockBase`. The contract lives in `backend/blocks/base.py`. Type-specific base classes extend `BlockBase` with behavioral requirements specific to each block type. Block implementations inherit from the appropriate type-specific base.

---

## BlockBase (all blocks)

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BlockBase(ABC):
    """Abstract base for all blocks in the Insights IDE block library."""

    @property
    @abstractmethod
    def block_type(self) -> str:
        """
        Abstract category of this block.
        Must be one of: source, transform, generation, evaluation,
        comparator, reporting, llm_flex, router, hitl, sink
        """
        ...

    @property
    @abstractmethod
    def input_schemas(self) -> List[str]:
        """
        List of accepted input data type identifiers.
        Source blocks return [].
        Each identifier must be in the edge data type vocabulary.
        """
        ...

    @property
    @abstractmethod
    def output_schemas(self) -> List[str]:
        """
        List of produced output data type identifiers.
        Sink blocks return [].
        Each identifier must be in the edge data type vocabulary.
        """
        ...

    @property
    @abstractmethod
    def config_schema(self) -> Dict:
        """
        JSON Schema dict describing valid configuration for this block.
        Used to auto-generate the configuration UI and validate input.
        Must be consistent with validate_config().
        """
        ...

    @property
    def description(self) -> str:
        """
        Natural language description for the block catalog.
        What this block does, when to use it, what it assumes about inputs.
        Used by the frontend palette and future agent composition features.
        Default: empty string. Override in all implementations.
        """
        return ""

    @abstractmethod
    def validate_config(self, config: Dict) -> bool:
        """
        Returns True if the provided config is valid for this block.
        Must be consistent with config_schema — if config_schema marks a
        field as required, validate_config must reject configs missing it.
        """
        ...

    @abstractmethod
    async def execute(self, inputs: Dict[str, Any], config: Dict) -> Dict[str, Any]:
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

    def test_fixtures(self) -> Dict:
        """
        Returns sample inputs, config, and expected outputs for contract tests.
        Required for all implementations. Used by the generic test suite.

        Returns:
            {
                "inputs": Dict[str, Any],   # keyed by port name
                "config": Dict,              # valid configuration
                "outputs": Dict[str, Any],   # expected return from execute()
            }
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement test_fixtures()"
        )
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
    def input_schemas(self) -> List[str]:
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
    def resolve_route(self, inputs: Dict[str, Any]) -> List[str]:
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
    def render_checkpoint(self, inputs: Dict[str, Any]) -> Dict:
        """
        Prepare data to present to the human reviewer.
        Returns a dict that the frontend renders as the review interface.
        """
        ...

    @abstractmethod
    def process_response(self, human_input: Dict) -> Dict[str, Any]:
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
    def declare_pipeline_inputs(self) -> List[str]:
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
    def output_schemas(self) -> List[str]:
        return []  # Sinks have no outputs — sealed by base class
```

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
def test_fixtures(self) -> Dict:
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

| Invariant | Consequence if violated |
|-----------|------------------------|
| `execute()` returns all declared output ports | Engine fails to route outputs; downstream nodes starve |
| `validate_config()` consistent with `config_schema` | Config passes schema validation but fails `validate_config()`, or vice versa |
| `block_type` matches the actual base class | Registry assigns wrong executor behavior |
| `input_schemas`/`output_schemas` match actual I/O | Validator passes but runtime type mismatch |
| No imports from sibling block files | Cross-block coupling breaks registry isolation |
| `execute()` is `async` | Calling code `await`s it; synchronous implementation causes TypeError |
