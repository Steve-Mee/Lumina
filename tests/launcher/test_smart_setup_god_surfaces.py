"""AST guards for smart_setup_service facade (phase 7A)."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_FACADE = _ROOT / "lumina_launcher" / "services" / "smart_setup_service.py"
_FACADE_LINE_BASELINE = 180

_BOUNDED_MARKERS = [
    "setup_detector",
    "ollama_installer",
    "setup_orchestrator",
    "setup_schemas",
]


def _source() -> str:
    return _FACADE.read_text(encoding="utf-8")


@pytest.mark.unit
def test_smart_setup_facade_loc_at_or_below_baseline() -> None:
    line_count = len(_source().splitlines())
    assert line_count <= _FACADE_LINE_BASELINE, (
        f"smart_setup_service.py has {line_count} lines (baseline <= {_FACADE_LINE_BASELINE})"
    )


@pytest.mark.unit
def test_smart_setup_facade_delegates_to_bounded_modules() -> None:
    source = _source()
    for marker in _BOUNDED_MARKERS:
        assert marker in source, f"smart_setup_service.py should delegate via {marker}"