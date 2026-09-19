"""Honest Playground fills — orderpath only. JSON / health / milestones are not fills."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.maturity.playground.tape import append_tape_row, load_tape_rows

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
