"""Build risk fortress snapshot for core WebSocket telemetry."""

from __future__ import annotations

from typing import Any

DEFAULT_DRAWDOWN_KILL_PCT = 8.0


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _compute_drawdown_pct(account_balance: float, account_equity: float) -> float | None:
    if account_balance <= 0:
        return None
    drawdown = max(0.0, (account_balance - account_equity) / account_balance * 100.0)
    return round(drawdown, 4)


def build_fortress_block(
    *,
    runtime: dict[str, Any],
    sim_state: dict[str, Any],
    obs_snapshot: dict[str, Any],
    kill_switch_metric_fn: Any,
) -> dict[str, Any] | None:
    has_runtime = bool(runtime)
    has_sim = bool(sim_state)
    if not has_runtime and not has_sim:
        return None

    snapshot = sim_state.get("state_snapshot") if isinstance(sim_state.get("state_snapshot"), dict) else {}
    risk_snap = snapshot.get("risk") if isinstance(snapshot.get("risk"), dict) else {}

    account_equity = _coerce_float(runtime.get("account_equity"), _coerce_float(risk_snap.get("account_equity")))
    account_balance = _coerce_float(runtime.get("account_balance"))

    drawdown_pct = _coerce_float(runtime.get("drawdown_pct"))
    if drawdown_pct is None and account_balance is not None and account_equity is not None:
        drawdown_pct = _compute_drawdown_pct(account_balance, account_equity)

    mc_drawdown_pct = _coerce_float(runtime.get("mc_drawdown_pct"))
    drawdown_kill_pct = _coerce_float(
        runtime.get("drawdown_kill_pct"),
        DEFAULT_DRAWDOWN_KILL_PCT,
    ) or DEFAULT_DRAWDOWN_KILL_PCT

    kill_switch_active = False
    if obs_snapshot:
        kill_switch = kill_switch_metric_fn(obs_snapshot, "lumina_risk_kill_switch_active", 0.0)
        kill_switch_active = float(kill_switch) >= 1.0

    pending_reconciliations = _coerce_int(
        runtime.get("pending_reconciliations"),
        _coerce_int(risk_snap.get("pending_reconciliations")),
    )

    return {
        "drawdown_pct": drawdown_pct,
        "drawdown_kill_pct": drawdown_kill_pct,
        "kill_switch_active": kill_switch_active,
        "mc_drawdown_pct": mc_drawdown_pct,
        "pending_reconciliations": pending_reconciliations,
    }
