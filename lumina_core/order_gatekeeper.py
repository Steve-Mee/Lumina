from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.mode_capabilities import resolve_mode_capabilities

_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


_LOG = logging.getLogger(__name__)


def _logger_for_engine(engine: Any):
    app = getattr(engine, "app", None)
    logger = getattr(app, "logger", None)
    return logger if logger is not None else _LOG


def _safe_log_warning(engine: Any, message: str) -> None:
    logger = _logger_for_engine(engine)
    try:
        logger.warning(message)
    except Exception:
        _LOG.warning(message)


def _record_mode_guard_block(engine: Any, *, mode: str, reason: str) -> None:
    obs = getattr(engine, "observability_service", None)
    if obs is not None and hasattr(obs, "record_mode_guard_block"):
        try:
            obs.record_mode_guard_block(mode=str(mode), reason=str(reason))
        except Exception:
            pass


def _audit_trade_decision(engine: Any, payload: dict[str, Any], *, mode: str) -> bool:
    service = getattr(engine, "audit_log_service", None)
    if service is None or not hasattr(service, "log_decision"):
        return True
    try:
        return bool(service.log_decision(payload, is_real_mode=str(mode).lower() == "real"))
    except Exception:
        return False


def _resolve_blackboard(engine: Any) -> Any | None:
    board = getattr(engine, "blackboard", None)
    if board is not None:
        return board
    app = getattr(engine, "app", None)
    return getattr(app, "blackboard", None)


def _agents_from_blackboard(engine: Any) -> list[dict[str, Any]]:
    board = _resolve_blackboard(engine)
    if board is None or not hasattr(board, "latest"):
        return []

    topics = (
        "agent.rl.proposal",
        "agent.news.proposal",
        "agent.emotional_twin.proposal",
        "agent.swarm.proposal",
        "agent.tape.proposal",
    )
    agents: list[dict[str, Any]] = []
    for topic in topics:
        try:
            event = board.latest(topic)
        except Exception:
            event = None
        if event is None:
            continue

        payload = getattr(event, "payload", {}) if hasattr(event, "payload") else {}
        payload = payload if isinstance(payload, dict) else {}
        producer = str(getattr(event, "producer", "") or "")
        agent_id = str(payload.get("agent_id") or payload.get("chosen_strategy") or producer or topic)
        confidence = float(
            payload.get("confidence", payload.get("confluence_score", getattr(event, "confidence", 0.0))) or 0.0
        )
        agents.append(
            {
                "agent_id": agent_id,
                "topic": topic,
                "producer": producer,
                "confidence": confidence,
                "signal": str(payload.get("signal", payload.get("sentiment_signal", "")) or ""),
                "reason": str(payload.get("reason", payload.get("why_no_trade", "")) or ""),
                "timestamp": str(getattr(event, "timestamp", "") or ""),
                "correlation_id": str(getattr(event, "correlation_id", "") or ""),
                "sequence": int(getattr(event, "sequence", 0) or 0),
                "lineage": {
                    "event_hash": str(getattr(event, "event_hash", "") or ""),
                    "prev_hash": str(getattr(event, "prev_hash", "") or ""),
                },
            }
        )
    return agents


def _execution_aggregate_lineage(engine: Any) -> dict[str, Any]:
    board = _resolve_blackboard(engine)
    if board is None or not hasattr(board, "latest"):
        return {}
    try:
        event = board.latest("execution.aggregate")
    except Exception:
        event = None
    if event is None:
        return {}

    payload = getattr(event, "payload", {}) if hasattr(event, "payload") else {}
    payload = payload if isinstance(payload, dict) else {}
    return {
        "topic": "execution.aggregate",
        "producer": str(getattr(event, "producer", "") or ""),
        "confidence": float(getattr(event, "confidence", 0.0) or 0.0),
        "timestamp": str(getattr(event, "timestamp", "") or ""),
        "correlation_id": str(getattr(event, "correlation_id", "") or ""),
        "sequence": int(getattr(event, "sequence", 0) or 0),
        "lineage": {
            "event_hash": str(getattr(event, "event_hash", "") or ""),
            "prev_hash": str(getattr(event, "prev_hash", "") or ""),
        },
        "signal": str(payload.get("signal", "") or ""),
        "chosen_strategy": str(payload.get("chosen_strategy", "") or ""),
    }


def _agents_from_dream(engine: Any) -> list[dict[str, Any]]:
    blackboard_agents = _agents_from_blackboard(engine)
    if blackboard_agents:
        return blackboard_agents

    snapshot = {}
    if hasattr(engine, "get_current_dream_snapshot"):
        try:
            snapshot = engine.get_current_dream_snapshot() or {}
        except Exception:
            snapshot = {}
    if not isinstance(snapshot, dict):
        return []

    chosen_strategy = str(snapshot.get("chosen_strategy", "unknown") or "unknown")
    confidence = float(snapshot.get("confidence", snapshot.get("confluence_score", 0.0)) or 0.0)
    reason = str(snapshot.get("reason", "") or "")
    return [
        {
            "agent_id": chosen_strategy,
            "topic": "dream.snapshot",
            "producer": "lumina_engine",
            "confidence": confidence,
            "reason": reason,
        }
    ]


