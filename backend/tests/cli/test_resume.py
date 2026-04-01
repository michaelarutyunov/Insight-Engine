"""Tests for 'insights run resume' command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

HITL_RESPONSE_FIXTURE = {
    "approved": True,
    "comments": "Looks good to proceed",
    "modifications": {},
}

RESUME_SUCCESS_FIXTURE = {
    "run_id": "22222222-2222-2222-2222-222222222222",
    "status": "running",
}

RESUME_ERROR_FIXTURE = {
    "detail": "Run 22222222-2222-2222-2222-222222222222 not found",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_resume_success(tmp_path: Path) -> None:
    """Test 'run resume' with valid response file."""
    # Create response file
    response_file = tmp_path / "hitl_response.json"
    import json

    response_file.write_text(json.dumps(HITL_RESPONSE_FIXTURE))

    def mock_post(url: str, **kwargs) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = RESUME_SUCCESS_FIXTURE
        mock.raise_for_status = MagicMock()
        return mock

    with patch("httpx.post", side_effect=mock_post):
        result = runner.invoke(
            app,
            [
                "run",
                "resume",
                "22222222-2222-2222-2222-222222222222",
                "--hitl-response",
                str(response_file),
            ],
        )

    assert result.exit_code == 0
    assert "Run resumed" in result.output
    assert "22222222" in result.output
    assert "running" in result.output


def test_resume_missing_response_file() -> None:
    """Test 'run resume' without --hitl-response option."""
    result = runner.invoke(app, ["run", "resume", "22222222-2222-2222-2222-222222222222"])

    assert result.exit_code == 1
    assert "--hitl-response is required" in result.output


def test_resume_response_file_not_found() -> None:
    """Test 'run resume' with non-existent response file."""
    result = runner.invoke(
        app,
        [
            "run",
            "resume",
            "22222222-2222-2222-2222-222222222222",
            "--hitl-response",
            "/nonexistent/response.json",
        ],
    )

    assert result.exit_code == 1
    assert "Response file not found" in result.output


def test_resume_invalid_json_response(tmp_path: Path) -> None:
    """Test 'run resume' with invalid JSON in response file."""
    response_file = tmp_path / "invalid_response.json"
    response_file.write_text('{"approved": true, "comments": "test"')

    result = runner.invoke(
        app,
        [
            "run",
            "resume",
            "22222222-2222-2222-2222-222222222222",
            "--hitl-response",
            str(response_file),
        ],
    )

    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_resume_http_error(tmp_path: Path) -> None:
    """Test 'run resume' when API returns an error."""
    response_file = tmp_path / "hitl_response.json"
    import json

    response_file.write_text(json.dumps(HITL_RESPONSE_FIXTURE))

    def mock_post(url: str, **kwargs) -> MagicMock:
        mock = MagicMock()
        mock.status_code = 404
        mock.json.return_value = RESUME_ERROR_FIXTURE
        mock.raise_for_status.side_effect = Exception("HTTP 404")
        mock.text = json.dumps(RESUME_ERROR_FIXTURE)
        return mock

    with patch("httpx.post", side_effect=mock_post):
        result = runner.invoke(
            app,
            [
                "run",
                "resume",
                "22222222-2222-2222-2222-222222222222",
                "--hitl-response",
                str(response_file),
            ],
        )

    assert result.exit_code == 1
