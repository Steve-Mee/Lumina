"""Sense lab — counterfactual shadows. No place_order. No playground tape. No n_P.

Hypotheses are pre-registered. A green shadow is not a pass and does not
replace the Awakening crawler. Always-flat realizes R = 0 because it does
not trade. First-touch uses Birth stop/target on both sides.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_trade_geometry import (
    MES_POINT_VALUE_USD,
    estimate_round_trip_cost_usd,
)
from lumina_core.io.atomic_fs import atomic_write_text
from lumina_core.maturity.playground.journal import append_experiment_entry
from lumina_core.maturity.playground.sense_candles import (
    exchange_session_key,
    slope_from_closes,
    slope_sign,
)

SENSE_REL = Path("state") / "lumina_playground_sense.json"
ALL_FLAT_BARS = 500
REPORT_MIN = 30
SCHEMA = "playground_sense_v1"

HYPOTHESIS_TEXT = (
    "Pre-registered. Entry uses only closed 5/60/240-minute candles. "
    "The forming bucket is not a feature. Clock is America/Chicago. "
    "H1: sign(closed 5m) == sign(closed 60m), both non-zero, and sign(closed 240m) "
    "is known and not opposite. Side is that shared sign. "
    "H2: sign(closed 5m) and sign(closed 60m) are non-zero and different. "
    "Side fades the 5m sign. "
    "Null A always-flat: no shadow, realized R is 0. "
    "Null B first-touch: long and short from the same close, Birth stop and target, "
    "resolved only on later closes. "
    "One open shadow per name. Shadows do not call place_order and do not write the tape. "
    "MEASURED is not a pass. The crawler stays the Awakening child."
)


def sense_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / SENSE_REL


def save_sense(workspace_root: Path | str, state: dict[str, Any]) -> None:
    _save(Path(workspace_root), state)


def load_sense(workspace_root: Path | str) -> dict[str, Any]:
    path = sense_path(workspace_root)
    if not path.is_file():
        return _empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    base = _empty()
    base.update(raw)
    return base


def load_birth_geometry(workspace_root: Path | str) -> dict[str, float] | None:
    """Stop, target, and hold from the frozen Birth progress. Missing is None."""
    path = Path(workspace_root) / "state" / "lumina_birth_progress.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        stop = float(raw.get("birth_trade_stop_pct"))
        target = float(raw.get("birth_trade_target_pct"))
        hold = int(raw.get("geometry_hold_bars"))
    except (TypeError, ValueError):
        return None
    if stop <= 0.0 or target <= stop or hold < 20:
        return None
    return {"stop_pct": stop, "target_pct": target, "hold_bars": hold}


def observe_closed_bar(
    workspace_root: Path | str,
    *,
    ts: str,
    close: float,
    decision: dict[str, Any] | None = None,
    geometry: dict[str, float] | None = None,
    native_htf: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    """Append one closed minute. Open shadows only when this bar was a policy decision."""
    root = Path(workspace_root)
    state = load_sense(root)
    try:
        px = float(close)
    except (TypeError, ValueError):
        return state
    if px <= 0.0:
        return state
    session = exchange_session_key(ts)
    if session is None:
        return state
    _flush_if_new_session(root, state, session)
    from lumina_core.maturity.playground.globex_gap import on_bar

    on_bar(state, ts=str(ts), px=px)
    closes = list(state.get("closes") or [])
    closes.append({"ts": str(ts), "px": px})
    state["closes"] = closes
    _resolve_open(state, px)
    if native_htf is not None:
        state["nt_htf"] = dict(native_htf)
    if decision is not None:
        _note_decision(root, state, decision, px, geometry)
    _save(root, state)
    return state


def net_r_after_cost(*, entry: float, exit_px: float, side: int, stop_pct: float) -> float | None:
    """Process-R minus round-trip cost in R units. Same cost function as Birth."""
    if int(side) == 0 or float(entry) <= 0.0 or float(stop_pct) <= 0.0:
        return None
    risk = float(entry) * float(stop_pct)
    risk_usd = risk * float(MES_POINT_VALUE_USD)
    if risk_usd <= 1e-12:
        return None
    gross = (1.0 if int(side) > 0 else -1.0) * (float(exit_px) - float(entry)) / risk
    cost = estimate_round_trip_cost_usd(price=float(entry))
    return float(gross - (cost / risk_usd))


def summarize_book(resolved: list[dict[str, Any]]) -> dict[str, Any]:
    """Reporting threshold is not a pass floor. pass_now stays false."""
    names = ("null_a", "null_b", "h1", "h2")
    rows = {name: _name_summary(resolved, name) for name in names}
    rows["null_a"] = {
        "name": "null_a",
        "n": 0,
        "mean_r": 0.0,
        "wr": None,
        "verdict": "FLAT_R0",
        "note": "no position, realized R is 0",
    }
    return {"pass_now": False, "names": rows}


def _note_decision(
    root: Path,
    state: dict[str, Any],
    decision: dict[str, Any],
    px: float,
    geometry: dict[str, float] | None,
) -> None:
    try:
        side = int(decision.get("side"))
    except (TypeError, ValueError):
        return
    action = decision.get("action0")
    state["decision_bars"] = int(state.get("decision_bars") or 0) + 1
    if side == 0:
        state["flat_bars"] = int(state.get("flat_bars") or 0) + 1
    if action is not None:
        try:
            state["last_action0"] = float(action)
        except (TypeError, ValueError):
            pass
    geo = geometry if geometry is not None else load_birth_geometry(root)
    if geo is None:
        state["geometry"] = "missing"
    else:
        state["geometry"] = "birth_progress"
        _open_shadows(state, px, geo)
    decisions = int(state["decision_bars"])
    flats = int(state.get("flat_bars") or 0)
    if decisions >= ALL_FLAT_BARS and flats == decisions and not state.get("all_flat_journaled"):
        append_experiment_entry(
            root,
            title="all_flat",
            lines=[
                f"Fresh decision bars: {decisions}. Policy side was 0 on every one.",
                "n_P was not changed. This is not a stall and not a pass.",
                "The phase stays incomplete. No wipe.",
                "Do not re-test: forcing a buy because action0 sits under 0.5, "
                "or sampling the stochastic policy to manufacture a fill.",
            ],
        )
        state["all_flat_journaled"] = True


def _open_shadows(state: dict[str, Any], px: float, geo: dict[str, float]) -> None:
    closes = list(state.get("closes") or [])
    if isinstance(state.get("nt_htf"), dict):
        native = state["nt_htf"]
        sign5 = slope_from_closes(list(native.get("5m") or []))
        sign60 = slope_from_closes(list(native.get("60m") or []))
        sign240 = slope_from_closes(list(native.get("240m") or []))
    else:
        sign5 = slope_sign(closes, span_min=5)
        sign60 = slope_sign(closes, span_min=60)
        sign240 = slope_sign(closes, span_min=240)
    state["signs"] = {"m5": sign5, "m60": sign60, "m240": sign240}
    entry_i = len(closes) - 1
    if sign5 is not None and sign60 is not None and sign5 == sign60 and sign240 not in (None, -sign5):
        _open_one(state, name="h1", side=int(sign5), px=px, entry_i=entry_i, geo=geo)
    if sign5 is not None and sign60 is not None and sign5 != sign60:
        _open_one(state, name="h2", side=-int(sign5), px=px, entry_i=entry_i, geo=geo)
    _open_one(state, name="null_b_long", side=1, px=px, entry_i=entry_i, geo=geo)
    _open_one(state, name="null_b_short", side=-1, px=px, entry_i=entry_i, geo=geo)


def _open_one(
    state: dict[str, Any],
    *,
    name: str,
    side: int,
    px: float,
    entry_i: int,
    geo: dict[str, float],
) -> None:
    book_name = "null_b" if name.startswith("null_b") else name
    open_rows = list(state.get("open") or [])
    if any(str(row.get("name")) == book_name and int(row.get("leg") or 0) == int(side) for row in open_rows):
        return
    if book_name != "null_b" and any(str(row.get("name")) == book_name for row in open_rows):
        return
    open_rows.append(
        {
            "name": book_name,
            "leg": int(side),
            "side": int(side),
            "entry": float(px),
            "entry_i": int(entry_i),
            "stop_pct": float(geo["stop_pct"]),
            "target_pct": float(geo["target_pct"]),
            "hold": int(geo["hold_bars"]),
        }
    )
    state["open"] = open_rows


def _resolve_open(state: dict[str, Any], px: float) -> None:
    closes = list(state.get("closes") or [])
    index = len(closes) - 1
    still: list[dict[str, Any]] = []
    resolved = list(state.get("resolved") or [])
    for row in list(state.get("open") or []):
        done = _outcome(row, px, index)
        if done is None:
            still.append(row)
            continue
        resolved.append(done)
    state["open"] = still
    state["resolved"] = resolved[-800:]


def _outcome(row: dict[str, Any], px: float, index: int) -> dict[str, Any] | None:
    entry = float(row["entry"])
    side = int(row["side"])
    stop = float(row["stop_pct"])
    target = float(row["target_pct"])
    held = int(index) - int(row["entry_i"])
    if held <= 0 or entry <= 0.0:
        return None
    ret = ((px - entry) / entry) * float(side)
    if ret <= -stop:
        exit_px = entry * (1.0 - float(side) * stop)
        reason = "stop"
    elif ret >= target:
        exit_px = entry * (1.0 + float(side) * target)
        reason = "target"
    elif held >= int(row["hold"]):
        exit_px = px
        reason = "time"
    else:
        return None
    scored = net_r_after_cost(entry=entry, exit_px=exit_px, side=side, stop_pct=stop)
    if scored is None:
        return None
    return {"name": str(row["name"]), "r": float(scored), "win": scored > 0.0, "reason": reason}


def _name_summary(resolved: list[dict[str, Any]], name: str) -> dict[str, Any]:
    rows = [row for row in resolved if str(row.get("name")) == name and row.get("r") is not None]
    n = len(rows)
    if n <= 0:
        return {"name": name, "n": 0, "mean_r": None, "wr": None, "verdict": "INCONCLUSIVE"}
    mean = sum(float(row["r"]) for row in rows) / float(n)
    wins = sum(1 for row in rows if float(row["r"]) > 0.0)
    verdict = "INCONCLUSIVE" if n < REPORT_MIN else "MEASURED"
    return {
        "name": name,
        "n": n,
        "mean_r": float(mean),
        "wr": wins / float(n),
        "verdict": verdict,
    }


def _flush_if_new_session(root: Path, state: dict[str, Any], session: str) -> None:
    previous = str(state.get("session_key") or "")
    if previous and previous != session:
        _write_session(root, state, previous)
        state["open"] = []
        state["resolved"] = []
    state["session_key"] = session


def _write_session(root: Path, state: dict[str, Any], session: str) -> None:
    flushed = list(state.get("sessions_flushed") or [])
    if session in flushed:
        return
    book = summarize_book(list(state.get("resolved") or []))
    lines = [
        f"Session {session} (America/Chicago calendar date).",
        HYPOTHESIS_TEXT,
        "pass_now false. A MEASURED row does not replace the crawler and is not a Playground pass.",
    ]
    for name, row in book["names"].items():
        lines.append(
            f"{name}: n={row['n']} mean_r={row['mean_r']} wr={row['wr']} verdict={row['verdict']}"
        )
    if int(state.get("decision_bars") or 0) < REPORT_MIN:
        lines.append("Decision sample is thin. INCONCLUSIVE.")
    append_experiment_entry(root, title=f"sense session {session}", lines=lines)
    flushed.append(session)
    state["sessions_flushed"] = flushed[-32:]


def _save(root: Path, state: dict[str, Any]) -> None:
    path = sense_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["schema"] = SCHEMA
    payload["pass_now"] = False
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True, default=str) + "\n")


def _empty() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "closes": [],
        "open": [],
        "resolved": [],
        "decision_bars": 0,
        "flat_bars": 0,
        "last_action0": None,
        "session_key": "",
        "sessions_flushed": [],
        "all_flat_journaled": False,
        "audit_verdict": "",
        "pass_now": False,
    }