def _build_audit_payload(
    engine: Any,
    *,
    symbol: str,
    regime: str,
    proposed_risk: float,
    mode: str,
    stage: str,
    final_decision: str,
    reason: str,
    var_payload: dict[str, Any] | None = None,
    mc_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = {}
    if hasattr(engine, "get_current_dream_snapshot"):
        try:
            snapshot = engine.get_current_dream_snapshot() or {}
        except Exception:
            snapshot = {}
    if not isinstance(snapshot, dict):
        snapshot = {}

    probability = float(snapshot.get("confidence", snapshot.get("confluence_score", 0.0)) or 0.0)
    expected_value = float(snapshot.get("expected_value", snapshot.get("ev", 0.0)) or 0.0)
    decision_id = f"{symbol}-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{uuid.uuid4().hex[:8]}"
    agents = _agents_from_dream(engine)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_id": decision_id,
        "stage": stage,
        "symbol": str(symbol),
        "regime": str(regime),
        "mode": str(mode),
        "proposed_risk": float(proposed_risk),
        "agents_involved": agents,
        "agent_lineage": agents,
        "execution_aggregate_lineage": _execution_aggregate_lineage(engine),
        "probability": probability,
        "expected_value": expected_value,
        "var_impact": dict(var_payload or {}),
        "monte_carlo": dict(mc_payload or {}),
        "final_decision": str(final_decision),
        "reason": str(reason),
    }


def _parse_contract_symbol(symbol: str) -> tuple[str | None, int | None, int | None]:
    text = str(symbol or "").strip().upper()
    parts = text.split()
    if len(parts) < 2:
        return None, None, None

    code = parts[1]
    if len(code) != 5:
        return None, None, None

    month = _MONTHS.get(code[:3])
    if month is None:
        return None, None, None

    try:
        year = 2000 + int(code[3:5])
    except ValueError:
        return None, None, None

    root = parts[0] if parts else None
    return root, month, year


def _third_friday(year: int, month: int) -> datetime:
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    weekday = first.weekday()  # Monday=0
    days_to_friday = (4 - weekday) % 7
    first_friday_day = 1 + days_to_friday
    third_friday_day = first_friday_day + 14
    return datetime(year, month, third_friday_day, 23, 59, 59, tzinfo=timezone.utc)


def is_stale_contract_symbol(symbol: str, *, now_utc: datetime | None = None) -> bool:
    """Return True when a futures contract symbol is clearly past expiry month.

    Expected format example: "MES JUN26".
    If parsing fails, return False to avoid false blocking.
    """
    _root, month, year = _parse_contract_symbol(symbol)
    if month is None or year is None:
        return False

    now = now_utc or datetime.now(timezone.utc)
    # Calendar-aware expiry approximation (3rd Friday of contract month, CME style futures).
    expiry_utc = _third_friday(int(year), int(month))
    return now > expiry_utc


def session_guard_allows_trading(engine: Any) -> tuple[bool, str]:
    """Centralized SessionGuard enforcement status used across runtime gates."""
    risk_controller = getattr(engine, "risk_controller", None)
    limits = getattr(risk_controller, "_active_limits", None)
    enforce_session_guard = bool(getattr(limits, "enforce_session_guard", True))
    if not enforce_session_guard:
        return True, "session_guard_disabled"

    session_guard = getattr(engine, "session_guard", None)
    if session_guard is None:
        return False, "session_guard_unavailable"

    try:
        if session_guard.is_rollover_window():
            return False, "rollover_window"
        if not session_guard.is_trading_session():
            return False, "outside_trading_session"
    except Exception:
        return False, "session_guard_check_failed"

    return True, "ok"


def _broker_metadata_contract_allowed(engine: Any, symbol: str) -> tuple[bool, str]:
    """Optional broker metadata check; pass-through when broker does not expose metadata APIs."""
    container = getattr(engine, "container", None)
    if container is None:
        app = getattr(engine, "app", None)
        container = getattr(app, "container", None)
    broker = getattr(container, "broker", None) if container is not None else None
    if broker is None:
        return True, "broker_unavailable_for_metadata"

    # Preferred explicit capability.
    if hasattr(broker, "is_contract_tradeable"):
        try:
            ok, reason = broker.is_contract_tradeable(str(symbol))
            return bool(ok), str(reason or "broker_metadata_gate")
        except Exception:
            return False, "broker_metadata_check_failed"

    # Optional metadata dictionary capability.
    if hasattr(broker, "get_contract_metadata"):
        try:
            meta = broker.get_contract_metadata(str(symbol))
            if isinstance(meta, dict):
                if bool(meta.get("expired", False)):
                    return False, "broker_metadata_expired"
                if meta.get("tradeable") is False:
                    return False, "broker_metadata_not_tradeable"
        except Exception:
            return False, "broker_metadata_check_failed"

    return True, "ok"


