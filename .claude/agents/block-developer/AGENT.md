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
        # One of: source, transform, generation, evaluation,
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
| `RouterBase`    | `def resolve_route(self, inputs) -> List[str]` — returns which output edge IDs to activate |
| `HITLBase`      | `def render_checkpoint(self, inputs) -> Dict` — data to show the human<br>`def process_response(self, human_input) -> Dict` — handles human's response |
| `ComparatorBase`| `input_schemas` accepts N inputs of the same type (declared as a single type, quantity N)  |
| `ReportingBase` | `def declare_pipeline_inputs(self) -> List[str]` — list of upstream node IDs this block needs (not just adjacent predecessors)<br>Must include `output_format` in `config_schema` |

### File Organization

```
backend/blocks/
├── base.py                      # All base classes — only shared imports here
├── sources/                     # block_type = "source"
├── transforms/                  # block_type = "transform"
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
Example: `blocks/transforms/segmentation_kmeans.py`

### Block Registry

The engine discovers blocks via `backend/engine/registry.py`. New blocks are automatically discovered if they:
1. Live in the correct subdirectory under `blocks/`
2. Contain a class that inherits from `BlockBase`
3. Do not import from other block implementation files

Each block's registry entry should include a natural language `description` field (what it does, when to use it, what it assumes about inputs) — this is how the block catalog API and future agent composition features describe blocks.

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

---

## Context Documents

- **`.claude/context/block-contracts.md`** — full BlockBase interface, all type-specific base classes, config schema conventions, and test_fixtures pattern
- **`.claude/context/pipeline-schema.md`** — pipeline definition structure; reference when implementing blocks that interact with the pipeline schema (e.g. Reporting blocks that declare pipeline inputs)
