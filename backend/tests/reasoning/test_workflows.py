"""Tests for reasoning/workflows.py — load_workflow, get_workflow_for_block."""

from pathlib import Path

import pytest

from reasoning.profiles import load_profile
from reasoning.workflows import get_workflow_for_block, load_workflow

REASONING_PROFILES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "reasoning_profiles"
DEFAULT_PROFILE_PATH = REASONING_PROFILES_DIR / "default" / "profile.yaml"
SEGMENTATION_WORKFLOW_PATH = (
    REASONING_PROFILES_DIR / "default" / "practitioner_workflows" / "segmentation.md"
)


class TestLoadWorkflow:
    """Tests for load_workflow()."""

    def test_segmentation_workflow_loads(self):
        """Loading segmentation.md returns a non-empty string."""
        content = load_workflow(SEGMENTATION_WORKFLOW_PATH)
        assert isinstance(content, str)
        assert len(content) > 0

    def test_segmentation_workflow_has_required_sections(self):
        """The workflow contains the expected section headings."""
        content = load_workflow(SEGMENTATION_WORKFLOW_PATH)
        assert "Pre-analysis checks" in content
        assert "Method selection guidance" in content
        assert "Execution steps" in content
        assert "Reporting requirements" in content

    def test_missing_workflow_raises(self):
        """Loading a non-existent workflow file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_workflow(Path("/nonexistent/workflow.md"))


class TestGetWorkflowForBlock:
    """Tests for get_workflow_for_block()."""

    @pytest.fixture()
    def profile(self):
        return load_profile(DEFAULT_PROFILE_PATH)

    def test_get_workflow_for_kmeans(self, profile):
        """segmentation_kmeans maps to segmentation.md workflow."""
        result = get_workflow_for_block(
            "segmentation_kmeans", profile, REASONING_PROFILES_DIR / "default"
        )
        assert result is not None
        assert "segmentation" in result.lower()

    def test_missing_workflow_returns_none(self, profile):
        """A block with no matching workflow file returns None."""
        result = get_workflow_for_block(
            "nonexistent_method", profile, REASONING_PROFILES_DIR / "default"
        )
        assert result is None

    def test_family_name_derivation(self, profile):
        """block_impl with underscore maps to family prefix."""
        # "segmentation_lca" should also map to "segmentation.md"
        result = get_workflow_for_block(
            "segmentation_lca", profile, REASONING_PROFILES_DIR / "default"
        )
        assert result is not None
        assert "segmentation" in result.lower()
