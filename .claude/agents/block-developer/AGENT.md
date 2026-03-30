# Block Developer Agent

## Role

Implements new blocks and ensures all blocks conform to the BlockBase contract. Owns the `backend/blocks/` directory and `backend/blocks/base.py`.

---

## Domain Knowledge

### The BlockBase Contract

Every block implementation must satisfy:

```python
class BlockBase(ABC):
    @property
    @abstractmethod
    def block_type(self) -> str:
        # One of: source, transform, analysis, generation, evaluation,
        # comparator, reporting, llm_flex, router, hitl, sink
        ...

    @property
    @abstractmethod
    def input_schemas(self) -> List[str]:
        # List of accepted input data type identifiers
        # e.g. ["respondent_collection", "segment_profile_set"]
        # Source blocks: return []
        ...

    @property
    @abstractmethod
    def output_schemas(self) -> List[str]:
        # List of produced output data type identifiers
        # Sink blocks: return []
        ...

    @property
    @abstractmethod
    def config_schema(self) -> Dict:
        # JSON Schema dict for this block's configuration options
        ...

    @abstractmethod
    def validate_config(self, config: Dict) -> bool:
        # Returns True if config is valid, False otherwise
        # Must be consistent with config_schema
        ...

    @abstractmethod
    async def execute(self, inputs: Dict[str, Any], config: Dict) -> Dict[str, Any]:
        # inputs: keyed by input port name, values are data objects
        # config: validated configuration parameters
        # returns: keyed by output port name, values are data objects
        # MUST include all declared output ports in return value
        ...
```

### Type-Specific Base Classes

| Base Class      | Adds                                                                                       |
|-----------------|--------------------------------------------------------------------------------------------|
| `AnalysisBase`  | `block_type = "analysis"`, `preserves_input_type = False`, `dimensions` (abstract — see below) |
| `RouterBase`    | `def resolve_route(self, inputs) -> List[str]` — returns which output edge IDs to activate |
| `HITLBase`      | `def render_checkpoint(self, inputs) -> Dict` — data to show the human<br>`def process_response(self, human_input) -> Dict` — handles human's response |
| `ComparatorBase`| `input_schemas` accepts N inputs of the same type (declared as a single type, quantity N)  |
| `ReportingBase` | `def declare_pipeline_inputs(self) -> List[str]` — list of upstream node IDs this block needs (not just adjacent predecessors)<br>Must include `output_format` in `config_schema` |

### Analysis Blocks: Additional Required Properties

All `AnalysisBase` subclasses must implement two properties beyond the base BlockBase contract:

**`description`** and **`methodological_notes`** (from ADR-002): see block-contracts.md.

**`dimensions`** (from ADR-004): ordinal metadata for reasoning layer matching.

```python
@property
def dimensions(self) -> Dict[str, str]:
    return {
        "exploratory_confirmatory": "exploratory",  # exploratory | mixed | confirmatory
        "assumption_weight": "medium",              # low | medium | high
        "output_interpretability": "medium",        # low | medium | high
        "sample_sensitivity": "high",               # low | medium | high
        "reproducibility": "high",                  # low | medium | high
        "data_structure_affinity": "numeric_continuous",  # unstructured_text | categorical | ordinal | numeric_continuous | mixed
    }
```

All six dimension keys are required. Values must be from the allowed sets defined in `reasoning/dimensions.py`. See `.claude/context/reasoning-layer.md` for the method classification reference table with pre-validated scores for 32 methods.

**`practitioner_workflow`** (optional): return the workflow filename if one exists.

```python
@property
def practitioner_workflow(self) -> Optional[str]:
    return "segmentation.md"  # or None
```

### IntegrationMixin

For blocks that call external APIs, inherit from both the type base and `IntegrationMixin` from `blocks/integration.py`:

```python
class MySourceBlock(SourceBase, IntegrationMixin):
    @property
    def service_name(self) -> str:
        return "My External Service"

    @property
    def estimated_latency(self) -> str:
        return "moderate"  # fast | moderate | slow | async
```

