"""
AST/grep guards for Fase 4A: order_gatekeeper god surface close-out.

Ensures __init__.py stays a thin compat hub; non-trivial logic lives in bounded modules.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PKG_INIT = _ROOT / "lumina_core" / "order_gatekeeper" / "__init__.py"
_GATE = _ROOT / "lumina_core" / "order_gatekeeper" / "gate.py"
_ADMISSION = _ROOT / "lumina_core" / "order_gatekeeper" / "admission_steps.py"

_FORBIDDEN_IN_FACADE = [
    "def enforce_pre_trade_gate",
    "AdmissionContext(",
    "default_chain_for_mode",
    "build_admission_step_handlers",
    "GateEntryPayload",
    "while True:",
]

_BOUNDED_MODULE_MARKERS = [
    "contract_symbols",
    "lineage_emitters",
    "admission_steps",
    "regime_session",
    "engine_helpers",
    "gate",
]


@pytest.mark.unit
def test_order_gatekeeper_facade_loc_at_or_below_target():
    line_count = len(_PKG_INIT.read_text(encoding="utf-8").splitlines())
    assert line_count <= 30, f"order_gatekeeper/__init__.py has {line_count} lines (target <=30)"


@pytest.mark.unit
def test_order_gatekeeper_facade_forbidden_inline_patterns():
    text = _PKG_INIT.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IN_FACADE:
        assert pat not in text, f"Forbidden inline pattern in facade: {pat!r}"


@pytest.mark.unit
def test_order_gatekeeper_facade_reexports_public_api():
    text = _PKG_INIT.read_text(encoding="utf-8")
    for symbol in (
        "enforce_pre_trade_gate",
        "is_stale_contract_symbol",
        "roll_stale_contract_symbol",
        "resolve_regime_snapshot",
        "session_guard_allows_trading",
        "_domain_event_fingerprint",
    ):
        assert symbol in text, f"Missing re-export: {symbol}"


@pytest.mark.unit
def test_gate_module_owns_orchestrator():
    text = _GATE.read_text(encoding="utf-8")
    assert "def enforce_pre_trade_gate" in text
    assert "default_chain_for_mode" in text
    assert "build_admission_step_handlers" in text


@pytest.mark.unit
def test_admission_steps_owns_chain_handlers():
    text = _ADMISSION.read_text(encoding="utf-8")
    assert "def build_admission_step_handlers" in text
    assert "ADMISSION_STEP_RISK_POLICY" in text
    assert "ADMISSION_STEP_FINAL_ARBITRATION" in text
    assert "evaluate_constitution_for_intent" in text


@pytest.mark.unit
def test_bounded_modules_exist():
    pkg = _ROOT / "lumina_core" / "order_gatekeeper"
    for name in _BOUNDED_MODULE_MARKERS:
        assert (pkg / f"{name}.py").is_file(), f"Missing bounded module: {name}.py"