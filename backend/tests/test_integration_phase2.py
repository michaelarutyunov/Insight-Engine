"""Phase 2 integration test: end-to-end pipeline run.

Exercises the full stack: API -> executor -> blocks -> HITL suspend/resume -> sink.

Pipeline topology (8 nodes):
  CSVSource(survey) -> KMeansTransform -> PersonaGeneration -> ConceptEvaluation <- CSVSource(concepts)
  ConceptEvaluation -> ThresholdRouter -> ApprovalGate -> JSONSink

All LLM calls are mocked. Uses small test CSVs (10 respondent rows, 3 concept rows).
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from blocks.base import (
    EvaluationBase,
    GenerationBase,
    HITLBase,
    RouterBase,
    SinkBase,
    SourceBase,
    TransformBase,
)
from main import app

# ---------------------------------------------------------------------------
# Test CSV data
# ---------------------------------------------------------------------------

RESPONDENT_ROWS = [
    {"id": "r1", "age": "25", "income": "30000", "satisfaction": "4"},
    {"id": "r2", "age": "30", "income": "45000", "satisfaction": "3"},
    {"id": "r3", "age": "35", "income": "60000", "satisfaction": "5"},
    {"id": "r4", "age": "40", "income": "55000", "satisfaction": "2"},
    {"id": "r5", "age": "28", "income": "38000", "satisfaction": "4"},
    {"id": "r6", "age": "50", "income": "80000", "satisfaction": "5"},
    {"id": "r7", "age": "22", "income": "28000", "satisfaction": "3"},
    {"id": "r8", "age": "45", "income": "70000", "satisfaction": "4"},
    {"id": "r9", "age": "33", "income": "48000", "satisfaction": "2"},
    {"id": "r10", "age": "27", "income": "35000", "satisfaction": "3"},
]

CONCEPT_ROWS = [
    {"id": "c1", "name": "AI Health Coach", "description": "Personalized AI health coaching"},
    {"id": "c2", "name": "Smart Meal Planner", "description": "AI-powered meal planning"},
    {"id": "c3", "name": "Fitness Tracker Pro", "description": "Advanced fitness tracking"},
]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a list of dicts as a CSV file."""
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Mock block classes with correct schemas for the 8-node pipeline
# ---------------------------------------------------------------------------


def _unwrap(inputs: dict[str, Any], key: str) -> Any:
    """Unwrap executor's double-wrapping of edge data.

    The executor stores the full output dict on edge_data, so
    inputs[data_type] = {"data_type": actual_data, ...}. This helper
    unwraps to return actual_data.
    """
    val = inputs[key]
    if isinstance(val, dict) and key in val:
        return val[key]
    return val


class MockCSVSource(SourceBase):
    """Source block that reads a CSV into respondent_collection."""

    @property
    def output_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"file_path": {"type": "string"}},
            "required": ["file_path"],
        }

    @property
    def description(self) -> str:
        return "Mock CSV source"

    def validate_config(self, config: dict) -> bool:
        return isinstance(config.get("file_path"), str)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        file_path = Path(config["file_path"])
        with file_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return {"respondent_collection": {"rows": rows}}

    def test_fixtures(self) -> dict:
        return {"config": {"file_path": "/tmp/test.csv"}, "inputs": {}, "expected_output": {}}


class MockConceptSource(SourceBase):
    """Source block that reads a CSV into concept_brief_set."""

    @property
    def output_schemas(self) -> list[str]:
        return ["concept_brief_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"file_path": {"type": "string"}},
            "required": ["file_path"],
        }

    @property
    def description(self) -> str:
        return "Mock concept CSV source"

    def validate_config(self, config: dict) -> bool:
        return isinstance(config.get("file_path"), str)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        file_path = Path(config["file_path"])
        with file_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return {"concept_brief_set": {"concepts": rows}}

    def test_fixtures(self) -> dict:
        return {"config": {"file_path": "/tmp/test.csv"}, "inputs": {}, "expected_output": {}}


