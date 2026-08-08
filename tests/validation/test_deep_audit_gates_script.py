"""T9: deep-audit pack script is importable and lists expected pytest paths."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_deep_audit_gates_module_loads() -> None:
    path = ROOT / "scripts" / "validation" / "run_deep_audit_gates.py"
    assert path.is_file()
    spec = importlib.util.spec_from_file_location("run_deep_audit_gates", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "_PYTEST_PATHS")
    assert len(mod._PYTEST_PATHS) >= 10
    # Core track files present
    joined = " ".join(mod._PYTEST_PATHS)
    assert "test_champion_freeze" in joined
    assert "test_perfect_birth" in joined
    assert "test_capital_aperture" in joined
    assert "test_twin_discipline" in joined
