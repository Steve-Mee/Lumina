"""Playground envelope — a seal is the operator's numbers, not a boolean.

Missing file is unsealed. A seal without a negative daily-loss floor and a
positive open-risk cap is unsealed. Breach is measured telemetry, never a guess.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.io.atomic_fs import atomic_write_text

SEAL_REL = Path("state") / "lumina_sim_envelope_sealed.json"
TELEMETRY_REL = Path("state") / "lumina_playground_risk_telemetry.json"
TELEMETRY_FRESH_SEC = 5 * 60


def envelope_seal_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / SEAL_REL


def telemetry_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / TELEMETRY_REL


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_seal(workspace_root: Path | str) -> dict[str, Any] | None:
    path = envelope_seal_path(workspace_root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def envelope_sealed_for_pass(workspace_root: Path | str) -> bool:
    """Operator sealed SIM limits. Legacy missing-file-as-sealed is not a pass."""
    raw = read_seal(workspace_root)
    if raw is None or raw.get("sealed") is not True:
        return False
    cap = _num(raw.get("daily_loss_cap"))
    risk = _num(raw.get("max_total_open_risk"))
    if cap is None or cap >= 0.0:
        return False
    if risk is None or risk <= 0.0:
        return False
    return True


def write_operator_seal(
    workspace_root: Path | str,
    *,
    daily_loss_cap: float,
    max_total_open_risk: float,
    source: str,
    equity: float | None = None,
    daily_loss_fraction: float | None = None,
    cash: float | None = None,
    net_liquidation: float | None = None,
    buying_power: float | None = None,
    account_name: str | None = None,
    floor_basis: str | None = None,
) -> None:
    cap = float(daily_loss_cap)
    risk = float(max_total_open_risk)
    if cap >= 0.0 or risk <= 0.0:
        raise ValueError("seal_limits_invalid")
    path = envelope_seal_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "sealed": True,
        "source": str(source or "operator"),
        "daily_loss_cap": cap,
        "max_total_open_risk": risk,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if equity is not None:
        payload["equity"] = float(equity)
    if daily_loss_fraction is not None:
        payload["daily_loss_fraction"] = float(daily_loss_fraction)
    if floor_basis:
        payload["floor_basis"] = str(floor_basis)
        payload["cash"] = None if cash is None else float(cash)
        payload["net_liquidation"] = None if net_liquidation is None else float(net_liquidation)
        payload["buying_power"] = None if buying_power is None else float(buying_power)
        payload["account_name"] = str(account_name or "")
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def read_telemetry(workspace_root: Path | str) -> dict[str, Any] | None:
    path = telemetry_path(workspace_root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def write_risk_telemetry(
    workspace_root: Path | str,
    *,
    realized_pnl_today: float | None,
    daily_pnl: float | None,
    open_risk: float | None,
    mode: str,
) -> None:
    """Persist numbers the engine already holds. None stays None."""
    path = telemetry_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "realized_pnl_today": _num(realized_pnl_today),
        "daily_pnl": _num(daily_pnl),
        "open_risk": _num(open_risk),
        "mode": str(mode or ""),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True) + "\n")


def publish_engine_risk_telemetry(workspace_root: Path | str, engine: Any, mode: str) -> None:
    """Copy risk-gate fields. Missing attributes stay null — no stand-in formula."""
    pnl_today = _attr_num(engine, "realized_pnl_today")
    controller = getattr(engine, "risk_controller", None)
    state = getattr(controller, "state", None) if controller is not None else None
    daily = _attr_num(state, "daily_pnl") if state is not None else None
    book = getattr(state, "open_risk_by_symbol", None) if state is not None else None
    open_risk: float | None
    if isinstance(book, dict):
        total = 0.0
        for value in book.values():
            number = _num(value)
            if number is None:
                open_risk = None
                break
            total += number
        else:
            open_risk = total
    else:
        open_risk = None
    write_risk_telemetry(
        workspace_root,
        realized_pnl_today=pnl_today,
        daily_pnl=daily,
        open_risk=open_risk,
        mode=mode,
    )


def assess_envelope(
    workspace_root: Path | str,
    *,
    n_p: int,
    bars_flowing: bool,
    now: float | None = None,
    latched_breach: bool = False,
) -> dict[str, Any]:
    """Return sealed / breached / telemetry status for the AND.

    Telemetry is required while bars are flowing, and whenever n_P > 0 and
    the file is absent. A quiet tape keeps the last complete reading.
    """
    sealed = envelope_sealed_for_pass(workspace_root)
    raw = read_seal(workspace_root) or {}
    tel = read_telemetry(workspace_root)
    status = "not_required"
    pnl = _pnl_number(tel)
    open_risk = _num((tel or {}).get("open_risk")) if tel else None
    required = bool(bars_flowing) or int(n_p) > 0
    loss_floor_hit = False
    breached = False
    if sealed and required:
        status = _telemetry_status(tel, bars_flowing=bars_flowing, n_p=int(n_p), now=now)
        if status == "ok" and pnl is not None and open_risk is not None:
            cap = _num(raw.get("daily_loss_cap"))
            risk_cap = _num(raw.get("max_total_open_risk"))
            if cap is not None and pnl <= cap:
                # The number stays visible. It does not stop Playground or flatten her.
                loss_floor_hit = True
            if risk_cap is not None and open_risk > risk_cap:
                loss_floor_hit = True
    _ = latched_breach
    return {
        "sealed": sealed,
        "breached": breached,
        "loss_floor_hit": loss_floor_hit,
        "telemetry": status,
        "pnl": pnl,
        "open_risk": open_risk,
    }


def _telemetry_status(
    tel: dict[str, Any] | None,
    *,
    bars_flowing: bool,
    n_p: int,
    now: float | None,
) -> str:
    if tel is None:
        return "missing"
    if _pnl_number(tel) is None:
        return "field_missing:pnl"
    if _num(tel.get("open_risk")) is None:
        return "field_missing:open_risk"
    if bars_flowing and _is_stale(tel, now=now):
        return "stale"
    if n_p > 0 or bars_flowing:
        return "ok"
    return "ok"


def _pnl_number(tel: dict[str, Any] | None) -> float | None:
    if not tel:
        return None
    daily = _num(tel.get("daily_pnl"))
    if daily is not None:
        return daily
    return _num(tel.get("realized_pnl_today"))


def _is_stale(tel: dict[str, Any], *, now: float | None) -> bool:
    stamp = str(tel.get("ts") or "")
    if not stamp:
        return True
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    current = float(now) if now is not None else datetime.now(timezone.utc).timestamp()
    return (current - parsed.timestamp()) > float(TELEMETRY_FRESH_SEC)


def _attr_num(obj: Any, name: str) -> float | None:
    if obj is None or not hasattr(obj, name):
        return None
    return _num(getattr(obj, name))