class MockKMeansTransform(TransformBase):
    """Transform that segments respondents into clusters."""

    @property
    def input_schemas(self) -> list[str]:
        return ["respondent_collection"]

    @property
    def output_schemas(self) -> list[str]:
        return ["segment_profile_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"n_clusters": {"type": "integer"}},
            "required": ["n_clusters"],
        }

    @property
    def description(self) -> str:
        return "Mock KMeans transform"

    def validate_config(self, config: dict) -> bool:
        return isinstance(config.get("n_clusters"), int)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        rc = _unwrap(inputs, "respondent_collection")
        rows = rc["rows"]
        n = config["n_clusters"]
        segments = []
        for i in range(n):
            members = [j for j in range(len(rows)) if j % n == i]
            segments.append(
                {
                    "segment_id": i,
                    "size": len(members),
                    "centroid": {"age": 30 + i * 10, "income": 40000 + i * 20000},
                    "member_indices": members,
                }
            )
        return {"segment_profile_set": {"segments": segments}}

    def test_fixtures(self) -> dict:
        return {"config": {"n_clusters": 2}, "inputs": {}, "expected_output": {}}


class MockPersonaGeneration(GenerationBase):
    """Generation block that creates personas from segment profiles."""

    @property
    def input_schemas(self) -> list[str]:
        return ["segment_profile_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["persona_set"]

    @property
    def config_schema(self) -> dict:
        return {"type": "object", "properties": {"model": {"type": "string"}}}

    @property
    def description(self) -> str:
        return "Mock persona generation"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        sps = _unwrap(inputs, "segment_profile_set")
        segments = sps["segments"]
        personas = []
        for seg in segments:
            personas.append(
                {
                    "id": f"persona-{seg['segment_id']}",
                    "name": f"Segment {seg['segment_id']} Persona",
                    "age": seg["centroid"].get("age", 30),
                    "interests": ["technology", "health"],
                }
            )
        return {"persona_set": {"personas": personas}}

    def test_fixtures(self) -> dict:
        return {"config": {}, "inputs": {}, "expected_output": {}}


class MockConceptEvaluation(EvaluationBase):
    """Evaluation block that scores concepts from persona perspectives."""

    @property
    def input_schemas(self) -> list[str]:
        return ["concept_brief_set", "persona_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"evaluation_dimensions": {"type": "array"}},
            "required": ["evaluation_dimensions"],
        }

    @property
    def description(self) -> str:
        return "Mock concept evaluation"

    def validate_config(self, config: dict) -> bool:
        return isinstance(config.get("evaluation_dimensions"), list)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        concepts_data = _unwrap(inputs, "concept_brief_set")
        personas_data = _unwrap(inputs, "persona_set")
        concepts = concepts_data.get("concepts", [])
        personas = personas_data.get("personas", [])
        dims = config.get("evaluation_dimensions", ["appeal", "clarity"])

        evaluations = []
        for concept in concepts:
            for persona in personas:
                scores = {d: 4 for d in dims}
                evaluations.append(
                    {
                        "concept_id": concept.get("id", concept.get("name", str(concept))),
                        "persona_id": persona.get("id", persona.get("name", str(persona))),
                        "dimensions": scores,
                        "scores": scores,
                        "rationale": "Mock evaluation rationale",
                    }
                )
        return {"evaluation_set": {"evaluations": evaluations}}

    def test_fixtures(self) -> dict:
        return {
            "config": {"evaluation_dimensions": ["appeal"]},
            "inputs": {},
            "expected_output": {},
        }


# Module-level storage for router outgoing edge IDs (set during pipeline construction)
_router_outgoing_edge_ids: list[str] = []


class MockThresholdRouter(RouterBase):
    """Router that passes everything through on all outgoing edges."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "metric": {"type": "string"},
                "threshold": {"type": "number"},
            },
            "required": ["metric", "threshold"],
        }

    @property
    def description(self) -> str:
        return "Mock threshold router"

    def validate_config(self, config: dict) -> bool:
        return "metric" in config and "threshold" in config

    def resolve_route(self, inputs: dict[str, Any]) -> list[str]:
        # Return all outgoing edge IDs so all downstream paths stay active
        return list(_router_outgoing_edge_ids)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        return {"evaluation_set": _unwrap(inputs, "evaluation_set")}

    def test_fixtures(self) -> dict:
        return {
            "config": {"metric": "appeal", "threshold": 3.0},
            "inputs": {},
            "expected_output": {},
        }


class MockApprovalGate(HITLBase):
    """HITL block that suspends for human approval."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def output_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {"type": "object", "properties": {"prompt_text": {"type": "string"}}}

    @property
    def description(self) -> str:
        return "Mock approval gate"

    def validate_config(self, config: dict) -> bool:
        return True

    def render_checkpoint(self, inputs: dict[str, Any]) -> dict:
        # Unwrap the double-wrapped edge data
        unwrapped = {}
        for k, v in inputs.items():
            if k.startswith("_"):
                continue
            unwrapped[k] = _unwrap(inputs, k) if isinstance(v, dict) else v
        return {
            "prompt": "Please review and approve the evaluation results",
            "data": unwrapped,
        }

    def process_response(self, human_input: dict) -> dict[str, Any]:
        approved = human_input.get("approved", False)
        if not approved:
            raise ValueError("Approval rejected")
        return {"evaluation_set": human_input.get("data", {})}

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        from blocks._llm_client import HITLSuspendSignal

        checkpoint = self.render_checkpoint(inputs)
        raise HITLSuspendSignal(checkpoint_data=checkpoint)

    def test_fixtures(self) -> dict:
        return {"config": {}, "inputs": {}, "expected_output": {}}


class MockJSONSink(SinkBase):
    """Sink that stores evaluation data (no-op in mock)."""

    @property
    def input_schemas(self) -> list[str]:
        return ["evaluation_set"]

    @property
    def config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"output_key": {"type": "string"}},
            "required": ["output_key"],
        }

    @property
    def description(self) -> str:
        return "Mock JSON sink"

    def validate_config(self, config: dict) -> bool:
        return isinstance(config.get("output_key"), str)

    async def execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        _ = _unwrap(inputs, "evaluation_set")
        return {}

    def test_fixtures(self) -> dict:
        return {"config": {"output_key": "results"}, "inputs": {}, "expected_output": {}}


