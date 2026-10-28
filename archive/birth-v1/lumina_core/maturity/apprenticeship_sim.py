"""ADR-0051: a DNA backtest is not a session day.

Kept as a fail-closed stub so old imports do not crash. Never writes
``apprenticeship_sim_day_*.json`` and never feeds READY_FOR_REAL.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.maturity.apprenticeship_sim")


def run_apprenticeship_multi_day_sim(
    workspace_root: Path | str,
    *,
    days: int | None = None,
) -> dict[str, Any]:
    """Refuse to materialize fake calendar days from MultiDaySimRunner."""
    _ = workspace_root
    requested = int(days) if days is not None else 0
    logger.warning(
        "apprenticeship_sim.rejected reason=backtest_is_not_a_session_day days_requested=%s",
        requested,
    )
    return {
        "ok": False,
        "reason": "backtest_is_not_a_session_day",
        "days_requested": requested,
        "days_written": 0,
        "note": (
            "Apprenticeship days come from NT SIM venue fills on "
            "state/lumina_apprenticeship_tape.jsonl (ADR-0051)."
        ),
    }
