"""Tests for 'insights pipeline validate' command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_PIPELINE_FIXTURE = {
    "pipeline_id": "11111111-1111-1111-1111-111111111111",
    "name": "Test Pipeline",
    "version": "1.0",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
    "nodes": [
        {
            "node_id": "22222222-2222-2222-2222-222222222222",
            "block_type": "source",
            "block_implementation": "csv_source",
            "label": "Load Data",
            "position": {"x": 100, "y": 100},
            "config": {},
            "input_schema": [],
            "output_schema": ["respondent_collection"],
        }
    ],
    "edges": [],
    "loop_definitions": [],
    "metadata": {"description": "Test pipeline", "tags": [], "author": ""},
}

INVALID_JSON_FIXTURE = '{"pipeline_id": "123", "name": "invalid", "nodes": [}'

INVALID_SCHEMA_FIXTURE = {
    "pipeline_id": "not-a-uuid",
    "name": "Invalid Pipeline",
    "version": "1.0",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
    "nodes": [],
    "edges": [],
    "loop_definitions": [],
    "metadata": {"description": "", "tags": [], "author": ""},
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_validate_valid_pipeline(tmp_path: Path) -> None:
    """Test validate command with a valid pipeline file."""
    # Create temporary pipeline file
    pipeline_file = tmp_path / "valid_pipeline.json"
    import json

    pipeline_file.write_text(json.dumps(VALID_PIPELINE_FIXTURE))

    result = runner.invoke(app, ["pipeline", "validate", str(pipeline_file)])

    assert result.exit_code == 0
    assert "Valid pipeline" in result.output
    assert "Test Pipeline" in result.output
    assert "11111111" in result.output
    assert "Nodes       : 1" in result.output


def test_validate_file_not_found() -> None:
    """Test validate command with non-existent file."""
    result = runner.invoke(app, ["pipeline", "validate", "/nonexistent/file.json"])

    assert result.exit_code == 1
    assert "File not found" in result.output


def test_validate_invalid_json(tmp_path: Path) -> None:
    """Test validate command with invalid JSON."""
    pipeline_file = tmp_path / "invalid.json"
    pipeline_file.write_text(INVALID_JSON_FIXTURE)

    result = runner.invoke(app, ["pipeline", "validate", str(pipeline_file)])

    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_validate_invalid_schema(tmp_path: Path) -> None:
    """Test validate command with invalid schema."""
    pipeline_file = tmp_path / "invalid_schema.json"
    import json

    pipeline_file.write_text(json.dumps(INVALID_SCHEMA_FIXTURE))

    result = runner.invoke(app, ["pipeline", "validate", str(pipeline_file)])

    assert result.exit_code == 1
    assert "Validation errors" in result.output
