---
name: new-block
description: Use when creating a new block implementation for Insights IDE. Triggered by "/new-block <block_type> <implementation_name>" or "create a new <type> block called <name>".
---

# New Block Scaffolder

Scaffold a new block implementation and its contract test.

## Arguments

```
/new-block <block_type> <implementation_name>
```

Examples:
- `/new-block transform segmentation_kmeans`
- `/new-block source csv_loader`
- `/new-block hitl approval_checkpoint`

---

## Step 1: Resolve paths

| block_type  | directory              | base class       | extra required methods                                      |
|-------------|------------------------|------------------|-------------------------------------------------------------|
| source      | blocks/sources/        | SourceBase       | _(none — input_schemas sealed by base)_                     |
| transform   | blocks/transforms/     | TransformBase    | _(none)_                                                    |
| generation  | blocks/generation/     | GenerationBase   | _(none)_                                                    |
| evaluation  | blocks/evaluation/     | EvaluationBase   | _(none)_                                                    |
| comparator  | blocks/comparison/     | ComparatorBase   | _(none)_                                                    |
| llm_flex    | blocks/llm_flex/       | LLMFlexBase      | _(none)_                                                    |
| router      | blocks/routing/        | RouterBase       | `resolve_route(self, inputs) -> list[str]`                  |
| hitl        | blocks/hitl/           | HITLBase         | `render_checkpoint(self, inputs) -> dict` · `process_response(self, human_input) -> dict` |
| reporting   | blocks/reporting/      | ReportingBase    | `declare_pipeline_inputs(self) -> list[str]`                |
| sink        | blocks/sinks/          | SinkBase         | _(none — output_schemas sealed by base)_                    |

- Implementation file: `backend/{directory}/{implementation_name}.py`
- Test file: `backend/tests/test_blocks/test_{implementation_name}.py`

---

## Step 2: Create the implementation file

```python
from typing import Any

from blocks.base import <BaseClass>


class <ClassName>(<BaseClass>):
    """One-line description of what this block does."""

    @property
    def input_schemas(self) -> list[str]:
        # Source blocks: omit this property (handled by base)
        # All others: list accepted data type identifiers
        # Valid types: respondent_collection, segment_profile_set, concept_brief_set,
        #              evaluation_set, text_corpus, persona_set, generic_blob
        return ["<data_type>"]

    @property
    def output_schemas(self) -> list[str]:
        # Sink blocks: omit this property (handled by base)
        return ["<data_type>"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                # "<param>": {"type": "string", "description": "..."}
            },
            "required": [],
            "additionalProperties": False,
        }

    @property
    def description(self) -> str:
        return "<What this block does, when to use it, what it assumes about inputs>"

    def validate_config(self, _config: dict) -> bool:
        # Must be consistent with config_schema required fields
        # Rename _config → config once you add real validation logic
        return True

    async def execute(self, _inputs: dict[str, Any], _config: dict) -> dict[str, Any]:
        # Must return ALL ports declared in output_schemas
        # Rename _inputs/_config → inputs/config once implemented
        raise NotImplementedError

    # --- Type-specific methods (add only if block_type requires them) ---

    # Router only:
    # def resolve_route(self, _inputs: dict[str, Any]) -> list[str]:
    #     raise NotImplementedError

    # HITL only:
    # def render_checkpoint(self, _inputs: dict[str, Any]) -> dict:
    #     raise NotImplementedError
    # def process_response(self, _human_input: dict) -> dict[str, Any]:
    #     raise NotImplementedError

    # Reporting only:
    # def declare_pipeline_inputs(self) -> list[str]:
    #     raise NotImplementedError

    def test_fixtures(self) -> dict:
        return {
            "inputs": {
                # "<port_name>": <sample_value>
            },
            "config": {},
            "outputs": {
                # "<port_name>": <expected_value>
            },
        }
```

Name the class: `CamelCase` of the implementation name (e.g. `segmentation_kmeans` → `SegmentationKmeans`).

---

## Step 3: Create the test file

```python
import pytest

from blocks.<directory_module>.<implementation_name> import <ClassName>


@pytest.fixture
def block():
    return <ClassName>()


def test_block_type(block):
    assert block.block_type == "<block_type>"


def test_schemas_declared(block):
    # Source blocks skip input_schemas check; Sink blocks skip output_schemas check
    assert isinstance(block.input_schemas, list)
    assert isinstance(block.output_schemas, list)


def test_config_schema_is_valid_json_schema(block):
    schema = block.config_schema
    assert schema.get("type") == "object"
    assert "properties" in schema


def test_validate_config_with_fixtures(block):
    fixtures = block.test_fixtures()
    assert block.validate_config(fixtures["config"]) is True


@pytest.mark.asyncio
async def test_execute_returns_all_output_ports(block):
    fixtures = block.test_fixtures()
    # Skip if execute is not yet implemented
    try:
        result = await block.execute(fixtures["inputs"], fixtures["config"])
        for port in block.output_schemas:
            assert port in result, f"Missing output port: {port}"
    except NotImplementedError:
        pytest.skip("execute() not yet implemented")
```

Replace `<directory_module>` with the Python module name (e.g. `sources`, `transforms`, `routing`).

---

## Step 4: Format

```bash
uv run ruff format backend/blocks/<dir>/<implementation>.py backend/tests/test_blocks/test_<implementation>.py
uv run ruff check backend/blocks/<dir>/<implementation>.py --fix
```

---

## Done checklist

- [ ] File created at correct path for block_type
- [ ] Correct base class imported and used
- [ ] `input_schemas` / `output_schemas` populated with valid data types from `schemas/data_objects.py`
- [ ] `config_schema` `required` list matches `validate_config()` logic
- [ ] `description` property filled in (used by block catalog API)
- [ ] Type-specific methods added if block_type requires them
- [ ] `test_fixtures()` provides non-empty sample data
- [ ] Test file created and passes `uv run pytest tests/test_blocks/test_<implementation>.py`
- [ ] Ruff clean