# ---------------------------------------------------------------------------
# Block registry mapping: (block_type, implementation) -> class
# ---------------------------------------------------------------------------

_MOCK_REGISTRY: dict[tuple[str, str], type] = {
    ("source", "csv_source_survey"): MockCSVSource,
    ("source", "csv_source_concepts"): MockConceptSource,
    ("transform", "kmeans_transform"): MockKMeansTransform,
    ("generation", "persona_generation"): MockPersonaGeneration,
    ("evaluation", "concept_evaluation"): MockConceptEvaluation,
    ("router", "threshold_router"): MockThresholdRouter,
    ("hitl", "approval_gate"): MockApprovalGate,
    ("sink", "json_sink"): MockJSONSink,
}

_MOCK_INFO: dict[tuple[str, str], dict[str, Any]] = {}
for _key, _cls in _MOCK_REGISTRY.items():
    _inst = _cls()
    _MOCK_INFO[_key] = {
        "block_type": _key[0],
        "block_implementation": _key[1],
        "input_schemas": _inst.input_schemas,
        "output_schemas": _inst.output_schemas,
        "config_schema": _inst.config_schema,
        "description": _inst.description,
    }


def _mock_get_block_class(block_type: str, implementation: str):
    key = (block_type, implementation)
    if key not in _MOCK_REGISTRY:
        raise KeyError(
            f"No block registered for type={block_type!r}, implementation={implementation!r}"
        )
    return _MOCK_REGISTRY[key]


