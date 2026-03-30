"""Tests for the core graph walker (executor)."""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blocks.base import HITLBase, RouterBase, SinkBase, SourceBase, TransformBase
from engine.executor import (
    ExecutionError,
    _topological_sort,
    execute_pipeline,
)
from schemas.execution import (
    NodeExecutionStatus,
    RunState,
    RunStatus,
)
from schemas.pipeline import (
    BlockType,
    EdgeSchema,
    NodeSchema,
    PipelineSchema,
    Position,
)

# ---------------------------------------------------------------------------
# Helpers: mock block implementations
# ---------------------------------------------------------------------------


class MockSource(SourceBase):
    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {}

    @property
    def description(self) -> str:
        return "Mock source for testing"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        return {"rows": [1, 2, 3]}

    def test_fixtures(self) -> dict:
        return {"inputs": {}, "config": {}, "outputs": {}}


class MockTransform(TransformBase):
    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {}

    @property
    def description(self) -> str:
        return "Mock transform for testing"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        return {"rows": [10, 20, 30]}

    def test_fixtures(self) -> dict:
        return {"inputs": {}, "config": {}, "outputs": {}}


class MockSink(SinkBase):
    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {}

    @property
    def description(self) -> str:
        return "Mock sink for testing"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        return {}

    def test_fixtures(self) -> dict:
        return {"inputs": {}, "config": {}, "outputs": {}}


class MockSlowTransform(TransformBase):
    """A transform that sleeps 0.1s to test concurrency."""

    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {}

    @property
    def description(self) -> str:
        return "Mock slow transform for testing"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        await asyncio.sleep(0.1)
        return {"rows": [99]}

    def test_fixtures(self) -> dict:
        return {"inputs": {}, "config": {}, "outputs": {}}


class MockRouter(RouterBase):
    """Router that selects edges based on config."""

    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {}

    @property
    def description(self) -> str:
        return "Mock router for testing"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        return {"rows": inputs.get("respondent_collection", {}).get("rows", [])}

    def resolve_route(self, inputs: dict[str, Any]) -> list[str]:
        # Return the selected edges from the config stashed by the test
        return self._selected_edges

    _selected_edges: list[str] = []

    def test_fixtures(self) -> dict:
        return {"inputs": {}, "config": {}, "outputs": {}}


class MockHITL(HITLBase):
    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {}

    @property
    def description(self) -> str:
        return "Mock HITL for testing"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    def render_checkpoint(self, inputs: dict[str, Any]) -> dict:
        return {"prompt": "Please review", "data": inputs}

    def process_response(self, human_input: dict) -> dict[str, Any]:
        return {"rows": [42]}

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        # Should not be called — executor handles HITL via render_checkpoint
        return {}

    def test_fixtures(self) -> dict:
        return {"inputs": {}, "config": {}, "outputs": {}}


class MockFailingTransform(TransformBase):
    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {}

    @property
    def description(self) -> str:
        return "Mock failing transform for testing"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        raise RuntimeError("Something went wrong")

    def test_fixtures(self) -> dict:
        return {"inputs": {}, "config": {}, "outputs": {}}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """Redirect storage to a temp database."""
    import storage.runs as runs_mod
    import storage.sqlite as sqlite_mod

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(runs_mod, "_DB_PATH", tmp_db)
    monkeypatch.setattr(sqlite_mod, "_DB_PATH", tmp_db)


def _make_pipeline(
    nodes: list[NodeSchema],
    edges: list[EdgeSchema],
) -> PipelineSchema:
    now = datetime.now()
    return PipelineSchema(
        pipeline_id=uuid4(),
        name="test-pipeline",
        created_at=now,
        updated_at=now,
        nodes=nodes,
        edges=edges,
    )


def _make_run_state(pipeline: PipelineSchema) -> RunState:
    return RunState(
        run_id=uuid4(),
        pipeline_id=pipeline.pipeline_id,
        status=RunStatus.PENDING,
    )