`IntegrationMixin` provides `get_credentials()`, `call_external()` (httpx with backoff), and `poll_for_result()`. Does NOT affect `block_type`. Never implement raw HTTP calls in a block — always use `call_external()`.

### File Organization

```
backend/blocks/
├── base.py                      # All base classes — only shared imports here
├── integration.py               # IntegrationMixin and exception classes
├── sources/                     # block_type = "source"
├── transforms/                  # block_type = "transform"
├── analysis/                    # block_type = "analysis"
├── generation/                  # block_type = "generation"
├── evaluation/                  # block_type = "evaluation"
├── comparison/                  # block_type = "comparator"
├── reporting/                   # block_type = "reporting"
├── llm_flex/                    # block_type = "llm_flex"
├── routing/                     # block_type = "router"
├── hitl/                        # block_type = "hitl"
└── sinks/                       # block_type = "sink"
```

One file per block implementation: `blocks/{type}/{implementation}.py`
Example: `blocks/analysis/segmentation_kmeans.py`

### Block Registry

The engine discovers blocks via `backend/engine/registry.py`. New blocks are automatically discovered if they:
1. Live in the correct subdirectory under `blocks/`
2. Contain a class that inherits from `BlockBase`
3. Do not import from other block implementation files

The registry exposes `description`, `methodological_notes`, `tags`, and (for Analysis blocks) `dimensions` and `practitioner_workflow` in the block catalog API.

---

## Testing Requirements

Every block implementation must include:

```python
def test_fixtures(self) -> Dict:
    """Returns sample inputs and expected outputs for contract tests."""
    return {
        "inputs": {...},    # sample inputs keyed by port name
        "config": {...},    # valid configuration
        "outputs": {...},   # expected outputs keyed by port name
    }
```

Test coverage rules by block category:

| Category                    | Test requirement                                              |
|-----------------------------|---------------------------------------------------------------|
| Transform (deterministic)   | Fixed input → assert exact output                             |
| LLM-powered (Generation, Evaluation, LLM Flex) | Mock the API call; test prompt construction and response parsing |
| Router                      | Test each condition branch separately                         |
| HITL                        | Test `render_checkpoint()` output structure and `process_response()` with valid and invalid human input |
| Reporting                   | Test that all declared pipeline inputs are referenced in output |

---

## Anti-Patterns to Flag

- **Cross-block imports**: A block importing from another block implementation. All shared logic goes in `blocks/base.py` or a shared utility module — never in a sibling block file.
- **Missing schema declarations**: `input_schemas = []` when the block actually accepts inputs, or vice versa.
- **Incomplete output ports**: `execute()` returns a dict missing one or more keys declared in `output_schemas`.
- **Config/validate mismatch**: `config_schema` declares a field as required but `validate_config()` treats it as optional, or vice versa.
- **Synchronous LLM calls**: LLM API calls inside `execute()` must be `await`-ed; `execute()` is always `async`.
- **Hardcoded data type strings**: Data type identifiers (e.g. `"respondent_collection"`) should be imported from a shared constants module, not repeated as string literals.
- **Invalid dimension values**: Analysis blocks must return dimension values from the allowed sets in `reasoning/dimensions.py`. Do not invent values — use `.claude/context/reasoning-layer.md` method classification table as reference.
- **Raw HTTP in blocks**: Never use `httpx` or `aiohttp` directly in a block. Use `IntegrationMixin.call_external()` for all external API calls.

---

## Context Documents

- **`.claude/context/block-contracts.md`** — full BlockBase interface, all type-specific base classes, config schema conventions, and test_fixtures pattern
- **`.claude/context/pipeline-schema.md`** — pipeline definition structure; reference when implementing blocks that interact with the pipeline schema (e.g. Reporting blocks that declare pipeline inputs)
- **`.claude/context/reasoning-layer.md`** — load when implementing `dimensions` on any Analysis block; contains pre-validated dimension scores for 32 methods
