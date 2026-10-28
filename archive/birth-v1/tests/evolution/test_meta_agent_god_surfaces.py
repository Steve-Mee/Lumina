"""
AST/grep guards for Fase 5A: meta_agent_core god surface close-out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_META = _ROOT / "lumina_core" / "engine" / "meta_agent_core.py"
_NIGHTLY = _ROOT / "lumina_core" / "evolution" / "nightly_cycle.py"

_FORBIDDEN_IN_META = [
    "EvolutionOrchestrator(",
    "ABExperimentFramework(",
    "apply_risk_config_mutation(",
    "guard.evaluate(",
]

_BOUNDED = [
    "nightly_cycle.py",
    "mutation_executor.py",
    "dream_integration.py",
    "meta_agent_config.py",
]


@pytest.mark.unit
def test_meta_agent_core_loc_at_or_below_target():
    line_count = len(_META.read_text(encoding="utf-8").splitlines())
    assert line_count <= 400, f"meta_agent_core.py has {line_count} lines (target <=400)"


@pytest.mark.unit
def test_meta_agent_core_forbidden_inline_patterns():
    text = _META.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IN_META:
        assert pat not in text, f"Forbidden pattern in meta_agent_core: {pat!r}"


@pytest.mark.unit
def test_meta_agent_core_delegates_nightly_cycle():
    text = _META.read_text(encoding="utf-8")
    assert "run_nightly_evolution_cycle" in text
    assert "apply_evolution_candidate" in text


@pytest.mark.unit
def test_nightly_cycle_owns_orchestration():
    text = _NIGHTLY.read_text(encoding="utf-8")
    assert "def run_nightly_evolution_cycle" in text
    assert "run_multi_gen_nightly_cycle" in text


@pytest.mark.unit
def test_bounded_evolution_modules_exist():
    pkg = _ROOT / "lumina_core" / "evolution"
    for name in _BOUNDED:
        assert (pkg / name).is_file(), f"Missing module: {name}"