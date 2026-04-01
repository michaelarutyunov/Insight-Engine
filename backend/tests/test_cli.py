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


# ---------------------------------------------------------------------------
# advise command
# ---------------------------------------------------------------------------


# Fixtures for advise endpoints
CHARACTERIZE_FIXTURE = {
    "profile": {
        "research_question": "How do customers perceive our brand?",
        "dimensions": {
            "data_type": "quantitative",
            "sample_size": "medium",
            "time_horizon": "cross_sectional",
            "inference_goal": "description",
            "explanation_need": "low",
            "domain_specificity": "general",
        },
        "situational_context": {
            "available_data": "Survey responses",
            "hypothesis_state": "Exploratory",
            "time_constraint": "None",
            "epistemic_stance": "Inductive",
            "deliverable_expectation": "Presentation deck",
        },
        "reasoning": "Brand perception study with survey data",
    }
}

MATCH_FIXTURE = {
    "candidates": [
        {
            "block_implementation": "sentiment_analysis",
            "block_type": "analysis",
            "fit_score": 0.85,
            "fit_reasoning": "Well-suited for text-based sentiment analysis",
            "tradeoffs": "Requires pre-processing, may miss nuanced sentiment",
            "dimensions": {
                "data_type": "quantitative",
                "sample_size": "medium",
                "time_horizon": "cross_sectional",
                "inference_goal": "description",
                "explanation_need": "low",
                "domain_specificity": "general",
            },
        },
        {
            "block_implementation": "topic_modeling",
            "block_type": "analysis",
            "fit_score": 0.72,
            "fit_reasoning": "Can uncover themes in open-ended responses",
            "tradeoffs": "Less interpretable than supervised approaches",
            "dimensions": {
                "data_type": "quantitative",
                "sample_size": "medium",
                "time_horizon": "cross_sectional",
                "inference_goal": "description",
                "explanation_need": "low",
                "domain_specificity": "general",
            },
        },
    ]
}

RECOMMEND_FIXTURE = {
    "recommendation": {
        "selected_method": "sentiment_analysis",
        "rationale": "Sentiment analysis is the most appropriate method for this brand perception study.",
        "pipeline_sketch": {
            "nodes": [
                {"id": "n1", "block_type": "source", "implementation": "csv_loader"},
                {"id": "n2", "block_type": "analysis", "implementation": "sentiment_analysis"},
            ],
            "edges": [{"source": "n1", "target": "n2"}],
        },
        "practitioner_workflow": "1. Load survey data\n2. Run sentiment analysis\n3. Visualize results",
    }
}


def test_advise_basic_stages_1_and_2():
    """Test advise command with basic research question (stages 1 and 2 only)."""

    def mock_post_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "characterize" in url:
            return _mock_response(CHARACTERIZE_FIXTURE)
        elif "match" in url:
            return _mock_response(MATCH_FIXTURE)
        return _mock_response({})

    with patch("httpx.post", side_effect=mock_post_side_effect):
        result = runner.invoke(app, ["advise", "How do customers perceive our brand?"])

    assert result.exit_code == 0
    assert "Stage 1" in result.output
    assert "Stage 2" in result.output
    assert "sentiment_analysis" in result.output
    assert "0.85" in result.output
    assert "Stage 3" not in result.output  # Without --recommend flag


def test_advise_with_recommend_flag():
    """Test advise command with --recommend flag (includes stage 3)."""

    def mock_post_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "characterize" in url:
            return _mock_response(CHARACTERIZE_FIXTURE)
        elif "match" in url:
            return _mock_response(MATCH_FIXTURE)
        elif "recommend" in url:
            return _mock_response(RECOMMEND_FIXTURE)
        return _mock_response({})

    with patch("httpx.post", side_effect=mock_post_side_effect):
        result = runner.invoke(
            app, ["advise", "How do customers perceive our brand?", "--recommend"]
        )

    assert result.exit_code == 0
    assert "Stage 1" in result.output
    assert "Stage 2" in result.output
    assert "Stage 3" in result.output
    assert "Selected Method:" in result.output
    assert "sentiment_analysis" in result.output
    assert "Rationale:" in result.output
    assert "Pipeline Sketch:" in result.output


def test_advise_with_profile_flag():
    """Test advise command with --profile flag."""

    def mock_post_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        # Check that profile parameter is in URL
        if "profile=" in url:
            return _mock_response(CHARACTERIZE_FIXTURE)
        return _mock_response({})

    with patch("httpx.post", side_effect=mock_post_side_effect) as mock_post:
        result = runner.invoke(
            app, ["advise", "How do customers perceive our brand?", "--profile", "academic"]
        )

    assert result.exit_code == 0
    # Verify profile parameter was passed
    called_urls = [call[0][0] for call in mock_post.call_args_list]
    assert any("profile=academic" in url for url in called_urls)


def test_advise_with_data_context():
    """Test advise command with --data-context flag."""

    def mock_post_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "characterize" in url:
            # Check payload includes data_context
            payload = kwargs.get("json", {})
            if payload.get("data_context"):
                return _mock_response(CHARACTERIZE_FIXTURE)
        return _mock_response({})

    with patch("httpx.post", side_effect=mock_post_side_effect) as mock_post:
        result = runner.invoke(
            app,
            [
                "advise",
                "How do customers perceive our brand?",
                "--data-context",
                '{"sample_size": 1000, "data_source": "survey"}',
            ],
        )

    assert result.exit_code == 0
    # Verify data_context was included in request
    call_kwargs = mock_post.call_args_list[0][1]
    payload = call_kwargs.get("json", {})
    assert payload.get("data_context") == {"sample_size": 1000, "data_source": "survey"}


def test_advise_invalid_json_data_context():
    """Test advise command with invalid JSON in --data-context."""
    result = runner.invoke(
        app,
        ["advise", "How do customers perceive our brand?", "--data-context", "{invalid json}"],
    )

    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_advise_no_candidates():
    """Test advise command when no candidates are found."""
    empty_match = {"candidates": []}

    def mock_post_side_effect(*args, **kwargs):
        url = args[0] if args else kwargs.get("url", "")
        if "characterize" in url:
            return _mock_response(CHARACTERIZE_FIXTURE)
        elif "match" in url:
            return _mock_response(empty_match)
        return _mock_response({})

    with patch("httpx.post", side_effect=mock_post_side_effect):
        result = runner.invoke(app, ["advise", "How do customers perceive our brand?"])

    assert result.exit_code == 0
    assert "No matching methods found" in result.output


def test_advise_connection_error():
    """Test advise command handles connection errors gracefully."""
    import httpx as httpx_lib

    with patch("httpx.post", side_effect=httpx_lib.ConnectError("refused")):
        result = runner.invoke(app, ["advise", "How do customers perceive our brand?"])

    assert result.exit_code == 1
    assert "Connection refused" in result.output
