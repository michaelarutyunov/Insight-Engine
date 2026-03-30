"""Contract tests for all registered Analysis blocks — dimensions, descriptions, notes, tags.

Auto-discovers Analysis blocks via the registry (no hardcoded list).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from blocks.base import AnalysisBase  # noqa: E402
from engine.registry import list_blocks, reset  # noqa: E402
from reasoning.dimensions import ALLOWED_VALUES, validate_dimensions  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_registry():
    """Reset the registry before each test so discovery runs cleanly."""
    reset()
    yield
    reset()


def _get_analysis_blocks() -> list[dict]:
    """Return info dicts for all registered Analysis blocks."""
    all_blocks = list_blocks()
    return [b for b in all_blocks if b.get("block_type") == "analysis"]


def _get_analysis_instances() -> list[AnalysisBase]:
    """Return instantiated Analysis blocks via the registry."""
    from engine.registry import get_block_class

    reset()
    infos = _get_analysis_blocks()
    instances = []
    for info in infos:
        cls = get_block_class(info["block_type"], info["block_implementation"])
        instances.append(cls())
    return instances


class TestAnalysisBlockDimensions:
    """Verify dimensions property on all Analysis blocks."""

    def test_all_analysis_blocks_have_dimensions(self):
        """Every Analysis block returns a non-empty dimensions dict."""
        for block in _get_analysis_instances():
            dims = block.dimensions
            assert isinstance(dims, dict), (
                f"{block.__class__.__name__}.dimensions should be dict, got {type(dims).__name__}"
            )
            assert len(dims) > 0, f"{block.__class__.__name__}.dimensions is empty"

    def test_all_analysis_block_dimensions_valid(self):
        """All dimension keys and values conform to ALLOWED_VALUES."""
        for block in _get_analysis_instances():
            dims = block.dimensions
            assert validate_dimensions(dims) is True, (
                f"{block.__class__.__name__} has invalid dimensions: {dims}"
            )

    def test_all_analysis_blocks_have_all_six_dimensions(self):
        """Each Analysis block declares all 6 dimensions."""
        expected_keys = set(ALLOWED_VALUES.keys())
        for block in _get_analysis_instances():
            dims = block.dimensions
            actual_keys = set(dims.keys())
            missing = expected_keys - actual_keys
            assert not missing, f"{block.__class__.__name__} missing dimensions: {missing}"


class TestAnalysisBlockCatalog:
    """Verify catalog metadata on all Analysis blocks."""

    def test_all_analysis_blocks_have_description(self):
        """description is a non-empty string."""
        for block in _get_analysis_instances():
            assert isinstance(block.description, str), (
                f"{block.__class__.__name__}.description is not a string"
            )
            assert len(block.description) > 0, f"{block.__class__.__name__}.description is empty"

    def test_all_analysis_blocks_have_methodological_notes(self):
        """methodological_notes is a non-empty string."""
        for block in _get_analysis_instances():
            assert isinstance(block.methodological_notes, str), (
                f"{block.__class__.__name__}.methodological_notes is not a string"
            )
            assert len(block.methodological_notes) > 0, (
                f"{block.__class__.__name__}.methodological_notes is empty"
            )

    def test_all_analysis_blocks_have_tags(self):
        """tags is a non-empty list of strings."""
        for block in _get_analysis_instances():
            assert isinstance(block.tags, list), f"{block.__class__.__name__}.tags is not a list"
            assert len(block.tags) > 0, f"{block.__class__.__name__}.tags is empty"
            assert all(isinstance(t, str) for t in block.tags), (
                f"{block.__class__.__name__}.tags contains non-string elements"
            )

    def test_all_analysis_blocks_preserves_input_type_false(self):
        """Analysis blocks must return preserves_input_type == False."""
        for block in _get_analysis_instances():
            assert block.preserves_input_type is False, (
                f"{block.__class__.__name__}.preserves_input_type should be False"
            )