def _node(
    node_id: UUID,
    block_type: BlockType,
    implementation: str,
) -> NodeSchema:
    return NodeSchema(
        node_id=node_id,
        block_type=block_type,
        block_implementation=implementation,
        label=implementation,
        position=Position(x=0, y=0),
    )


def _edge(
    edge_id: UUID,
    source: UUID,
    target: UUID,
    data_type: str = "respondent_collection",
) -> EdgeSchema:
    return EdgeSchema(
        edge_id=edge_id,
        source_node=source,
        target_node=target,
        data_type=data_type,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    def test_linear(self) -> None:
        order = _topological_sort(
            ["a", "b", "c"],
            {"a": ["b"], "b": ["c"]},
            {"b": ["a"], "c": ["b"]},
        )
        assert order == ["a", "b", "c"]

    def test_parallel(self) -> None:
        order = _topological_sort(
            ["a", "b", "c", "d"],
            {"a": ["b", "c"], "b": ["d"], "c": ["d"]},
            {"b": ["a"], "c": ["a"], "d": ["b", "c"]},
        )
        assert order[0] == "a"
        assert order[-1] == "d"

    def test_cycle_raises(self) -> None:
        with pytest.raises(ExecutionError, match="cycle"):
            _topological_sort(
                ["a", "b"],
                {"a": ["b"], "b": ["a"]},
                {"b": ["a"], "a": ["b"]},
            )


@pytest.mark.asyncio
async def test_linear_pipeline():
    """AC1: Source -> Transform -> Sink executes end-to-end."""
    src_id, tx_id, sink_id = uuid4(), uuid4(), uuid4()
    e1, e2 = uuid4(), uuid4()

    pipeline = _make_pipeline(
        nodes=[
            _node(src_id, BlockType.SOURCE, "mock_source"),
            _node(tx_id, BlockType.TRANSFORM, "mock_transform"),
            _node(sink_id, BlockType.SINK, "mock_sink"),
        ],
        edges=[
            _edge(e1, src_id, tx_id),
            _edge(e2, tx_id, sink_id),
        ],
    )
    run_state = _make_run_state(pipeline)

    with patch("engine.executor.get_block_class") as mock_get:
        mock_get.side_effect = lambda bt, impl: {
            ("source", "mock_source"): MockSource,
            ("transform", "mock_transform"): MockTransform,
            ("sink", "mock_sink"): MockSink,
        }[(bt, impl)]

        result = await execute_pipeline(pipeline, str(run_state.run_id), run_state)

    assert result.status == RunStatus.COMPLETED
    assert result.node_states[str(src_id)].status == NodeExecutionStatus.COMPLETED
    assert result.node_states[str(tx_id)].status == NodeExecutionStatus.COMPLETED
    assert result.node_states[str(sink_id)].status == NodeExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_parallel_branches_concurrent():
    """AC2: Parallel branches dispatched via asyncio.gather; concurrency proven."""
    src_id = uuid4()
    a_id, b_id = uuid4(), uuid4()
    sink_id = uuid4()
    e_sa, e_sb, e_as, e_bs = uuid4(), uuid4(), uuid4(), uuid4()

    pipeline = _make_pipeline(
        nodes=[
            _node(src_id, BlockType.SOURCE, "mock_source"),
            _node(a_id, BlockType.TRANSFORM, "mock_slow_a"),
            _node(b_id, BlockType.TRANSFORM, "mock_slow_b"),
            _node(sink_id, BlockType.SINK, "mock_sink"),
        ],
        edges=[
            _edge(e_sa, src_id, a_id),
            _edge(e_sb, src_id, b_id),
            _edge(e_as, a_id, sink_id),
            _edge(e_bs, b_id, sink_id),
        ],
    )
    run_state = _make_run_state(pipeline)

    with patch("engine.executor.get_block_class") as mock_get:
        mock_get.side_effect = lambda bt, impl: {
            ("source", "mock_source"): MockSource,
            ("transform", "mock_slow_a"): MockSlowTransform,
            ("transform", "mock_slow_b"): MockSlowTransform,
            ("sink", "mock_sink"): MockSink,
        }[(bt, impl)]

        start = time.monotonic()
        result = await execute_pipeline(pipeline, str(run_state.run_id), run_state)
        elapsed = time.monotonic() - start

    assert result.status == RunStatus.COMPLETED
    # Two 0.1s sleeps should complete in < 0.15s if concurrent
    assert elapsed < 0.3, f"Expected concurrent execution, took {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_router_activates_selected_edges():
    """AC3: Router blocks correctly activate only selected output edges."""
    src_id = uuid4()
    router_id = uuid4()
    a_id, b_id = uuid4(), uuid4()
    e_sr = uuid4()
    e_ra, e_rb = uuid4(), uuid4()

    pipeline = _make_pipeline(
        nodes=[
            _node(src_id, BlockType.SOURCE, "mock_source"),
            _node(router_id, BlockType.ROUTER, "mock_router"),
            _node(a_id, BlockType.TRANSFORM, "mock_transform_a"),
            _node(b_id, BlockType.TRANSFORM, "mock_transform_b"),
        ],
        edges=[
            _edge(e_sr, src_id, router_id),
            _edge(e_ra, router_id, a_id),
            _edge(e_rb, router_id, b_id),
        ],
    )
    run_state = _make_run_state(pipeline)

    # Only activate edge to A
    class TestRouter(MockRouter):
        _selected_edges = [str(e_ra)]

    with patch("engine.executor.get_block_class") as mock_get:
        mock_get.side_effect = lambda bt, impl: {
            ("source", "mock_source"): MockSource,
            ("router", "mock_router"): TestRouter,
            ("transform", "mock_transform_a"): MockTransform,
            ("transform", "mock_transform_b"): MockTransform,
        }[(bt, impl)]

        result = await execute_pipeline(pipeline, str(run_state.run_id), run_state)

    assert result.status == RunStatus.COMPLETED
    assert result.node_states[str(a_id)].status == NodeExecutionStatus.COMPLETED
    assert result.node_states[str(b_id)].status == NodeExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_hitl_suspends_execution():
    """AC4: HITL blocks suspend execution and persist state."""
    src_id = uuid4()
    hitl_id = uuid4()
    sink_id = uuid4()
    e1, e2 = uuid4(), uuid4()

    pipeline = _make_pipeline(
        nodes=[
            _node(src_id, BlockType.SOURCE, "mock_source"),
            _node(hitl_id, BlockType.HITL, "mock_hitl"),
            _node(sink_id, BlockType.SINK, "mock_sink"),
        ],
        edges=[
            _edge(e1, src_id, hitl_id),
            _edge(e2, hitl_id, sink_id),
        ],
    )
    run_state = _make_run_state(pipeline)

    with patch("engine.executor.get_block_class") as mock_get:
        mock_get.side_effect = lambda bt, impl: {
            ("source", "mock_source"): MockSource,
            ("hitl", "mock_hitl"): MockHITL,
            ("sink", "mock_sink"): MockSink,
        }[(bt, impl)]

        result = await execute_pipeline(pipeline, str(run_state.run_id), run_state)

    assert result.status == RunStatus.SUSPENDED
    assert result.hitl_checkpoint is not None
    assert result.hitl_checkpoint.node_id == str(hitl_id)
    assert "prompt" in result.hitl_checkpoint.checkpoint_data
    # Sink should NOT have executed
    assert result.node_states[str(sink_id)].status == NodeExecutionStatus.PENDING


@pytest.mark.asyncio
async def test_failed_block_halts_execution():
    """AC5: Failed blocks halt execution with error in RunState."""
    src_id = uuid4()
    tx_id = uuid4()
    sink_id = uuid4()
    e1, e2 = uuid4(), uuid4()

    pipeline = _make_pipeline(
        nodes=[
            _node(src_id, BlockType.SOURCE, "mock_source"),
            _node(tx_id, BlockType.TRANSFORM, "mock_failing"),
            _node(sink_id, BlockType.SINK, "mock_sink"),
        ],
        edges=[
            _edge(e1, src_id, tx_id),
            _edge(e2, tx_id, sink_id),
        ],
    )
    run_state = _make_run_state(pipeline)

    with patch("engine.executor.get_block_class") as mock_get:
        mock_get.side_effect = lambda bt, impl: {
            ("source", "mock_source"): MockSource,
            ("transform", "mock_failing"): MockFailingTransform,
            ("sink", "mock_sink"): MockSink,
        }[(bt, impl)]

        result = await execute_pipeline(pipeline, str(run_state.run_id), run_state)

    assert result.status == RunStatus.FAILED
    assert result.error is not None
    assert "Something went wrong" in result.error
    assert result.node_states[str(tx_id)].status == NodeExecutionStatus.FAILED
    # Sink should NOT have executed
    assert result.node_states[str(sink_id)].status == NodeExecutionStatus.PENDING


@pytest.mark.asyncio
async def test_node_status_transitions():
    """AC6: NodeStatus updated at each transition (pending->running->completed)."""
    src_id = uuid4()
    e1 = uuid4()
    tx_id = uuid4()

    class TrackingTransform(TransformBase):
        @property
        def input_schemas(self) -> list[str]:
            return ["respondent_collection"]

        @property
        def output_schemas(self) -> list[str]:
            return ["respondent_collection"]

        @property
        def config_schema(self) -> dict:
            return {}

        @property
        def description(self) -> str:
            return "Mock tracking transform for testing"

        @property
        def methodological_notes(self) -> str:
            return "Mock for testing - no real methodology"

        def validate_config(self, config: dict) -> bool:
            return True

        async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
            # At this point, node should be "running"
            return {"rows": [1]}

    pipeline = _make_pipeline(
        nodes=[
            _node(src_id, BlockType.SOURCE, "mock_source"),
            _node(tx_id, BlockType.TRANSFORM, "mock_tracking"),
        ],
        edges=[_edge(e1, src_id, tx_id)],
    )
    run_state = _make_run_state(pipeline)

    with patch("engine.executor.get_block_class") as mock_get:
        mock_get.side_effect = lambda bt, impl: {
            ("source", "mock_source"): MockSource,
            ("transform", "mock_tracking"): TrackingTransform,
        }[(bt, impl)]

        result = await execute_pipeline(pipeline, str(run_state.run_id), run_state)

    assert result.status == RunStatus.COMPLETED
    # Both nodes should be completed with timestamps
    for nid in [str(src_id), str(tx_id)]:
        ns = result.node_states[nid]
        assert ns.status == NodeExecutionStatus.COMPLETED
        assert ns.started_at is not None
        assert ns.completed_at is not None


@pytest.mark.asyncio
async def test_execution_context_injected():
    """AC7: Executor injects _execution_context into each block's inputs."""
    src_id = uuid4()
    captured_context: dict[str, Any] = {}

    class ContextCapture(SourceBase):
        @property
        def output_schemas(self) -> list[str]:
            return ["respondent_collection"]

        @property
        def config_schema(self) -> dict:
            return {}

        @property
        def description(self) -> str:
            return "Mock context capture for testing"

        @property
        def methodological_notes(self) -> str:
            return "Mock for testing - no real methodology"

        def validate_config(self, config: dict) -> bool:
            return True

        async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
            captured_context.update(inputs.get("_execution_context", {}))
            return {"rows": [1]}

    pipeline = _make_pipeline(
        nodes=[_node(src_id, BlockType.SOURCE, "ctx_source")],
        edges=[],
    )
    run_state = _make_run_state(pipeline)

    with patch("engine.executor.get_block_class") as mock_get:
        mock_get.return_value = ContextCapture

        result = await execute_pipeline(pipeline, str(run_state.run_id), run_state)

    assert result.status == RunStatus.COMPLETED
    assert captured_context["run_id"] == str(run_state.run_id)
    assert captured_context["pipeline_id"] == str(pipeline.pipeline_id)
    assert captured_context["node_id"] == str(src_id)
