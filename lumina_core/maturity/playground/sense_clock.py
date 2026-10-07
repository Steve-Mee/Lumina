"""Flat is a measurement. The hub says so. It is not a stall and not a pass."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.maturity.playground.journal import append_experiment_entry
from lumina_core.maturity.playground.sense_lab import ALL_FLAT_BARS, load_sense, save_sense


def recognize_existing_flat_book(workspace_root: Path | str) -> None:
    """The crawl denominator is already all flat. Journal it once. Do not invent an action."""
    from lumina_core.maturity.playground.crawl import crawl_totals, last_policy_decision

    root = Path(workspace_root)
    state = load_sense(root)
    if state.get("all_flat_journaled"):
        return
    totals = crawl_totals(root)
    total = int(totals.get("total_bars") or 0)
    flats = int(totals.get("flat_bars") or 0)
    if total < ALL_FLAT_BARS or flats != total:
        return
    decision = last_policy_decision(root)
    action = decision.get("action0")
    action_line = "action0 was not stored on this book."
    if action is not None:
        try:
            action_line = f"last action0={float(action):.4f}."
        except (TypeError, ValueError):
            action_line = "action0 was not a number."
    append_experiment_entry(
        root,
        title="all_flat",
        lines=[
            f"Crawl decision bars: {total}. Flat bars: {flats}.",
            "Blind bars are not in this denominator.",
            action_line,
            "n_P was not changed. This is not a stall and not a pass.",
            "The phase stays incomplete. No wipe.",
            "Do not re-test: forcing a buy because the book is flat, "
            "or sampling the stochastic policy to manufacture a fill.",
        ],
    )
    state["all_flat_journaled"] = True
    if action is not None and state.get("last_action0") is None:
        try:
            state["last_action0"] = float(action)
        except (TypeError, ValueError):
            pass
    save_sense(root, state)


def playground_flat_line(workspace_root: Path | str, *, n_p: int) -> str | None:
    """Sense book first. An older all-flat crawl book still speaks before the next decision."""
    from lumina_core.maturity.playground.crawl import crawl_totals, last_policy_decision
    from lumina_core.maturity.playground.school_days import green_day_streak

    root = Path(workspace_root)
    state = load_sense(root)
    green = green_day_streak(root)
    fresh = flat_clock_message(state, n_p=n_p, green_days=green)
    if fresh is not None:
        return fresh
    if int(state.get("decision_bars") or 0) > 0:
        return None
    totals = crawl_totals(root)
    total = int(totals.get("total_bars") or 0)
    if total <= 0 or int(totals.get("flat_bars") or 0) != total:
        return None
    action = state.get("last_action0")
    if action is None:
        action = last_policy_decision(root).get("action0")
    return _flat_sentence(action, n_p=n_p, green_days=green)


def flat_clock_message(state: dict[str, Any], *, n_p: int, green_days: int = 0) -> str | None:
    """Dutch line while every fresh decision is flat. None when she has entered."""
    decisions = int(state.get("decision_bars") or 0)
    flats = int(state.get("flat_bars") or 0)
    if decisions <= 0 or flats != decisions:
        return None
    return _flat_sentence(state.get("last_action0"), n_p=n_p, green_days=green_days)


def _flat_sentence(action: Any, *, n_p: int, green_days: int) -> str | None:
    tail = f"Groen {int(green_days)}/5. Closes {int(n_p)}. Geen stall. Geen pass."
    if action is None:
        return f"Zij kiest plat. {tail}"
    try:
        shown = float(action)
    except (TypeError, ValueError):
        return f"Zij kiest plat. {tail}"
    return f"Zij kiest plat. Actie {shown:.2f}. {tail}"
