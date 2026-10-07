"""Apprenticeship SIM tape — policy-only closes. Playground tape and JSON stamps are not rows."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from lumina_core.birth.foundation_metrics import skill_winrate

TAPE_REL = Path("state") / "lumina_apprenticeship_tape.jsonl"
ORDERPATH_SOURCES = frozenset({"orderpath", "ops_place_order", "venue_fill"})
REQUIRED_MODE = "sim_real_guard"


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
    entry_px: float | None = None,
    stop_px: float | None = None,
    target_px: float | None = None,
    risk_event: bool = False,
    var_breach: bool = False,
    daily_kill: bool = False,
) -> dict[str, Any]:
    """Append a venue fill. Refuse JSON stamps, health flags, Playground `sim`, and REAL."""
    src = str(source or "").strip()
    if src not in ORDERPATH_SOURCES:
        return {"ok": False, "reason": "source_not_orderpath", "source": src}
    trade_mode = str(mode or "").strip().lower()
    if trade_mode != REQUIRED_MODE:
        return {"ok": False, "reason": "mode_not_sim_real_guard", "mode": trade_mode}
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
    if entry_px is not None:
        row["entry_px"] = float(entry_px)
    if stop_px is not None:
        row["stop_px"] = float(stop_px)
    if target_px is not None:
        row["target_px"] = float(target_px)
    append_tape_row(workspace_root, row)
    return {"ok": True, "row": row}


def tape_breakeven_wr(workspace_root: Path | str) -> tuple[float | None, str]:
    """BE from the stops and targets on this tape. No fallback and no Playground tape."""
    from lumina_core.birth.birth_trade_geometry import economics_after_cost

    closes = [r for r in load_tape_rows(workspace_root) if _is_policy_close(r)]
    if not closes:
        return None, "no_closes"
    geos: list[tuple[float, float, float]] = []
    for row in closes:
        entry = _f(row.get("entry_px"))
        stop = _f(row.get("stop_px"))
        target = _f(row.get("target_px"))
        if entry is None or stop is None or target is None or entry <= 0.0:
            return None, "geometry_incomplete"
        geos.append((abs(entry - stop) / entry, abs(target - entry) / entry, entry))
    stop_pct = float(median(item[0] for item in geos))
    target_pct = float(median(item[1] for item in geos))
    price = float(median(item[2] for item in geos))
    if stop_pct <= 0.0 or target_pct <= 0.0:
        return None, "geometry_incomplete"
    from lumina_core.market.nt_fees import CostCardError, contract_root

    roots: set[str] = set()
    for row in closes:
        try:
            roots.add(contract_root(str(row.get("instrument") or "")))
        except CostCardError:
            return None, "cost_root_unknown"
    if len(roots) != 1:
        return None, "cost_root_unknown"
    _win, _loss, _rr, be_wr, _cost = economics_after_cost(
        stop_pct,
        target_pct,
        price=price,
        instrument=next(iter(roots)),
    )
    return float(be_wr), "tape"


def tape_skill_metrics(workspace_root: Path | str) -> dict[str, Any]:
    """n_A / WR / mean R / process-R from policy closes only."""
    rows = load_tape_rows(workspace_root)
    policy_closes = [r for r in rows if _is_policy_close(r)]
    plant_closes = [r for r in rows if _is_close(r) and not _is_policy(r)]
    r_series = [_f(r.get("r")) for r in policy_closes]
    r_ok = [x for x in r_series if x is not None]
    losses = [abs(x) for x in r_ok if x < 0]
    wins = sum(1 for r in policy_closes if bool(r.get("win")) or (_f(r.get("r")) or 0.0) > 0.0)
    n_a = len(policy_closes)
    mean_r = (sum(r_ok) / float(len(r_ok))) if r_ok else None
    median_loss = float(median(losses)) if losses else (0.0 if n_a > 0 else None)
    return {
        "n_a": n_a,
        "n_plant": len(plant_closes),
        "skill_wr": None if n_a <= 0 else skill_winrate(trades=n_a, wins=wins),
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