def _audit_stale_override(engine: Any, symbol: str, mode: str) -> None:
    _safe_log_warning(
        engine,
        (
            "OVERRIDE_AUDIT,gate=stale_contract,"
            f"mode={mode},symbol={symbol},source=LUMINA_ALLOW_STALE_CONTRACTS"
        ),
    )


def resolve_regime_snapshot(engine: Any, regime: str | None = None) -> dict[str, Any]:
    """Resolve and refresh the active regime snapshot used by risk/session gates."""
    reasoning_service = getattr(engine, "reasoning_service", None)
    if reasoning_service is not None and hasattr(reasoning_service, "refresh_regime_snapshot"):
        snapshot = reasoning_service.refresh_regime_snapshot()
        return snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)

    existing = getattr(engine, "current_regime_snapshot", {})
    if isinstance(existing, dict) and existing:
        return existing

    label = str(regime or getattr(engine, "market_regime", "NEUTRAL") or "NEUTRAL")
    fallback = {
        "label": label,
        "risk_state": "NORMAL",
        "adaptive_policy": {
            "risk_multiplier": 1.0,
            "cooldown_minutes": 30,
            "high_risk": False,
        },
    }
    engine.current_regime_snapshot = fallback
    return fallback


def enforce_pre_trade_gate(
    engine: Any,
    *,
    symbol: str,
    regime: str,
    proposed_risk: float,
) -> tuple[bool, str]:
    """Single pre-trade gatekeeper for SessionGuard + HardRiskController."""
    mode = str(getattr(getattr(engine, "config", None), "trade_mode", "paper") or "paper").strip().lower()
    capabilities = resolve_mode_capabilities(mode)

    def _audit_or_fail_closed(payload: dict[str, Any], *, reason_code: str = "audit_fail_closed") -> tuple[bool, str]:
        ok = _audit_trade_decision(engine, payload, mode=mode)
        if mode == "real" and not ok:
            _record_mode_guard_block(engine, mode=mode, reason=reason_code)
            return False, "AUDIT FAIL-CLOSED: trade decision log write failed"
        return True, ""

    def _deny(reason_code: str, user_reason: str) -> tuple[bool, str]:
        _record_mode_guard_block(engine, mode=mode, reason=reason_code)
        audit_ok, audit_reason = _audit_or_fail_closed(
            _build_audit_payload(
                engine,
                symbol=symbol,
                regime=str(regime),
                proposed_risk=float(proposed_risk),
                mode=mode,
                stage="policy_gate",
                final_decision="block",
                reason=str(user_reason),
            ),
        )
        if not audit_ok:
            return False, f"{user_reason} | {audit_reason}"
        return False, user_reason

    allow_stale = os.getenv("LUMINA_ALLOW_STALE_CONTRACTS", "false").strip().lower() == "true"
    if capabilities.requires_live_broker:
        stale_contract = is_stale_contract_symbol(symbol)
        if stale_contract and not allow_stale:
            return _deny("stale_contract", f"Contract symbol stale/expired by calendar check: {symbol}")
        if stale_contract and allow_stale:
            _audit_stale_override(engine, symbol, mode)

        broker_ok, broker_reason = _broker_metadata_contract_allowed(engine, symbol)
        if not broker_ok:
            return _deny("broker_metadata_block", f"Contract blocked by broker metadata: {symbol} ({broker_reason})")

    risk_controller = getattr(engine, "risk_controller", None)
    if not risk_controller:
        return _deny("risk_controller_unavailable", "Risk controller not available")

    session_ok, session_reason = session_guard_allows_trading(engine)
    if not session_ok:
        session_guard = getattr(engine, "session_guard", None)
        next_open = session_guard.next_open() if (session_guard is not None and hasattr(session_guard, "next_open")) else None
        suffix = f" | next_open={next_open.isoformat()}" if next_open is not None else ""
        return _deny(f"session_{session_reason}", f"Session guard blocked order: {session_reason}{suffix}")

    snapshot = resolve_regime_snapshot(engine, regime)
    adaptive = snapshot.get("adaptive_policy", {}) if isinstance(snapshot, dict) else {}
    risk_controller.apply_regime_override(
        regime=str(snapshot.get("label", regime or "NEUTRAL")),
        risk_state=str(snapshot.get("risk_state", "NORMAL")),
        risk_multiplier=float(adaptive.get("risk_multiplier", 1.0) or 1.0),
        cooldown_after_streak=int(adaptive.get("cooldown_minutes", 30) or 30),
    )
    if hasattr(risk_controller, "record_regime_snapshot"):
        try:
            risk_controller.record_regime_snapshot(snapshot)
        except Exception:
            pass
    if hasattr(risk_controller, "record_regime_detector_history"):
        try:
            reasoning_service = getattr(engine, "reasoning_service", None)
            regime_detector = getattr(reasoning_service, "regime_detector", None)
            market_df = getattr(engine, "ohlc_1min", None)
            instrument = str(getattr(getattr(engine, "config", None), "instrument", symbol) or symbol)
            risk_controller.record_regime_detector_history(
                detector=regime_detector,
                market_df=market_df,
                instrument=instrument,
            )
        except Exception:
            pass

    # LIVING ORGANISM v51: explicit VaR/ES gate before final order admission.
    if hasattr(risk_controller, "check_var_es_pre_trade"):
        var_result = risk_controller.check_var_es_pre_trade(float(proposed_risk))
        var_ok = True
        var_reason = "VAR_ES gate skipped (legacy contract)"
        var_payload: dict[str, Any] = {}
        if isinstance(var_result, tuple):
            if len(var_result) >= 2:
                var_ok = bool(var_result[0])
                var_reason = str(var_result[1])
            if len(var_result) >= 3 and isinstance(var_result[2], dict):
                var_payload = dict(var_result[2])
            elif len(var_result) == 1:
                var_ok = bool(var_result[0])
                var_reason = "VAR_ES gate result missing reason"

        mc_ok = True
        mc_reason = "MC drawdown gate skipped (legacy contract)"
        mc_payload: dict[str, Any] = {}
        if hasattr(risk_controller, "check_monte_carlo_drawdown_pre_trade"):
            mc_result = risk_controller.check_monte_carlo_drawdown_pre_trade(float(proposed_risk))
            if isinstance(mc_result, tuple):
                if len(mc_result) >= 2:
                    mc_ok = bool(mc_result[0])
                    mc_reason = str(mc_result[1])
                if len(mc_result) >= 3 and isinstance(mc_result[2], dict):
                    mc_payload = dict(mc_result[2])

        audit_ok, audit_reason = _audit_or_fail_closed(
            _build_audit_payload(
                engine,
                symbol=symbol,
                regime=str(snapshot.get("label", regime)),
                proposed_risk=float(proposed_risk),
                mode=mode,
                stage="risk_gate",
                final_decision="allow" if (var_ok and mc_ok) else "block",
                reason=(str(var_reason) if not var_ok else str(mc_reason)),
                var_payload=var_payload,
                mc_payload=mc_payload,
            ),
        )
        if not audit_ok:
            return False, audit_reason

        if capabilities.risk_enforced and not bool(var_ok):
            return _deny("risk_var_es", str(var_reason))
        if capabilities.risk_enforced and not bool(mc_ok):
            return _deny("risk_mc_drawdown", str(mc_reason))
        if not capabilities.risk_enforced and not bool(var_ok):
            _safe_log_warning(
                engine,
                f"RISK_VAR_ES_ADVISORY,mode={mode},symbol={symbol},reason={var_reason}",
            )
        if not capabilities.risk_enforced and not bool(mc_ok):
            _safe_log_warning(
                engine,
                f"RISK_MC_DRAWDOWN_ADVISORY,mode={mode},symbol={symbol},reason={mc_reason}",
            )

    risk_ok, risk_reason = risk_controller.check_can_trade(symbol, str(snapshot.get("label", regime)), proposed_risk)
    if capabilities.risk_enforced:
        if not bool(risk_ok):
            return _deny(f"risk_{risk_reason}", str(risk_reason))
        audit_ok, audit_reason = _audit_or_fail_closed(
            _build_audit_payload(
                engine,
                symbol=symbol,
                regime=str(snapshot.get("label", regime)),
                proposed_risk=float(proposed_risk),
                mode=mode,
                stage="policy_gate",
                final_decision="allow",
                reason=str(risk_reason),
            ),
        )
        if not audit_ok:
            return False, audit_reason
        return True, str(risk_reason)

    # Advisory mode (SIM): keep learning path unconstrained while retaining diagnostics.
    if not bool(risk_ok):
        _safe_log_warning(
            engine,
            f"RISK_ADVISORY,mode={mode},symbol={symbol},reason={risk_reason}",
        )
    _audit_or_fail_closed(
        _build_audit_payload(
            engine,
            symbol=symbol,
            regime=str(snapshot.get("label", regime)),
            proposed_risk=float(proposed_risk),
            mode=mode,
            stage="policy_gate",
            final_decision="allow",
            reason=str(risk_reason),
        ),
    )
    return True, str(risk_reason)
