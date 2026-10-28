"""H-halt and H-carry across the Globex halt. Shadows only. No tape. No invented price.

H-halt flattens at the last real price when the book shuts.
H-carry stays open and uses the first print after the reopen.
A gap through the stop is a stop. A gap through the target is a target.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.market.globex_hours import globex_status, parse_instant
from lumina_core.maturity.playground.journal import append_experiment_entry
from lumina_core.maturity.playground.sense_lab import load_sense, net_r_after_cost, save_sense

_NOTE = (
    "Globex calendar, America/New_York. Sunday 18:00 ET to Friday 17:00 ET. "
    "Monday-Thursday 17:00-18:00 ET is the halt. 17:00 is closed. 18:00 is open. "
    "H-halt flattens at the last real price. H-carry waits for the first print after the reopen. "
    "Neither writes the tape. "
    "Do not re-test: orders during the halt, invented prices, scoring the halt as a stall, "
    "scoring Saturday as a red day, or using the 16:59 price as a fill at 17:30."
)


def note_globex_once(workspace_root: Path | str) -> None:
    root = Path(workspace_root)
    state = load_sense(root)
    if state.get("globex_noted"):
        return
    append_experiment_entry(root, title="globex calendar", lines=[_NOTE])
    state["globex_noted"] = True
    save_sense(root, state)


def on_clock(workspace_root: Path | str, *, now: datetime | None = None) -> None:
    """Flatten when the book is shut. Carry only if the account allows overnight."""
    from lumina_core.maturity.playground.session_flat import overnight_allowed

    root = Path(workspace_root)
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        return
    state = load_sense(root)
    if globex_status(moment) == "open":
        return
    if _flatten_halt(state, keep_carry=overnight_allowed(root)):
        save_sense(root, state)


def on_bar(state: dict[str, Any], *, ts: str, px: float) -> None:
    """A closed-book print does not resolve H-carry. The first open print can."""
    instant = parse_instant(ts)
    if instant is None:
        return
    try:
        status = globex_status(instant)
    except ValueError:
        return
    if status != "open":
        _flatten_halt(state, keep_carry=False)
        return
    _resolve_carry(state, px)


def _flatten_halt(state: dict[str, Any], *, keep_carry: bool = False) -> bool:
    if state.get("halt_flat_done"):
        return False
    closes = list(state.get("closes") or [])
    if not closes:
        state["halt_flat_done"] = True
        state["carry"] = []
        return True
    try:
        last_px = float(closes[-1].get("px") or 0.0)
    except (TypeError, ValueError):
        last_px = 0.0
    if last_px <= 0.0:
        return False
    resolved = list(state.get("resolved") or [])
    carry: list[dict[str, Any]] = []
    for row in list(state.get("open") or []):
        scored = net_r_after_cost(
            entry=float(row["entry"]),
            exit_px=last_px,
            side=int(row["side"]),
            stop_pct=float(row["stop_pct"]),
        )
        if scored is None:
            continue
        resolved.append({"name": "h_halt", "r": float(scored), "win": scored > 0.0, "reason": "halt_flat"})
        if keep_carry:
            carried = dict(row)
            carried["name"] = "h_carry"
            carry.append(carried)
    state["resolved"] = resolved[-800:]
    state["carry"] = carry
    state["halt_flat_done"] = True
    return True


def _resolve_carry(state: dict[str, Any], px: float) -> None:
    carry = list(state.get("carry") or [])
    if not carry or not state.get("halt_flat_done"):
        return
    resolved = list(state.get("resolved") or [])
    still: list[dict[str, Any]] = []
    for row in carry:
        done = _gap_outcome(row, px)
        if done is None:
            still.append(row)
            continue
        resolved.append(done)
    state["carry"] = still
    state["resolved"] = resolved[-800:]
    if not still:
        state["halt_flat_done"] = False


def _gap_outcome(row: dict[str, Any], px: float) -> dict[str, Any] | None:
    entry = float(row["entry"])
    side = int(row["side"])
    stop = float(row["stop_pct"])
    target = float(row["target_pct"])
    if entry <= 0.0 or px <= 0.0 or side == 0:
        return None
    ret = ((px - entry) / entry) * float(side)
    if ret <= -stop:
        exit_px = entry * (1.0 - float(side) * stop)
        reason = "stop"
    elif ret >= target:
        exit_px = entry * (1.0 + float(side) * target)
        reason = "target"
    else:
        return None
    scored = net_r_after_cost(entry=entry, exit_px=exit_px, side=side, stop_pct=stop)
    if scored is None:
        return None
    return {"name": "h_carry", "r": float(scored), "win": scored > 0.0, "reason": reason}
