"""
AST/grep guards for Fase 5B: orchestrator_core god surface close-out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_ORCH = _ROOT / "lumina_core" / "evolution" / "orchestrator_core.py"
_GEN_RUNNER = _ROOT / "lumina_core" / "evolution" / "generation_runner.py"
_BIRTH_BOOT = _ROOT / "lumina_core" / "evolution" / "birth_gen0_bootstrap.py"

_FORBIDDEN_IN_ORCH = [
    "resolve_birth_gen0_dna(",
    "run_auto_forks(",
    "check_pre_promotion(",
]

_BOUNDED = [
    "generation_runner.py",
    "birth_gen0_bootstrap.py",
]


@pytest.mark.unit
def test_orchestrator_core_loc_at_or_below_target():
    line_count = len(_ORCH.read_text(encoding="utf-8").splitlines())
    assert line_count <= 1050, f"orchestrator_core.py has {line_count} lines (target <=1050)"


@pytest.mark.unit
def test_orchestrator_core_forbidden_inline_patterns():
    text = _ORCH.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IN_ORCH:
        assert pat not in text, f"Forbidden pattern in orchestrator_core: {pat!r}"


@pytest.mark.unit
def test_orchestrator_core_delegates_generation_runner():
    text = _ORCH.read_text(encoding="utf-8")
    assert "run_single_generation" in text
    assert "generation_runner" in text


@pytest.mark.unit
def test_generation_runner_owns_single_generation():
    text = _GEN_RUNNER.read_text(encoding="utf-8")
    assert "def run_single_generation" in text
    assert "resolve_initial_top_and_active_dna" in text
    assert "run_auto_forks(" in text


@pytest.mark.unit
def test_birth_gen0_bootstrap_owns_seed_resolution():
    text = _BIRTH_BOOT.read_text(encoding="utf-8")
    assert "resolve_birth_gen0_dna" in text
    assert "def bootstrap_active_dna" in text
    assert "def resolve_initial_top_and_active_dna" in text


@pytest.mark.unit
def test_bounded_evolution_modules_exist():
    pkg = _ROOT / "lumina_core" / "evolution"
    for name in _BOUNDED:
        assert (pkg / name).is_file(), f"Missing module: {name}"