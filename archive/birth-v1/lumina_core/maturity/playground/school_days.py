"""Green session days of the living Playground policy. Tape only. A refill is not a day."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from lumina_core.market.nt_fees import net_close_usd
from lumina_core.maturity.apprenticeship.days import (
    DaySummary,
    consecutive_green_streak,
    row_session_date,
)
from lumina_core.maturity.playground.tape import load_tape_rows

POLICY_REL = Path("state") / "lumina_playground_living_policy.json"


def living_policy_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / POLICY_REL


def living_policy_since(workspace_root: Path | str) -> str:
    """Closes before this stamp belong to the previous pupil. Empty means the whole tape."""
    path = living_policy_path(workspace_root)
    if not path.is_file():
        return ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("since") or "")


def _row_ns(row: dict[str, Any]) -> int:
    from lumina_core.market.globex_hours import parse_instant

    instant = parse_instant(row.get("ts"))
    if instant is None:
        return 0
    return int(instant.timestamp() * 1_000_000_000)


def green_day_streak(workspace_root: Path | str) -> int:
    return consecutive_green_streak(_day_summaries(workspace_root))


def _mark(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _day_is_green(slot: dict[str, Any], *, n: int, constitution: bool) -> bool:
    """Account end must be strictly above the session open. A refill is not green."""
    if constitution or slot.get("refill") is True or n < 1:
        return False
    open_equity = slot.get("open_equity")
    close_equity = slot.get("close_equity")
    if open_equity is not None and close_equity is not None:
        delta = float(close_equity) - float(open_equity)
        if delta <= 0.0:
            return False
        if slot.get("has_pnl") and abs(delta - float(slot["pnl"])) > 0.05:
            return False
        return True
    return False


def _day_summaries(workspace_root: Path | str) -> list[DaySummary]:
    from lumina_core.maturity.playground.research_kit import coloring_hand

    hand = coloring_hand(workspace_root)
    if hand is None:
        return []
    hand_name, hand_since_ns = hand
    by_day: dict[date, dict[str, Any]] = {}
    for row in load_tape_rows(workspace_root):
        if str(row.get("kind") or "") != "close" or not bool(row.get("policy")):
            continue
        if str(row.get("shadow") or "") == "1":
            continue
        if str(row.get("rule_name") or "") != hand_name:
            continue
        if _row_ns(row) < hand_since_ns:
            continue
        day = row_session_date(row)
        if day is None:
            continue
        slot = by_day.setdefault(
            day,
            {"n": 0, "pnl": 0.0, "has_pnl": False, "constitution": False, "refill": False},
        )
        slot["n"] += 1
        pnl = net_close_usd(row)
        if pnl is not None:
            slot["pnl"] += pnl
            slot["has_pnl"] = True
        if row.get("risk_event") or row.get("var_breach") or row.get("daily_kill"):
            slot["constitution"] = True
        if row.get("refill") is True:
            slot["refill"] = True
        open_mark = _mark(row.get("session_open_equity"))
        close_mark = _mark(row.get("session_close_equity"))
        if open_mark is not None and close_mark is not None:
            slot["open_equity"] = open_mark
            slot["close_equity"] = close_mark
    out: list[DaySummary] = []
    for day in sorted(by_day):
        slot = by_day[day]
        n = int(slot["n"])
        expectancy = (float(slot["pnl"]) / float(n)) if n > 0 and slot["has_pnl"] else None
        constitution = bool(slot["constitution"])
        green = _day_is_green(slot, n=n, constitution=constitution)
        out.append(
            DaySummary(
                session_date=day,
                n_closes=n,
                pnl=float(slot["pnl"]) if slot["has_pnl"] else 0.0,
                expectancy=expectancy,
                green=green,
                constitution_hit=constitution,
            )
        )
    return out


def note_sim_refill(workspace_root: Path | str, *, cash_before: float, cash_after: float) -> None:
    """A cash top-up is not a green day and does not delete the tape."""
    from lumina_core.maturity.playground.journal import append_experiment_entry

    append_experiment_entry(
        workspace_root,
        title="sim refill",
        lines=[
            f"Cash {cash_before} -> {cash_after}.",
            "The tape, the shadow book, and the green-day streak stay.",
            "A refill is not a session day and not a pass.",
        ],
    )
