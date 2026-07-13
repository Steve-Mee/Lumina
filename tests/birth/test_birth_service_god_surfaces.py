"""
AST/grep guards for birth_service god-surface baseline (phase 2A).

Locks facade size so birth_service.py cannot grow without an intentional guard update.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_BIRTH_SERVICE = _ROOT / "lumina_launcher" / "services" / "birth_service.py"

# Baseline captured 2026-07-04; runner facade collapsed into direct submodule imports.
_SERVICE_LINE_BASELINE = 520
_SERVICE_METHOD_BASELINE = 56

_BOUNDED_MODULE_MARKERS = [
    "birth_status_mapper",
    "birth_status_enricher",
    "birth_runner_start",
    "birth_runner_lock",
]


def _service_source() -> str:
    return _BIRTH_SERVICE.read_text(encoding="utf-8")


def _birth_service_class(tree: ast.Module) -> ast.ClassDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "BirthService":
            return node
    msg = "BirthService not found"
    raise AssertionError(msg)


@pytest.mark.unit
def test_birth_service_loc_at_or_below_baseline() -> None:
    line_count = len(_service_source().splitlines())
    assert line_count <= _SERVICE_LINE_BASELINE, (
        f"birth_service.py has {line_count} lines (baseline <= {_SERVICE_LINE_BASELINE}); "
        "extract to bounded modules instead of growing the god file"
    )


@pytest.mark.unit
def test_birth_service_method_count_at_or_below_baseline() -> None:
    tree = ast.parse(_service_source())
    cls = _birth_service_class(tree)
    method_count = sum(
        1 for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    assert method_count <= _SERVICE_METHOD_BASELINE, (
        f"BirthService has {method_count} methods (baseline <= {_SERVICE_METHOD_BASELINE})"
    )


@pytest.mark.unit
def test_birth_service_delegates_to_bounded_modules() -> None:
    source = _service_source()
    for marker in _BOUNDED_MODULE_MARKERS:
        assert marker.replace(".", "/") in source.replace(".", "/") or marker in source, (
            f"birth_service.py should delegate via {marker}"
        )