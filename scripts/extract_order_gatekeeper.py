"""One-shot mechanical split of lumina_core/order_gatekeeper.py into a bounded package."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "lumina_core" / "order_gatekeeper.py"
PKG = ROOT / "lumina_core" / "order_gatekeeper"

ENGINE_HELPERS = '''"""Shared engine accessors for the pre-trade gate."""

from __future__ import annotations

from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.logging_utils import get_logger

_LOG = get_logger("lumina.trading.gate")
MODES_REQUIRING_EQUITY_SNAPSHOT = frozenset({"real", "paper", "sim_real_guard"})


def logger_for_engine(engine: Any):
    app = getattr(engine, "app", None)
    logger = getattr(app, "logger", None)
    return logger if logger is not None else _LOG


def safe_log_warning(engine: Any, message: str) -> None:
    logger_for_engine(engine).warning(message)


def record_mode_guard_block(engine: Any, *, mode: str, reason: str) -> None:
    obs = getattr(engine, "observability_service", None)
    if obs is not None and hasattr(obs, "record_mode_guard_block"):
        obs.record_mode_guard_block(mode=str(mode), reason=str(reason))


def audit_trade_decision(engine: Any, payload: dict[str, Any], *, mode: str) -> bool:
    service = getattr(engine, "audit_log_service", None)
    if service is None or not hasattr(service, "log_decision"):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="AUDIT_LOG_SERVICE_MISSING",
            message="audit_log_service.log_decision is required for pre-trade enforcement.",
        )
    return bool(service.log_decision(payload, is_real_mode=str(mode).lower() == "real"))


def resolve_blackboard(engine: Any) -> Any | None:
    board = getattr(engine, "blackboard", None)
    if board is not None:
        return board
    app = getattr(engine, "app", None)
    return getattr(app, "blackboard", None)


def resolve_event_bus(engine: Any) -> Any | None:
    return getattr(engine, "event_bus", None)


def is_risk_reducing_side(*, engine: Any, order_side: str | None) -> bool:
    side = str(order_side or "").strip().upper()
    if side not in {"BUY", "SELL"}:
        return False
    live_qty = int(getattr(engine, "live_position_qty", 0) or 0)
    return (live_qty > 0 and side == "SELL") or (live_qty < 0 and side == "BUY")
'''

CONTRACT_SYMBOLS_HEADER = '''"""Futures contract symbol parsing and roll helpers."""

from __future__ import annotations

from datetime import datetime, timezone

'''

REGIME_SESSION_HEADER = '''"""Regime snapshot and session/broker gate helpers."""

from __future__ import annotations

from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.order_gatekeeper.engine_helpers import safe_log_warning

'''

LINEAGE_HEADER = '''"""Decision lineage fingerprints and audit payload builders."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.order_gatekeeper.engine_helpers import resolve_blackboard, resolve_event_bus

'''

INIT = '''"""Pre-trade gate facade (re-exports bounded submodules)."""

from __future__ import annotations

from lumina_core.order_gatekeeper.contract_symbols import is_stale_contract_symbol, roll_stale_contract_symbol
from lumina_core.order_gatekeeper.gate import enforce_pre_trade_gate
from lumina_core.order_gatekeeper.lineage_emitters import domain_event_fingerprint
from lumina_core.order_gatekeeper.regime_session import resolve_regime_snapshot, session_guard_allows_trading

# Backward-compatible private alias used by policy_engine and tests.
_domain_event_fingerprint = domain_event_fingerprint

__all__ = [
    "_domain_event_fingerprint",
    "enforce_pre_trade_gate",
    "is_stale_contract_symbol",
    "resolve_regime_snapshot",
    "roll_stale_contract_symbol",
    "session_guard_allows_trading",
]
'''


def _slice(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    PKG.mkdir(parents=True, exist_ok=True)

    contract_body = _slice(lines, 32, 49) + "\n" + _slice(lines, 257, 323)
    contract_body = contract_body.replace("_MONTHS", "MONTHS").replace(
        "_QUARTERLY_MONTH_CODES", "QUARTERLY_MONTH_CODES"
    ).replace("_MONTH_CODE_BY_NUM", "MONTH_CODE_BY_NUM").replace(
        "_parse_contract_symbol", "parse_contract_symbol"
    ).replace("_third_friday", "third_friday")
    (PKG / "contract_symbols.py").write_text(CONTRACT_SYMBOLS_HEADER + contract_body, encoding="utf-8")

    regime_body = _slice(lines, 326, 398)
    regime_body = regime_body.replace("_safe_log_warning", "safe_log_warning").replace(
        "_broker_metadata_contract_allowed", "broker_metadata_contract_allowed"
    ).replace("_audit_stale_override", "audit_stale_override")
    (PKG / "regime_session.py").write_text(REGIME_SESSION_HEADER + regime_body, encoding="utf-8")

    lineage_body = _slice(lines, 92, 254)
    lineage_body = (
        lineage_body.replace("_resolve_blackboard", "resolve_blackboard")
        .replace("_resolve_event_bus", "resolve_event_bus")
        .replace("_domain_event_fingerprint", "domain_event_fingerprint")
        .replace("_agents_from_blackboard", "agents_from_blackboard")
        .replace("_execution_aggregate_lineage", "execution_aggregate_lineage")
        .replace("_agents_from_dream", "agents_from_dream")
        .replace("_build_audit_payload", "build_audit_payload")
    )
    (PKG / "lineage_emitters.py").write_text(LINEAGE_HEADER + lineage_body, encoding="utf-8")

    (PKG / "engine_helpers.py").write_text(ENGINE_HELPERS, encoding="utf-8")
    (PKG / "__init__.py").write_text(INIT, encoding="utf-8")

    print(f"Wrote package skeleton under {PKG}")
    print("Next: run admission_steps.py + gate.py manual extraction (nested closures)")


if __name__ == "__main__":
    main()