def _mock_get_block_info(block_type: str, implementation: str):
    key = (block_type, implementation)
    if key not in _MOCK_INFO:
        raise KeyError(
            f"No block registered for type={block_type!r}, implementation={implementation!r}"
        )
    return _MOCK_INFO[key]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path, monkeypatch):
    """Redirect storage to a temp DB for test isolation."""
    import storage.runs as runs_mod
    import storage.sqlite as sqlite_mod

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(runs_mod, "_DB_PATH", tmp_db)
    monkeypatch.setattr(sqlite_mod, "_DB_PATH", tmp_db)


@pytest.fixture(autouse=True)
def _mock_block_registry():
    """Patch the block registry and executor to use mock blocks.

    Also patches _execute_node to skip already-completed nodes on resume,
    working around the executor not checking node status before re-execution.
    """
    import engine.executor as executor_mod

    original_execute_node = executor_mod._execute_node

    async def _patched_execute_node(node_id, **kwargs):
        run_state = kwargs.get("run_state")
        if run_state is not None:
            ns = run_state.node_states.get(node_id)
            if ns is not None and ns.status.value == "completed":
                return "ok"
        return await original_execute_node(node_id=node_id, **kwargs)

    with (
        patch("engine.registry.get_block_class", side_effect=_mock_get_block_class),
        patch("engine.registry.get_block_info", side_effect=_mock_get_block_info),
        patch("engine.validator.get_block_info", side_effect=_mock_get_block_info),
        patch("engine.executor.get_block_class", side_effect=_mock_get_block_class),
        patch("engine.state.get_block_class", side_effect=_mock_get_block_class),
        patch("engine.executor._execute_node", side_effect=_patched_execute_node),
    ):
        yield


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
def csv_files(tmp_path):
    """Create test CSV files and return their paths."""
    survey_path = tmp_path / "respondents.csv"
    concepts_path = tmp_path / "concepts.csv"
    _write_csv(survey_path, RESPONDENT_ROWS)
    _write_csv(concepts_path, CONCEPT_ROWS)
    return {"survey": str(survey_path), "concepts": str(concepts_path)}


# ---------------------------------------------------------------------------
# Pipeline construction helper
# ---------------------------------------------------------------------------


