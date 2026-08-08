"""
AST/grep guards for Fase 6A: container god surface close-out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PKG_INIT = _ROOT / "lumina_core" / "container" / "__init__.py"

_FORBIDDEN_IN_FACADE = [
    "MarketDataIngestService(",
    "SelfEvolutionMetaAgent.from_container(",
    "PortfolioVaRAllocator(",
    "AgentBlackboard(",
]

_BOUNDED = [
    "engine_wiring.py",
    "agent_wiring.py",
    "risk_wiring.py",
]


@pytest.mark.unit
def test_container_facade_loc_at_or_below_target():
    line_count = len(_PKG_INIT.read_text(encoding="utf-8").splitlines())
    assert line_count <= 600, f"container/__init__.py has {line_count} lines (target <=600)"


@pytest.mark.unit
def test_container_facade_forbidden_inline_patterns():
    text = _PKG_INIT.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IN_FACADE:
        assert pat not in text, f"Forbidden inline pattern in container facade: {pat!r}"


@pytest.mark.unit
def test_container_facade_delegates_wiring_modules():
    """Wiring lives on ApplicationContainerServicesMixin (M5 extract), not the facade."""
    services = (_ROOT / "lumina_core" / "container" / "container_services.py").read_text(
        encoding="utf-8"
    )
    facade = _PKG_INIT.read_text(encoding="utf-8")
    assert "ApplicationContainerServicesMixin" in facade
    assert "wire_platform_services" in services
    assert "wire_intelligence_agents" in services
    assert "wire_risk_services" in services


@pytest.mark.unit
def test_bounded_container_modules_exist():
    pkg = _ROOT / "lumina_core" / "container"
    for name in _BOUNDED:
        assert (pkg / name).is_file(), f"Missing bounded module: {name}"