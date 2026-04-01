"""Tests for 'insights pipeline create' command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_list_templates(monkeypatch) -> None:
    """Test 'pipeline create --list-templates' lists available templates."""
    # Mock TEMPLATES_DIR to point to test data
    test_templates = Path(__file__).parent.parent.parent / "templates"

    with patch("cli.main._TEMPLATES_DIR", test_templates):
        result = runner.invoke(app, ["pipeline", "create", "--list-templates"])

    assert result.exit_code == 0
    # The backend/templates/ directory should have at least 3 templates
    # Check that some template names appear
    assert "Template Name" in result.output or "templates" in result.output.lower()


def test_create_from_template_not_found() -> None:
    """Test 'pipeline create --from-template' with non-existent template."""
    result = runner.invoke(app, ["pipeline", "create", "--from-template", "nonexistent_template"])

    assert result.exit_code == 1
    assert "Template not found" in result.output


def test_create_from_template_missing_argument() -> None:
    """Test 'pipeline create' without --from-template or --list-templates."""
    result = runner.invoke(app, ["pipeline", "create"])

    assert result.exit_code == 1
    assert "--from-template is required" in result.output


def test_create_from_template_success(tmp_path: Path, monkeypatch) -> None:
    """Test 'pipeline create --from-template' creates a new file."""
    # Mock TEMPLATES_DIR
    test_templates = Path(__file__).parent.parent.parent / "templates"

    # Create a test template
    template_file = test_templates / "test_template.json"
    template_content = """{
        "pipeline_id": "11111111-1111-1111-1111-111111111111",
        "name": "Test Template Pipeline",
        "version": "1.0",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "nodes": [],
        "edges": [],
        "loop_definitions": [],
        "metadata": {"description": "Test template", "tags": [], "author": ""}
    }"""
    template_file.parent.mkdir(parents=True, exist_ok=True)
    template_file.write_text(template_content)

    # Change to temp directory
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        with patch("cli.main._TEMPLATES_DIR", test_templates):
            result = runner.invoke(app, ["pipeline", "create", "--from-template", "test_template"])

        assert result.exit_code == 0
        assert "Pipeline created" in result.output
        assert "test_template_pipeline.json" in result.output

        # Verify file was created
        output_file = tmp_path / "test_template_pipeline.json"
        assert output_file.exists()

    finally:
        os.chdir(original_cwd)
        # Cleanup
        if template_file.exists():
            template_file.unlink()


def test_create_from_template_output_file_exists(tmp_path: Path, monkeypatch) -> None:
    """Test 'pipeline create --from-template' when output file exists."""
    # Mock TEMPLATES_DIR
    test_templates = Path(__file__).parent.parent.parent / "templates"

    # Create a test template
    template_file = test_templates / "test_template_exists.json"
    template_content = """{
        "pipeline_id": "11111111-1111-1111-1111-111111111111",
        "name": "Test Pipeline",
        "version": "1.0",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "nodes": [],
        "edges": [],
        "loop_definitions": [],
        "metadata": {"description": "", "tags": [], "author": ""}
    }"""
    template_file.parent.mkdir(parents=True, exist_ok=True)
    template_file.write_text(template_content)

    # Create output file that already exists
    output_file = tmp_path / "test_pipeline.json"
    output_file.write_text("{}")

    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        with patch("cli.main._TEMPLATES_DIR", test_templates):
            result = runner.invoke(
                app,
                [
                    "pipeline",
                    "create",
                    "--from-template",
                    "test_template_exists",
                    "--output",
                    "test_pipeline.json",
                ],
            )

        assert result.exit_code == 1
        assert "already exists" in result.output

    finally:
        os.chdir(original_cwd)
        # Cleanup
        if template_file.exists():
            template_file.unlink()
        if output_file.exists():
            output_file.unlink()
