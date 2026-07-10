"""
AST/grep guards for Fase 4C: trade_reconciler god surface close-out.

Ensures __init__.py stays a thin compat hub; non-trivial logic lives in bounded mixins.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PKG_INIT = _ROOT / "lumina_core" / "engine" / "trade_reconciler" / "__init__.py"
_RECONCILER = _ROOT / "lumina_core" / "engine" / "trade_reconciler" / "reconciler.py"

_FORBIDDEN_IN_FACADE = [
    "def ingest_fill_event",
    "def mark_closing",
    "websockets.connect",
    "EconomicPnLService",
    "asyncio.run",
]

_MIXIN_MARKERS = [
    "lifecycle_mixin",
    "fill_ingest_mixin",
    "transport_mixin",
    "fill_matching_mixin",
    "finalize_mixin",
    "audit_status_mixin",
    "fill_normalization_mixin",
]


@pytest.mark.unit
def test_trade_reconciler_facade_loc_at_or_below_target():
    line_count = len(_PKG_INIT.read_text(encoding="utf-8").splitlines())
    assert line_count <= 20, f"trade_reconciler/__init__.py has {line_count} lines (target <=20)"


@pytest.mark.unit
def test_trade_reconciler_facade_forbidden_inline_patterns():
    text = _PKG_INIT.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IN_FACADE:
        assert pat not in text, f"Forbidden inline pattern in facade: {pat!r}"


@pytest.mark.unit
def test_trade_reconciler_facade_reexports_public_api():
    text = _PKG_INIT.read_text(encoding="utf-8")
    for symbol in ("TradeReconciler", "FillEvent", "PendingTradeClose"):
        assert symbol in text, f"Missing re-export: {symbol}"


@pytest.mark.unit
def test_reconciler_composes_mixins():
    text = _RECONCILER.read_text(encoding="utf-8")
    for mixin in (
        "LifecycleMixin",
        "FillIngestMixin",
        "TransportMixin",
        "FillMatchingMixin",
        "FinalizeMixin",
        "AuditStatusMixin",
        "FillNormalizationMixin",
    ):
        assert mixin in text, f"Missing mixin: {mixin}"
    assert "class TradeReconciler(" in text


@pytest.mark.unit
def test_bounded_mixin_modules_exist():
    pkg = _ROOT / "lumina_core" / "engine" / "trade_reconciler"
    for name in _MIXIN_MARKERS:
        assert (pkg / f"{name}.py").is_file(), f"Missing mixin module: {name}.py"
    assert (pkg / "schemas.py").is_file()
    assert (pkg / "reconciler.py").is_file()