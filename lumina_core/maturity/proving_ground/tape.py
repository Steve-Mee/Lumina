"""Proving Ground SIM tape — policy-only closes. Other phase tapes are not rows."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from lumina_core.birth.foundation_metrics import skill_winrate

TAPE_REL = Path("state") / "lumina_proving_ground_tape.jsonl"
ORDERPATH_SOURCES = frozenset({"orderpath", "ops_place_order", "venue_fill"})
SIM_MODES = frozenset({"sim", "sim_real_guard"})


def tape_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / TAPE_REL


def load_tape_rows(workspace_root: Path | str) -> list[dict[str, Any]]:
    path = tape_path(workspace_root)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except ValueError:
            continue
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def append_tape_row(workspace_root: Path | str, row: dict[str, Any]) -> None:
    path = tape_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


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
    pnl: float | None = None,
    session_date: str | None = None,
    risk_event: bool = False,
    var_breach: bool = False,
    daily_kill: bool = False,
    fill_rate: float | None = None,
    slippage: float | None = None,
) -> dict[str, Any]:
    """Append a venue fill. Refuse JSON stamps, health flags, and REAL."""
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
    row: dict[str, Any] = {
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
        "pnl": pnl,
        "risk_event": bool(risk_event),
        "var_breach": bool(var_breach),
        "daily_kill": bool(daily_kill),
    }
    if session_date:
        row["session_date"] = str(session_date)[:10]
    if fill_rate is not None:
        row["fill_rate"] = float(fill_rate)
    if slippage is not None:
        row["slippage"] = float(slippage)
    append_tape_row(workspace_root, row)
    return {"ok": True, "row": row}


def tape_skill_metrics(workspace_root: Path | str) -> dict[str, Any]:
    """n_G / WR / mean R / process-R from policy closes only."""
    rows = load_tape_rows(workspace_root)
    policy_closes = [r for r in rows if _is_policy_close(r)]
    plant_closes = [r for r in rows if _is_close(r) and not _is_policy(r)]
    r_series = [_f(r.get("r")) for r in policy_closes]
    r_ok = [x for x in r_series if x is not None]
    losses = [abs(x) for x in r_ok if x < 0]
    wins = sum(1 for r in policy_closes if bool(r.get("win")) or (_f(r.get("r")) or 0.0) > 0.0)
    n_g = len(policy_closes)
    mean_r = (sum(r_ok) / float(len(r_ok))) if r_ok else None
    median_loss = float(median(losses)) if losses else (0.0 if n_g > 0 else None)
    return {
        "n_g": n_g,
        "n_plant": len(plant_closes),
        "skill_wr": None if n_g <= 0 else skill_winrate(trades=n_g, wins=wins),
        "mean_r": mean_r,
        "median_loss_r": median_loss,
        "policy_only": True,
        "has_orderpath_fill": any(_is_orderpath(r) for r in rows),
    }


def _is_close(row: dict[str, Any]) -> bool:
    return str(row.get("kind") or "") == "close"


def _is_policy(row: dict[str, Any]) -> bool:
    return bool(row.get("policy"))


def _is_policy_close(row: dict[str, Any]) -> bool:
    return _is_close(row) and _is_policy(row)


def _is_orderpath(row: dict[str, Any]) -> bool:
    return str(row.get("source") or "") in ORDERPATH_SOURCES


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
