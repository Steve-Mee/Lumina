"""Honest Playground fills — orderpath only. JSON / health / milestones are not fills."""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from lumina_core.maturity.playground.tape import append_tape_row, load_tape_rows

logger = logging.getLogger(__name__)

ORDERPATH_SOURCES = frozenset({"orderpath", "ops_place_order", "venue_fill"})
SIM_MODES = frozenset({"sim", "sim_real_guard"})
JSON_STAMP = Path("state") / "first_sim_order.json"


def record_orderpath_fill(
    workspace_root: Path | str,
    *,
    order_id: str,
    fill_px: float,
    qty: int,
    instrument: str,
    mode: str,
    source: str,
    kind: str = "fill",
    policy: bool = True,
    r: float | None = None,
    win: bool | None = None,
) -> dict[str, Any]:
    """Append a venue fill. Refuse JSON stamps, health flags, and non-SIM modes."""
    src = str(source or "").strip()
    if src not in ORDERPATH_SOURCES:
        return {"ok": False, "reason": "source_not_orderpath", "source": src}
    trade_mode = str(mode or "").strip().lower()
    if trade_mode not in SIM_MODES:
        return {"ok": False, "reason": "mode_not_sim", "mode": trade_mode}
    oid = str(order_id or "").strip()
    if not oid:
        return {"ok": False, "reason": "order_id_missing"}
    try:
        px = float(fill_px)
    except (TypeError, ValueError):
        return {"ok": False, "reason": "fill_px_invalid"}
    if px <= 0.0:
        return {"ok": False, "reason": "fill_px_invalid"}
    q = int(qty)
    if q <= 0:
        return {"ok": False, "reason": "qty_invalid"}
    row = {
        "kind": str(kind or "fill"),
        "order_id": oid,
        "fill_px": px,
        "qty": q,
        "instrument": str(instrument or "").strip(),
        "mode": trade_mode,
        "source": src,
        "policy": bool(policy),
        "r": r,
        "win": win,
    }
    append_tape_row(workspace_root, row)
    return {"ok": True, "row": row}


def record_policy_close(
    workspace_root: Path | str,
    *,
    order_id: str,
    entry_px: float,
    exit_px: float,
    stop_px: float,
    side: int,
    qty: int,
    instrument: str,
    mode: str,
    source: str,
    target_px: float | None = None,
    ts: str | None = None,
    rule_name: str | None = None,
    session_open_equity: float | None = None,
    session_close_equity: float | None = None,
) -> dict[str, Any]:
    """Append one policy close. Process-R is written only when stop, entry, and exit exist."""
    src = str(source or "").strip()
    if src not in ORDERPATH_SOURCES:
        return _refuse("source_not_orderpath", source=src)
    trade_mode = str(mode or "").strip().lower()
    if trade_mode not in SIM_MODES:
        return _refuse("mode_not_sim", mode=trade_mode)
    oid = str(order_id or "").strip()
    if not oid:
        return _refuse("order_id_missing")
    try:
        q = int(qty)
    except (TypeError, ValueError):
        return _refuse("qty_invalid")
    if q <= 0:
        return _refuse("qty_invalid")
    entry = _positive(entry_px)
    exit_px_ok = _positive(exit_px)
    stop = _positive(stop_px)
    try:
        held = int(side)
    except (TypeError, ValueError):
        held = 0
    if entry is None or exit_px_ok is None or stop is None or held == 0:
        return _refuse("r_inputs_missing")
    risk = abs(entry - stop)
    if not math.isfinite(risk) or risk <= 1e-12:
        return _refuse("r_inputs_missing")
    sign = 1.0 if held > 0 else -1.0
    trade_r = sign * (exit_px_ok - entry) / risk
    if not math.isfinite(trade_r):
        return _refuse("r_inputs_missing")
    row: dict[str, Any] = {
        "kind": "close",
        "order_id": oid,
        "rule_name": str(rule_name or ""),
        "fill_px": exit_px_ok,
        "entry_px": entry,
        "exit_px": exit_px_ok,
        "stop_px": stop,
        "side": held,
        "qty": q,
        "instrument": str(instrument or "").strip(),
        "mode": trade_mode,
        "source": src,
        "policy": True,
        "r": trade_r,
        "win": trade_r > 0.0,
    }
    target = _positive(target_px)
    if target is not None:
        row["target_px"] = target
    if ts:
        row["ts"] = str(ts)
    if session_open_equity is not None and session_close_equity is not None:
        row["session_open_equity"] = float(session_open_equity)
        row["session_close_equity"] = float(session_close_equity)
    try:
        written = append_tape_row(workspace_root, row)
    except OSError:
        logger.info("playground.fill.close_refused reason=tape_write_failed")
        return {"ok": False, "reason": "tape_write_failed"}
    if not written:
        return {"ok": True, "reason": "already_recorded"}
    return {"ok": True, "row": row}


def _positive(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _refuse(reason: str, **extra: Any) -> dict[str, Any]:
    logger.info("playground.fill.close_refused reason=%s", reason)
    payload: dict[str, Any] = {"ok": False, "reason": reason}
    payload.update(extra)
    return payload


def json_stamp_exists(workspace_root: Path | str) -> bool:
    return (Path(workspace_root) / JSON_STAMP).is_file()


def first_honest_fill(workspace_root: Path | str) -> dict[str, Any] | None:
    """First orderpath SIM fill on the playground tape. JSON stamps never qualify."""
    for row in load_tape_rows(workspace_root):
        src = str(row.get("source") or "")
        mode = str(row.get("mode") or "").lower()
        oid = str(row.get("order_id") or "").strip()
        if src in ORDERPATH_SOURCES and mode in SIM_MODES and oid:
            return dict(row)
    return None
