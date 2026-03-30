"""Tests for the CLI (insights) — uses httpx mock to avoid live server."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PIPELINE_FIXTURE = {
    "pipeline_id": "11111111-1111-1111-1111-111111111111",
    "name": "Test Pipeline",
    "nodes": [{"id": "n1"}, {"id": "n2"}],
    "edges": [],
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
}

RUN_FIXTURE = {
    "run_id": "22222222-2222-2222-2222-222222222222",
    "status": "pending",
}

STATUS_FIXTURE = {
    "run_id": "22222222-2222-2222-2222-222222222222",
    "pipeline_id": "11111111-1111-1111-1111-111111111111",
    "status": "running",
    "current_node_id": "n1",
    "node_statuses": [
        {
            "node_id": "n1",
            "status": "running",
            "started_at": "2026-01-01T00:00:01",
            "completed_at": None,
            "error": None,
        },
        {
            "node_id": "n2",
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "error": None,
        },
    ],
    "error": None,
    "started_at": "2026-01-01T00:00:00",
    "completed_at": None,
}

BLOCK_LIST_FIXTURE = [
    {
        "block_type": "source",
        "implementation": "csv_loader",
        "description": "Load data from CSV",
        "config_schema": {},
        "input_schemas": {},
        "output_schemas": {"data": "respondent_collection"},
    },
    {
        "block_type": "analysis",
        "implementation": "segmentation_kmeans",
        "description": "K-means segmentation",
        "config_schema": {},
        "input_schemas": {"data": "respondent_collection"},
        "output_schemas": {"segments": "segment_profile_set"},
    },
]

BLOCK_INSPECT_FIXTURE = BLOCK_LIST_FIXTURE[0]


def _mock_response(data: dict | list, status: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# pipeline list
# ---------------------------------------------------------------------------


def test_pipeline_list_shows_table():
    with patch("httpx.get", return_value=_mock_response([PIPELINE_FIXTURE])):
        result = runner.invoke(app, ["pipeline", "list"])
    assert result.exit_code == 0
    assert "Test Pipeline" in result.output
    assert "11111111" in result.output


def test_pipeline_list_empty():
    with patch("httpx.get", return_value=_mock_response([])):
        result = runner.invoke(app, ["pipeline", "list"])
    assert result.exit_code == 0
    assert "No pipelines" in result.output


# ---------------------------------------------------------------------------
# pipeline show
# ---------------------------------------------------------------------------


def test_pipeline_show_prints_json():
    with patch("httpx.get", return_value=_mock_response(PIPELINE_FIXTURE)):
        result = runner.invoke(app, ["pipeline", "show", "11111111-1111-1111-1111-111111111111"])
    assert result.exit_code == 0
    assert "Test Pipeline" in result.output


# ---------------------------------------------------------------------------
# pipeline run
# ---------------------------------------------------------------------------


def test_pipeline_run_shows_run_id():
    with patch("httpx.post", return_value=_mock_response(RUN_FIXTURE)):
        result = runner.invoke(app, ["pipeline", "run", "11111111-1111-1111-1111-111111111111"])
    assert result.exit_code == 0
    assert "22222222" in result.output
    assert "pending" in result.output


# ---------------------------------------------------------------------------
# pipeline status
# ---------------------------------------------------------------------------


def test_pipeline_status_shows_nodes():
    with patch("httpx.get", return_value=_mock_response(STATUS_FIXTURE)):
        result = runner.invoke(app, ["pipeline", "status", "22222222-2222-2222-2222-222222222222"])
    assert result.exit_code == 0
    assert "running" in result.output
    assert "n1" in result.output
    assert "n2" in result.output


# ---------------------------------------------------------------------------
# block list
# ---------------------------------------------------------------------------


def test_block_list_shows_all():
    with patch("httpx.get", return_value=_mock_response(BLOCK_LIST_FIXTURE)) as mock_get:
        result = runner.invoke(app, ["block", "list"])
    assert result.exit_code == 0
    assert "csv_loader" in result.output
    assert "segmentation_kmeans" in result.output
    # No type filter in URL
    called_url = mock_get.call_args[0][0]
    assert "type=" not in called_url


def test_block_list_filter_by_type():
    filtered = [BLOCK_LIST_FIXTURE[1]]
    with patch("httpx.get", return_value=_mock_response(filtered)) as mock_get:
        result = runner.invoke(app, ["block", "list", "--type", "analysis"])
    assert result.exit_code == 0
    assert "segmentation_kmeans" in result.output
    called_url = mock_get.call_args[0][0]
    assert "type=analysis" in called_url


# ---------------------------------------------------------------------------
# block inspect
# ---------------------------------------------------------------------------


def test_block_inspect_shows_schema():
    with patch("httpx.get", return_value=_mock_response(BLOCK_INSPECT_FIXTURE)):
        result = runner.invoke(app, ["block", "inspect", "source", "csv_loader"])
    assert result.exit_code == 0
    assert "source" in result.output
    assert "csv_loader" in result.output
    assert "output_schemas" in result.output or "respondent_collection" in result.output


# ---------------------------------------------------------------------------
# Connection error handling
# ---------------------------------------------------------------------------


def test_connection_error_exits_gracefully():
    import httpx as httpx_lib

    with patch("httpx.get", side_effect=httpx_lib.ConnectError("refused")):
        result = runner.invoke(app, ["pipeline", "list"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# --api-url override
# ---------------------------------------------------------------------------


def test_api_url_override():
    with patch("httpx.get", return_value=_mock_response([PIPELINE_FIXTURE])) as mock_get:
        result = runner.invoke(
            app, ["--api-url", "http://myserver:9000/api/v1", "pipeline", "list"]
        )
    assert result.exit_code == 0
    called_url = mock_get.call_args[0][0]
    assert "myserver:9000" in called_url
