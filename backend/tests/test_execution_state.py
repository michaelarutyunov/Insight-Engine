"""Tests for execution state models and run storage."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.execution import (
    HITLCheckpoint,
    NodeExecutionStatus,
    NodeState,
    RunResponse,
    RunState,
    RunStatus,
    RunStatusResponse,
)
from storage.runs import create_run, get_run, list_runs_for_pipeline, update_run


class TestRunStatusEnum:
    def test_all_statuses(self) -> None:
        assert RunStatus.PENDING == "pending"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.SUSPENDED == "suspended"
        assert RunStatus.COMPLETED == "completed"
        assert RunStatus.FAILED == "failed"


class TestNodeState:
    def test_defaults(self) -> None:
        ns = NodeState(node_id="node-1")
        assert ns.status == NodeExecutionStatus.PENDING
        assert ns.started_at is None
        assert ns.error is None

    def test_with_values(self) -> None:
        from datetime import datetime

        now = datetime.now()
        ns = NodeState(
            node_id="node-1",
            status=NodeExecutionStatus.COMPLETED,
            started_at=now,
            completed_at=now,
        )
        assert ns.status == "completed"


class TestRunState:
    def test_defaults(self) -> None:
        run = RunState(run_id=uuid4(), pipeline_id=uuid4())
        assert run.status == RunStatus.PENDING
        assert run.current_node_id is None
        assert run.node_states == {}
        assert run.edge_data == {}
        assert run.loop_counters == {}
        assert run.hitl_checkpoint is None
        assert run.error is None

    def test_serialization_roundtrip(self) -> None:
        run = RunState(
            run_id=uuid4(),
            pipeline_id=uuid4(),
            status=RunStatus.RUNNING,
            current_node_id="node-1",
            node_states={"node-1": NodeState(node_id="node-1", status=NodeExecutionStatus.RUNNING)},
            edge_data={"edge-1": {"key": "value"}},
            loop_counters={"loop-1": 3},
        )
        json_str = run.model_dump_json()
        restored = RunState.model_validate_json(json_str)
        assert restored.run_id == run.run_id
        assert restored.status == RunStatus.RUNNING
        assert restored.current_node_id == "node-1"
        assert "node-1" in restored.node_states
        assert restored.loop_counters["loop-1"] == 3

    def test_hitl_checkpoint(self) -> None:
        run = RunState(
            run_id=uuid4(),
            pipeline_id=uuid4(),
            status=RunStatus.SUSPENDED,
            hitl_checkpoint=HITLCheckpoint(
                node_id="hitl-1",
                checkpoint_data={"prompt": "Review this data"},
            ),
        )
        assert run.hitl_checkpoint is not None
        assert run.hitl_checkpoint.node_id == "hitl-1"


class TestRunResponse:
    def test_create(self) -> None:
        r = RunResponse(run_id=uuid4(), status=RunStatus.RUNNING)
        assert r.status == "running"


class TestRunStatusResponse:
    def test_create(self) -> None:
        r = RunStatusResponse(run_id=uuid4(), pipeline_id=uuid4(), status=RunStatus.PENDING)
        assert r.node_states == {}


# ---------------------------------------------------------------------------
# Storage tests (use the real SQLite db, isolated per test)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """Redirect both storage modules to a temp database."""
    import storage.runs as runs_mod
    import storage.sqlite as sqlite_mod

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(runs_mod, "_DB_PATH", tmp_db)
    monkeypatch.setattr(sqlite_mod, "_DB_PATH", tmp_db)


@pytest.mark.asyncio
async def test_create_and_get_run():
    pipeline_id = uuid4()
    run = await create_run(pipeline_id)
    assert run.pipeline_id == pipeline_id
    assert run.status == RunStatus.PENDING

    fetched = await get_run(run.run_id)
    assert fetched is not None
    assert fetched.run_id == run.run_id
    assert fetched.pipeline_id == pipeline_id


@pytest.mark.asyncio
async def test_get_nonexistent_run():
    result = await get_run(uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_update_run():
    pipeline_id = uuid4()
    run = await create_run(pipeline_id)

    run.status = RunStatus.RUNNING
    run.current_node_id = "node-1"
    run = await update_run(run)

    fetched = await get_run(run.run_id)
    assert fetched is not None
    assert fetched.status == RunStatus.RUNNING
    assert fetched.current_node_id == "node-1"


@pytest.mark.asyncio
async def test_list_runs_for_pipeline():
    pipeline_id = uuid4()
    await create_run(pipeline_id)
    await create_run(pipeline_id)

    runs = await list_runs_for_pipeline(pipeline_id)
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_list_runs_empty():
    runs = await list_runs_for_pipeline(uuid4())
    assert runs == []


@pytest.mark.asyncio
async def test_roundtrip_with_node_states():
    pipeline_id = uuid4()
    run = await create_run(pipeline_id)

    run.status = RunStatus.SUSPENDED
    run.node_states = {
        "src-1": NodeState(node_id="src-1", status=NodeExecutionStatus.COMPLETED),
        "hitl-1": NodeState(node_id="hitl-1", status=NodeExecutionStatus.RUNNING),
    }
    run.hitl_checkpoint = HITLCheckpoint(node_id="hitl-1", checkpoint_data={"prompt": "Approve?"})
    run.loop_counters = {"loop-1": 2}
    run.edge_data = {"e1": {"type": "respondent_collection", "data": [1, 2, 3]}}

    await update_run(run)

    fetched = await get_run(run.run_id)
    assert fetched is not None
    assert fetched.status == RunStatus.SUSPENDED
    assert "src-1" in fetched.node_states
    assert fetched.node_states["src-1"].status == NodeExecutionStatus.COMPLETED
    assert fetched.hitl_checkpoint is not None
    assert fetched.loop_counters == {"loop-1": 2}
    assert "e1" in fetched.edge_data