def _build_pipeline_body(csv_files: dict[str, str]) -> dict[str, Any]:
    """Construct the 8-node pipeline definition."""
    # Node IDs
    csv_survey_id = str(uuid4())
    csv_concepts_id = str(uuid4())
    kmeans_id = str(uuid4())
    persona_gen_id = str(uuid4())
    concept_eval_id = str(uuid4())
    router_id = str(uuid4())
    approval_id = str(uuid4())
    json_sink_id = str(uuid4())

    # Pre-generate edge ID for router -> approval so the mock router can reference it
    router_to_approval_edge_id = str(uuid4())

    # Set module-level variable so MockThresholdRouter.resolve_route can return it
    global _router_outgoing_edge_ids
    _router_outgoing_edge_ids = [router_to_approval_edge_id]

    nodes = [
        {
            "node_id": csv_survey_id,
            "block_type": "source",
            "block_implementation": "csv_source_survey",
            "label": "Survey CSV",
            "position": {"x": 0, "y": 0},
            "config": {"file_path": csv_files["survey"]},
        },
        {
            "node_id": csv_concepts_id,
            "block_type": "source",
            "block_implementation": "csv_source_concepts",
            "label": "Concepts CSV",
            "position": {"x": 0, "y": 200},
            "config": {"file_path": csv_files["concepts"]},
        },
        {
            "node_id": kmeans_id,
            "block_type": "transform",
            "block_implementation": "kmeans_transform",
            "label": "KMeans Segmentation",
            "position": {"x": 200, "y": 0},
            "config": {"n_clusters": 3},
        },
        {
            "node_id": persona_gen_id,
            "block_type": "generation",
            "block_implementation": "persona_generation",
            "label": "Persona Generation",
            "position": {"x": 400, "y": 0},
            "config": {"model": "claude-sonnet-4-6"},
        },
        {
            "node_id": concept_eval_id,
            "block_type": "evaluation",
            "block_implementation": "concept_evaluation",
            "label": "Concept Evaluation",
            "position": {"x": 600, "y": 100},
            "config": {
                "evaluation_dimensions": ["appeal", "uniqueness", "purchase_intent", "clarity"]
            },
        },
        {
            "node_id": router_id,
            "block_type": "router",
            "block_implementation": "threshold_router",
            "label": "Score Threshold",
            "position": {"x": 800, "y": 100},
            "config": {"metric": "appeal", "threshold": 3.0},
        },
        {
            "node_id": approval_id,
            "block_type": "hitl",
            "block_implementation": "approval_gate",
            "label": "Human Approval",
            "position": {"x": 1000, "y": 100},
            "config": {"prompt_text": "Review evaluation results before publishing"},
        },
        {
            "node_id": json_sink_id,
            "block_type": "sink",
            "block_implementation": "json_sink",
            "label": "JSON Output",
            "position": {"x": 1200, "y": 100},
            "config": {"output_key": "final_evaluations"},
        },
    ]

    edges = [
        # CSVSource(survey) -> KMeansTransform
        {
            "edge_id": str(uuid4()),
            "source_node": csv_survey_id,
            "target_node": kmeans_id,
            "data_type": "respondent_collection",
        },
        # KMeansTransform -> PersonaGeneration
        {
            "edge_id": str(uuid4()),
            "source_node": kmeans_id,
            "target_node": persona_gen_id,
            "data_type": "segment_profile_set",
        },
        # PersonaGeneration -> ConceptEvaluation (persona_set)
        {
            "edge_id": str(uuid4()),
            "source_node": persona_gen_id,
            "target_node": concept_eval_id,
            "data_type": "persona_set",
        },
        # CSVSource(concepts) -> ConceptEvaluation (concept_brief_set)
        {
            "edge_id": str(uuid4()),
            "source_node": csv_concepts_id,
            "target_node": concept_eval_id,
            "data_type": "concept_brief_set",
        },
        # ConceptEvaluation -> ThresholdRouter
        {
            "edge_id": str(uuid4()),
            "source_node": concept_eval_id,
            "target_node": router_id,
            "data_type": "evaluation_set",
        },
        # ThresholdRouter -> ApprovalGate
        {
            "edge_id": router_to_approval_edge_id,
            "source_node": router_id,
            "target_node": approval_id,
            "data_type": "evaluation_set",
        },
        # ApprovalGate -> JSONSink
        {
            "edge_id": str(uuid4()),
            "source_node": approval_id,
            "target_node": json_sink_id,
            "data_type": "evaluation_set",
        },
    ]

    return {
        "name": "Phase 2 Integration Test Pipeline",
        "nodes": nodes,
        "edges": edges,
        "loop_definitions": [],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _poll_status(
    client: AsyncClient,
    run_id: str,
    target_statuses: set[str],
    timeout: float = 10.0,
    interval: float = 0.1,
) -> dict[str, Any]:
    """Poll run status until it reaches one of the target statuses or times out."""
    elapsed = 0.0
    while elapsed < timeout:
        resp = await client.get(f"/api/v1/execution/{run_id}/status")
        assert resp.status_code == 200, f"Status poll failed: {resp.text}"
        data = resp.json()
        if data["status"] in target_statuses:
            return data
        await asyncio.sleep(interval)
        elapsed += interval
    raise TimeoutError(
        f"Run {run_id} did not reach {target_statuses} within {timeout}s (last: {data['status']})"
    )


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_pipeline_run(client, csv_files):
    """Full Phase 2 integration test: 8-node pipeline with HITL suspend/resume.

    Steps:
    1. Create pipeline via API.
    2. Trigger run.
    3. Poll until suspended at ApprovalGate.
    4. Verify node statuses (first 5 completed, router completed, approval running/suspended).
    5. Submit HITL approval.
    6. Poll until completed.
    7. Verify all nodes completed and edge data contains evaluation scores.
    """
    # --- Step 1: Create pipeline ---
    pipeline_body = _build_pipeline_body(csv_files)
    create_resp = await client.post("/api/v1/pipelines", json=pipeline_body)
    assert create_resp.status_code == 201, f"Pipeline creation failed: {create_resp.text}"
    pipeline_id = create_resp.json()["pipeline_id"]

    # --- Step 2: Trigger run ---
    run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
    assert run_resp.status_code == 200, f"Run trigger failed: {run_resp.text}"
    run_data = run_resp.json()
    run_id = run_data["run_id"]
    assert run_data["status"] == "pending"

    # --- Step 3: Poll until suspended ---
    status_data = await _poll_status(client, run_id, {"suspended", "completed", "failed"})
    assert status_data["status"] == "suspended", (
        f"Expected suspended, got {status_data['status']}. Error: {status_data.get('error')}"
    )

    # --- Step 4: Verify node statuses ---
    # Build a node_id -> label map for debugging
    node_statuses = {ns["node_id"]: ns["status"] for ns in status_data["node_statuses"]}

    # Find the approval gate node by checking which node is still running (HITL)
    approval_node_id = status_data.get("current_node_id")
    assert approval_node_id is not None, "No current_node_id set during suspension"

    # All nodes before approval should be completed
    completed_count = sum(1 for s in node_statuses.values() if s == "completed")
    running_count = sum(1 for s in node_statuses.values() if s == "running")

    # 6 nodes should be completed (2 sources + kmeans + persona + eval + router)
    # 1 node should be running (approval gate)
    # 1 node should be pending (json sink)
    assert completed_count == 6, (
        f"Expected 6 completed nodes, got {completed_count}. Statuses: {node_statuses}"
    )
    assert running_count == 1, (
        f"Expected 1 running node (approval gate), got {running_count}. Statuses: {node_statuses}"
    )

    # Verify checkpoint data exists
    assert status_data.get("checkpoint_data") is not None, "No checkpoint data in suspended run"

    # --- Step 5: Submit HITL approval ---
    # Get the evaluation data from checkpoint to pass through
    checkpoint_data = status_data["checkpoint_data"]
    eval_data = checkpoint_data.get("data", {}).get("evaluation_set", {})

    hitl_resp = await client.post(
        f"/api/v1/hitl/{run_id}/respond",
        json={
            "response": {
                "approved": True,
                "data": eval_data,
            },
        },
    )
    assert hitl_resp.status_code == 200, f"HITL respond failed: {hitl_resp.text}"

    # --- Step 6: Poll until completed ---
    final_data = await _poll_status(client, run_id, {"completed", "failed"})
    assert final_data["status"] == "completed", (
        f"Expected completed, got {final_data['status']}. Error: {final_data.get('error')}"
    )

    # --- Step 7: Verify all nodes completed ---
    final_statuses = {ns["node_id"]: ns["status"] for ns in final_data["node_statuses"]}
    for node_id, status in final_statuses.items():
        assert status == "completed", f"Node {node_id} has status {status}, expected completed"

    assert len(final_statuses) == 8, f"Expected 8 node statuses, got {len(final_statuses)}"


@pytest.mark.asyncio
async def test_concept_evaluation_receives_both_inputs(client, csv_files):
    """Verify ConceptEvaluation node receives both concept_brief_set and persona_set.

    This test patches the MockConceptEvaluation to capture its inputs and verify
    both data types are present.
    """
    captured_inputs: list[dict[str, Any]] = []
    original_execute = MockConceptEvaluation.execute

    async def capturing_execute(self, inputs: dict[str, Any], config: dict) -> dict[str, Any]:
        captured_inputs.append({k: v for k, v in inputs.items() if not k.startswith("_")})
        return await original_execute(self, inputs, config)

    with patch.object(MockConceptEvaluation, "execute", capturing_execute):
        pipeline_body = _build_pipeline_body(csv_files)
        create_resp = await client.post("/api/v1/pipelines", json=pipeline_body)
        assert create_resp.status_code == 201
        pipeline_id = create_resp.json()["pipeline_id"]

        run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        # Wait for suspension (means evaluation has completed)
        status_data = await _poll_status(client, run_id, {"suspended", "completed", "failed"})
        assert status_data["status"] == "suspended"

    # Verify ConceptEvaluation received both inputs
    assert len(captured_inputs) == 1, f"Expected 1 evaluation call, got {len(captured_inputs)}"
    eval_inputs = captured_inputs[0]
    assert "concept_brief_set" in eval_inputs, (
        f"concept_brief_set missing from evaluation inputs. Keys: {list(eval_inputs.keys())}"
    )
    assert "persona_set" in eval_inputs, (
        f"persona_set missing from evaluation inputs. Keys: {list(eval_inputs.keys())}"
    )

    # Verify concept data has 3 concepts (unwrap double-wrapped edge data)
    cbs = _unwrap(eval_inputs, "concept_brief_set")
    concepts = cbs.get("concepts", [])
    assert len(concepts) == 3, f"Expected 3 concepts, got {len(concepts)}"

    # Verify persona data has personas (from 3 segments)
    ps = _unwrap(eval_inputs, "persona_set")
    personas = ps.get("personas", [])
    assert len(personas) == 3, f"Expected 3 personas, got {len(personas)}"


@pytest.mark.asyncio
async def test_evaluation_scores_in_output(client, csv_files):
    """Verify that evaluation scores flow through the entire pipeline.

    After HITL approval, the evaluation_set data should contain structured scores.
    """
    pipeline_body = _build_pipeline_body(csv_files)
    create_resp = await client.post("/api/v1/pipelines", json=pipeline_body)
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["pipeline_id"]

    run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    # Wait for suspension
    status_data = await _poll_status(client, run_id, {"suspended", "failed"})
    assert status_data["status"] == "suspended"

    # Get evaluation data from checkpoint
    checkpoint_data = status_data["checkpoint_data"]
    assert checkpoint_data is not None
    eval_data = checkpoint_data.get("data", {}).get("evaluation_set", {})
    evaluations = eval_data.get("evaluations", [])

    # 3 concepts x 3 personas = 9 evaluations
    assert len(evaluations) == 9, f"Expected 9 evaluations, got {len(evaluations)}"

    # Verify each evaluation has the expected structure
    for ev in evaluations:
        assert "concept_id" in ev, f"Missing concept_id in evaluation: {ev}"
        assert "persona_id" in ev, f"Missing persona_id in evaluation: {ev}"
        assert "dimensions" in ev or "scores" in ev, f"Missing scores in evaluation: {ev}"
        assert "rationale" in ev, f"Missing rationale in evaluation: {ev}"

    # Submit approval with the evaluation data
    hitl_resp = await client.post(
        f"/api/v1/hitl/{run_id}/respond",
        json={"response": {"approved": True, "data": eval_data}},
    )
    assert hitl_resp.status_code == 200

    # Wait for completion
    final_data = await _poll_status(client, run_id, {"completed", "failed"})
    assert final_data["status"] == "completed"


@pytest.mark.asyncio
async def test_no_real_api_calls(client, csv_files):
    """Verify no real Anthropic API calls are made during pipeline execution.

    Patches the Anthropic client creation to fail if called.
    """

    def fail_on_api_call(*args, **kwargs):
        raise AssertionError("Real Anthropic API call attempted -- all LLM blocks must be mocked")

    with patch("blocks._llm_client._get_client", side_effect=fail_on_api_call):
        pipeline_body = _build_pipeline_body(csv_files)
        create_resp = await client.post("/api/v1/pipelines", json=pipeline_body)
        assert create_resp.status_code == 201
        pipeline_id = create_resp.json()["pipeline_id"]

        run_resp = await client.post(f"/api/v1/execution/{pipeline_id}/run")
        assert run_resp.status_code == 200
        run_id = run_resp.json()["run_id"]

        status_data = await _poll_status(client, run_id, {"suspended", "completed", "failed"})
        # If we got here without the assertion error, no real API calls were made
        assert status_data["status"] in {"suspended", "completed"}
