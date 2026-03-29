"""Contract tests for all block implementations.

Verifies that each block:
  1. Implements BlockBase with valid schemas
  2. Passes validate_config with its own test fixture config
  3. Returns all declared output ports from execute()
  4. Provides test_fixtures()
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks._llm_client import BlockExecutionError  # noqa: E402
from blocks.base import (  # noqa: E402
    BlockBase,
    ComparatorBase,
    EvaluationBase,
    GenerationBase,
    HITLBase,
    LLMFlexBase,
    ReportingBase,
    RouterBase,
    SinkBase,
    SourceBase,
    TransformBase,
)
from blocks.comparison.side_by_side_comparator import SideBySideComparator
from blocks.evaluation.rubric_evaluation import RubricEvaluation
from blocks.generation.llm_generation import LLMGeneration
from blocks.hitl.approval_gate import ApprovalGate
from blocks.llm_flex.prompt_flex import PromptFlex
from blocks.reporting.markdown_report import MarkdownReport
from blocks.routing.conditional_router import ConditionalRouter
from blocks.sinks.json_sink import JSONSink
from blocks.sources.csv_source import CSVSource
from blocks.transforms.filter_transform import FilterTransform

ALL_BLOCKS: list[type[BlockBase]] = [
    CSVSource,
    FilterTransform,
    LLMGeneration,
    RubricEvaluation,
    SideBySideComparator,
    PromptFlex,
    ConditionalRouter,
    ApprovalGate,
    MarkdownReport,
    JSONSink,
]

BASE_TYPE_MAP: dict[type, str] = {
    SourceBase: "source",
    TransformBase: "transform",
    GenerationBase: "generation",
    EvaluationBase: "evaluation",
    ComparatorBase: "comparator",
    LLMFlexBase: "llm_flex",
    RouterBase: "router",
    HITLBase: "hitl",
    ReportingBase: "reporting",
    SinkBase: "sink",
}


def _run(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Parameterised contract tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("block_cls", ALL_BLOCKS, ids=lambda c: c.__name__)
class TestBlockContracts:
    def test_has_test_fixtures(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        fixtures = block.test_fixtures()
        assert isinstance(fixtures, dict)
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures

    def test_block_type_matches_base(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        expected_type = None
        for base_cls, type_str in BASE_TYPE_MAP.items():
            if isinstance(block, base_cls):
                expected_type = type_str
                break
        assert expected_type is not None, f"{block_cls.__name__} does not match any known base"
        assert block.block_type == expected_type

    def test_schemas_are_lists_of_strings(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        assert isinstance(block.input_schemas, list)
        assert isinstance(block.output_schemas, list)
        assert all(isinstance(s, str) for s in block.input_schemas)
        assert all(isinstance(s, str) for s in block.output_schemas)

    def test_config_schema_is_dict(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        assert isinstance(block.config_schema, dict)

    def test_validate_config_accepts_fixture(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        config = block.test_fixtures()["config"]
        assert block.validate_config(config) is True

    def test_description_is_nonempty_string(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        assert isinstance(block.description, str)
        assert len(block.description) > 0

    def test_execute_returns_declared_outputs(self, block_cls: type[BlockBase]) -> None:
        from blocks._llm_client import HITLSuspendSignal

        block = block_cls()
        fixtures = block.test_fixtures()

        # HITL blocks raise HITLSuspendSignal instead of returning output
        if isinstance(block, HITLBase):
            with pytest.raises(HITLSuspendSignal) as exc_info:
                _run(block.execute(fixtures["inputs"], fixtures["config"]))
            # Verify checkpoint data is present
            assert hasattr(exc_info.value, "checkpoint_data")
            assert isinstance(exc_info.value.checkpoint_data, dict)
        else:
            result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
            assert isinstance(result, dict)
            for port in block.output_schemas:
                assert port in result, f"Missing output port: {port}"

    def test_validate_config_rejects_empty(self, block_cls: type[BlockBase]) -> None:
        block = block_cls()
        # ApprovalGate accepts empty config because all fields have defaults
        if block_cls.__name__ == "ApprovalGate":
            assert block.validate_config({}) is True
        else:
            assert block.validate_config({}) is False


# ---------------------------------------------------------------------------
# Block-specific tests
# ---------------------------------------------------------------------------


class TestCSVSource:
    def test_execute_output(self) -> None:
        block = CSVSource()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]

    def test_source_has_no_inputs(self) -> None:
        assert CSVSource().input_schemas == []


class TestFilterTransform:
    def test_execute_output(self) -> None:
        block = FilterTransform()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestLLMGeneration:
    def test_execute_output(self) -> None:
        block = LLMGeneration()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestRubricEvaluation:
    def test_execute_output(self) -> None:
        block = RubricEvaluation()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestSideBySideComparator:
    def test_execute_output(self) -> None:
        block = SideBySideComparator()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestPromptFlex:
    def test_execute_output(self) -> None:
        block = PromptFlex()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]


class TestConditionalRouter:
    def test_execute_output(self) -> None:
        block = ConditionalRouter()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]

    def test_resolve_route(self) -> None:
        block = ConditionalRouter()
        fixtures = block.test_fixtures()
        # Pass config directly to resolve_route
        routes = block.resolve_route(fixtures["inputs"], fixtures["config"])
        assert routes == fixtures["expected_routes"]


class TestApprovalGate:
    def test_render_checkpoint(self) -> None:
        block = ApprovalGate()
        fixtures = block.test_fixtures()
        inputs_with_config = {**fixtures["inputs"], "_config": fixtures["config"]}
        checkpoint = block.render_checkpoint(inputs_with_config)
        assert checkpoint == fixtures["expected_checkpoint"]

    def test_process_response_approve(self) -> None:
        block = ApprovalGate()
        fixtures = block.test_fixtures()
        human_input = fixtures["test_approve_response"]
        result = block.process_response(human_input, fixtures["inputs"], fixtures["config"])
        assert result == fixtures["expected_output"]

    def test_process_response_reject(self) -> None:
        block = ApprovalGate()
        fixtures = block.test_fixtures()
        human_input = fixtures["test_reject_response"]
        with pytest.raises(BlockExecutionError):
            block.process_response(human_input, fixtures["inputs"], fixtures["config"])


class TestMarkdownReport:
    def test_execute_output(self) -> None:
        block = MarkdownReport()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == fixtures["expected_output"]

    def test_declare_pipeline_inputs(self) -> None:
        block = MarkdownReport()
        assert block.declare_pipeline_inputs() == ["evaluation_set", "text_corpus"]

    def test_fixtures(self) -> None:
        block = MarkdownReport()
        fixtures = block.test_fixtures()
        assert isinstance(fixtures, dict)
        assert "config" in fixtures
        assert "inputs" in fixtures
        assert "expected_output" in fixtures


class TestJSONSink:
    def test_execute_returns_empty(self) -> None:
        block = JSONSink()
        fixtures = block.test_fixtures()
        result = _run(block.execute(fixtures["inputs"], fixtures["config"]))
        assert result == {}

    def test_sink_has_no_outputs(self) -> None:
        assert JSONSink().output_schemas == []
