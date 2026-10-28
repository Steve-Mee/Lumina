"""Pre-trade gate facade (re-exports bounded submodules)."""

from __future__ import annotations

from lumina_core.order_gatekeeper.contract_symbols import (  # noqa: F401
    is_stale_contract_symbol,
    roll_stale_contract_symbol,
)
from lumina_core.order_gatekeeper.gate import enforce_pre_trade_gate  # noqa: F401
from lumina_core.order_gatekeeper.lineage_emitters import domain_event_fingerprint
from lumina_core.order_gatekeeper.regime_session import (  # noqa: F401
    audit_stale_override,
    broker_metadata_contract_allowed,
    resolve_regime_snapshot,
    session_guard_allows_trading,
)
from lumina_core.order_gatekeeper.ungated_place_block import (  # noqa: F401
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    blocked_order_result,
    gate_order,
)
from lumina_core.risk.final_arbitration import evaluate_constitution_for_intent  # noqa: F401

_domain_event_fingerprint = domain_event_fingerprint
