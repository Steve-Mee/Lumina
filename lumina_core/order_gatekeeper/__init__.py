"""Pre-trade gate facade (re-exports bounded submodules)."""

from __future__ import annotations

from lumina_core.order_gatekeeper.contract_symbols import is_stale_contract_symbol, roll_stale_contract_symbol
from lumina_core.order_gatekeeper.gate import enforce_pre_trade_gate
from lumina_core.order_gatekeeper.lineage_emitters import domain_event_fingerprint
from lumina_core.order_gatekeeper.regime_session import (
    audit_stale_override,
    broker_metadata_contract_allowed,
    resolve_regime_snapshot,
    session_guard_allows_trading,
)
from lumina_core.risk.final_arbitration import evaluate_constitution_for_intent

# Backward-compatible private alias used by policy_engine and tests.
_domain_event_fingerprint = domain_event_fingerprint

__all__ = [
    "_domain_event_fingerprint",
    "audit_stale_override",
    "broker_metadata_contract_allowed",
    "enforce_pre_trade_gate",
    "evaluate_constitution_for_intent",
    "is_stale_contract_symbol",
    "resolve_regime_snapshot",
    "roll_stale_contract_symbol",
    "session_guard_allows_trading",
]
