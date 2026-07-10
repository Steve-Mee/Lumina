"""
AST/grep guards for Fase 4B: broker_bridge god surface close-out.

Ensures __init__.py stays a thin compat hub; non-trivial logic lives in bounded modules.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PKG_INIT = _ROOT / "lumina_core" / "broker" / "broker_bridge" / "__init__.py"
_PAPER = _ROOT / "lumina_core" / "broker" / "broker_bridge" / "paper_broker.py"
_CROSS = _ROOT / "lumina_core" / "broker" / "broker_bridge" / "cross_trade_broker.py"

_FORBIDDEN_IN_FACADE = [
    "class PaperBroker",
    "class CrossTradeBroker",
    "def broker_factory",
    "def run_final_arbitration",
    "requests.Session",
    "TradeExecutionCostModel",
]

_BOUNDED_MODULE_MARKERS = [
    "schemas",
    "admission",
    "base",
    "paper_broker",
    "cross_trade_broker",
    "cross_trade_account",
    "factory",
]


@pytest.mark.unit
def test_broker_bridge_facade_loc_at_or_below_target():
    line_count = len(_PKG_INIT.read_text(encoding="utf-8").splitlines())
    assert line_count <= 40, f"broker_bridge/__init__.py has {line_count} lines (target <=40)"


@pytest.mark.unit
def test_broker_bridge_facade_forbidden_inline_patterns():
    text = _PKG_INIT.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IN_FACADE:
        assert pat not in text, f"Forbidden inline pattern in facade: {pat!r}"


@pytest.mark.unit
def test_broker_bridge_facade_reexports_public_api():
    text = _PKG_INIT.read_text(encoding="utf-8")
    for symbol in (
        "PaperBroker",
        "CrossTradeBroker",
        "broker_factory",
        "Order",
        "enforce_pre_trade_gate",
        "random",
    ):
        assert symbol in text, f"Missing re-export: {symbol}"


@pytest.mark.unit
def test_paper_broker_owns_submit_order():
    text = _PAPER.read_text(encoding="utf-8")
    assert "def submit_order" in text
    assert "run_final_arbitration" in text
    assert "EXECUTION_FILL_RECEIVED_TOPIC" in text


@pytest.mark.unit
def test_cross_trade_broker_owns_live_rest():
    text = _CROSS.read_text(encoding="utf-8")
    assert "def submit_order" in text
    assert "get_account_info" in text
    assert "subscribe_to_websocket" in text


@pytest.mark.unit
def test_bounded_modules_exist():
    pkg = _ROOT / "lumina_core" / "broker" / "broker_bridge"
    for name in _BOUNDED_MODULE_MARKERS:
        assert (pkg / f"{name}.py").is_file(), f"Missing bounded module: {name}.py"