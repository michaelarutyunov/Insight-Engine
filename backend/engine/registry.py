"""Block registry — auto-discovers block implementations under backend/blocks/*/*.py."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any

from blocks.base import BlockBase

_BLOCKS_DIR = Path(__file__).resolve().parent.parent / "blocks"

_REGISTRY: dict[tuple[str, str], type[BlockBase]] = {}
_INFO: dict[tuple[str, str], dict[str, Any]] = {}
_LOADED = False


def _import_module(py_file: Path, module_name: str):
    """Import a module from its file path."""
    spec = importlib.util.spec_from_file_location(module_name, py_file)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception:
        return None
    return module


def _discover() -> None:
    """Walk backend/blocks/{type}/{impl}.py, import, and register BlockBase subclasses."""
    global _LOADED
    if _LOADED:
        return

    blocks_pkg = _BLOCKS_DIR
    if not blocks_pkg.is_dir():
        _LOADED = True
        return

    for type_dir in sorted(blocks_pkg.iterdir()):
        if not type_dir.is_dir() or type_dir.name.startswith("_"):
            continue
        if not (type_dir / "__init__.py").exists():
            continue

        for py_file in sorted(type_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            implementation = py_file.stem
            module_name = f"blocks.{type_dir.name}.{implementation}"

            module = _import_module(py_file, module_name)
            if module is None:
                continue

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if obj is BlockBase:
                    continue
                if not issubclass(obj, BlockBase):
                    continue
                if obj.__module__ == "blocks.base":
                    continue
                if inspect.isabstract(obj):
                    continue

                block_type = obj().block_type
                key = (block_type, implementation)
                _REGISTRY[key] = obj
                _INFO[key] = {
                    "block_type": block_type,
                    "block_implementation": implementation,
                    "input_schemas": obj().input_schemas,
                    "output_schemas": obj().output_schemas,
                    "config_schema": obj().config_schema,
                    "description": obj().description,
                }

    _LOADED = True


def _ensure_loaded() -> None:
    _discover()


def list_blocks() -> list[dict[str, Any]]:
    """Return info dicts for every registered block implementation."""
    _ensure_loaded()
    return list(_INFO.values())


def get_block_class(block_type: str, implementation: str) -> type[BlockBase]:
    """Return the class for a specific block type + implementation.

    Raises KeyError if not found.
    """
    _ensure_loaded()
    key = (block_type, implementation)
    if key not in _REGISTRY:
        raise KeyError(
            f"No block registered for type={block_type!r}, implementation={implementation!r}"
        )
    return _REGISTRY[key]


def get_block_info(block_type: str, implementation: str) -> dict[str, Any]:
    """Return the info dict for a specific block type + implementation.

    Raises KeyError if not found.
    """
    _ensure_loaded()
    key = (block_type, implementation)
    if key not in _INFO:
        raise KeyError(
            f"No block registered for type={block_type!r}, implementation={implementation!r}"
        )
    return _INFO[key]


def reset() -> None:
    """Clear the registry. Used for testing."""
    global _LOADED
    _REGISTRY.clear()
    _INFO.clear()
    _LOADED = False
