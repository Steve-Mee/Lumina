"""Playground SIM tape — policy-only closes. JSON stamps are not rows."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from statistics import median

from lumina_core.birth.birth_trade_geometry import economics_after_cost
from lumina_core.birth.foundation_metrics import skill_winrate

TAPE_REL = Path("state") / "lumina_playground_tape.jsonl"


def tape_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / TAPE_REL


def load_tape_rows(workspace_root: Path | str) -> list[dict[str, Any]]:
    path = tape_path(workspace_root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
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


def append_tape_row(workspace_root: Path | str, row: dict[str, Any]) -> bool:
    """Append one row. Refuses a missing order_id. Duplicate order_id+kind is a no-op."""
    oid = str(row.get("order_id") or "").strip()
    if not oid:
        raise ValueError("order_id_missing")
    kind = str(row.get("kind") or "")
    if _row_exists(workspace_root, order_id=oid, kind=kind):
        return False
    path = tape_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload["order_id"] = oid
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return True


def _row_exists(workspace_root: Path | str, *, order_id: str, kind: str) -> bool:
    for row in load_tape_rows(workspace_root):
        if str(row.get("order_id") or "") == order_id and str(row.get("kind") or "") == kind:
            return True
    return False


def tape_skill_metrics(workspace_root: Path | str) -> dict[str, Any]:
    """n_P / WR / mean R / process-R from policy closes only."""
    rows = load_tape_rows(workspace_root)
    policy_closes = [r for r in rows if _is_policy_close(r)]
    plant_closes = [r for r in rows if _is_close(r) and not _is_policy(r)]
    fills = [r for r in rows if str(r.get("kind") or "") in {"fill", "close", "entry"}]
    r_series = [_f(r.get("r")) for r in policy_closes]
    r_complete = bool(policy_closes) and all(x is not None for x in r_series)
    r_ok = [x for x in r_series if x is not None]
    losses = [abs(x) for x in r_ok if x < 0]
    wins = sum(1 for r in policy_closes if bool(r.get("win")) or (_f(r.get("r")) or 0.0) > 0.0)
    n_p = len(policy_closes)
    if not r_complete:
        mean_r = None
        median_loss = None
    else:
        mean_r = sum(r_ok) / float(len(r_ok))
        median_loss = float(median(losses)) if losses else 0.0
    return {
        "n_p": n_p,
        "n_plant": len(plant_closes),
        "n_fills": len(fills),
        "skill_wr": None if n_p <= 0 else skill_winrate(trades=n_p, wins=wins),
        "mean_r": mean_r,
        "median_loss_r": median_loss,
        "policy_only": len(plant_closes) == 0,
        "has_orderpath_fill": any(_is_orderpath(r) for r in rows),
    }


def tape_breakeven_wr(workspace_root: Path | str) -> tuple[float | None, str]:
    """BE from the stops and targets that actually closed. No fallback."""
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


def last_policy_close(workspace_root: Path | str) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    for row in load_tape_rows(workspace_root):
        if _is_policy_close(row):
            found = row
    return found


def _is_close(row: dict[str, Any]) -> bool:
    return str(row.get("kind") or "") == "close"


def _is_policy(row: dict[str, Any]) -> bool:
    return bool(row.get("policy"))


def _is_policy_close(row: dict[str, Any]) -> bool:
    return _is_close(row) and _is_policy(row)


def _is_orderpath(row: dict[str, Any]) -> bool:
    return str(row.get("source") or "") in {"orderpath", "ops_place_order", "venue_fill"}


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
