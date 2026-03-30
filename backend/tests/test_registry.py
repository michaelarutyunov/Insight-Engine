"""Tests for backend/engine/registry.py."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import registry  # noqa: E402

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListBlocks:
    def test_returns_list_when_empty(self) -> None:
        registry.reset()
        with patch.object(registry, "_discover"):
            registry._LOADED = True  # noqa: SLF001
            result = registry.list_blocks()
        assert isinstance(result, list)
        assert len(result) == 0


class TestGetBlockClass:
    def test_raises_keyerror_for_unknown(self) -> None:
        registry.reset()
        with pytest.raises(KeyError, match="no_such_type"):
            registry.get_block_class("no_such_type", "no_such_impl")


class TestGetBlockInfo:
    def test_raises_keyerror_for_unknown(self) -> None:
        registry.reset()
        with pytest.raises(KeyError, match="no_such_type"):
            registry.get_block_info("no_such_type", "no_such_impl")


class TestDiscovery:
    def test_discovers_concrete_block(self, tmp_path: Path) -> None:
        """Write a temporary block file, point the registry at it, verify discovery."""
        sources_dir = tmp_path / "sources"
        sources_dir.mkdir()
        (sources_dir / "__init__.py").write_text("")

        block_code = """
import sys
from pathlib import Path
# Ensure blocks.base is importable even when loaded from a temp dir
_backend = Path(__file__).resolve().parent.parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from blocks.base import SourceBase


class FakeTestSource(SourceBase):
    @property
    def output_schemas(self) -> list[str]:
        return ["generic_blob"]

    @property
    def config_schema(self) -> dict:
        return {"type": "object"}

    @property
    def description(self) -> str:
        return "test source"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict, config: dict) -> dict:
        return {"generic_blob": []}
"""
        (sources_dir / "fake_test_source.py").write_text(block_code)

        registry.reset()
        with patch.object(registry, "_BLOCKS_DIR", tmp_path):
            blocks = registry.list_blocks()

        assert len(blocks) == 1
        info = blocks[0]
        assert info["block_type"] == "source"
        assert info["block_implementation"] == "fake_test_source"
        assert info["output_schemas"] == ["generic_blob"]
        assert info["description"] == "test source"

    def test_get_block_class_after_discovery(self, tmp_path: Path) -> None:
        """get_block_class returns the class for a discovered block."""
        sources_dir = tmp_path / "sources"
        sources_dir.mkdir()
        (sources_dir / "__init__.py").write_text("")

        block_code = """
import sys
from pathlib import Path
_backend = Path(__file__).resolve().parent.parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from blocks.base import SourceBase


class HelloSource(SourceBase):
    @property
    def output_schemas(self) -> list[str]:
        return ["text_corpus"]

    @property
    def config_schema(self) -> dict:
        return {}

    @property
    def description(self) -> str:
        return "hello source"

    @property
    def methodological_notes(self) -> str:
        return "Mock for testing - no real methodology"

    def validate_config(self, config: dict) -> bool:
        return True

    async def execute(self, inputs: dict, config: dict) -> dict:
        return {"text_corpus": []}
"""
        (sources_dir / "hello_source.py").write_text(block_code)

        registry.reset()
        with patch.object(registry, "_BLOCKS_DIR", tmp_path):
            cls = registry.get_block_class("source", "hello_source")

        from blocks.base import SourceBase

        assert issubclass(cls, SourceBase)
        assert cls().block_type == "source"
