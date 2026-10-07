"""NinjaTrader demo cash. Ceiling 50_000. It cannot go negative.

Playground has no drawdown stop. When cash is used up, ask for a refill.
A refill is not a green day and not a stall.
"""
from __future__ import annotations

from pathlib import Path

from lumina_core.maturity.playground.envelope import read_seal

DEMO_CASH_FULL = 50_000.0


def refill_needed(cash: float | None) -> bool:
    """True only when the account is empty. Unknown cash is not empty."""
    if cash is None:
        return False
    return float(cash) <= 0.0


def seal_cash(workspace_root: Path | str) -> float | None:
    raw = read_seal(workspace_root) or {}
    value = raw.get("cash")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def refill_sentence(cash: float | None = 0.0) -> str:
    shown = 0.0 if cash is None else float(cash)
    return (
        f"Demo-rekening is op ({shown:.0f}). Startmarkering 50.000. "
        "Stort elk positief bedrag bij. Zij kan niet onder nul. "
        "Dit is geen stall en geen groene dag."
    )


def note_refill_needed_once(workspace_root: Path | str) -> str | None:
    """One journal line per empty reading. None when cash is still there."""
    cash = seal_cash(workspace_root)
    if not refill_needed(cash):
        return None
    from lumina_core.maturity.playground.sense_lab import load_sense, save_sense

    state = load_sense(workspace_root)
    if state.get("demo_empty_noted"):
        return refill_sentence(cash)
    from lumina_core.maturity.playground.journal import append_experiment_entry

    append_experiment_entry(
        workspace_root,
        title="demo cash empty",
        lines=[
            refill_sentence(cash),
            "Operator refills the NinjaTrader demo to 50000.",
            "Do not count the refill as a green day. Do not stop the school.",
        ],
    )
    state["demo_empty_noted"] = True
    save_sense(workspace_root, state)
    return refill_sentence(cash)
