"""Shadow honesty for THIS Proving Ground clock. Audit-scan is not proof."""
from __future__ import annotations

from typing import Any

ALLOWED_BANDS = frozenset({"GREEN", "YELLOW"})


def shadow_from_progress(prog: dict[str, Any]) -> dict[str, Any]:
    clock = str(prog.get("clock_id") or "")
    shadow_clock = str(prog.get("shadow_clock_id") or "")
    this_run = bool(prog.get("shadow_this_run"))
    if clock and shadow_clock and clock != shadow_clock:
        this_run = False
    if bool(prog.get("shadow_from_audit_scan")):
        this_run = False
    band = str(prog.get("reality_gap_band") or "").upper()
    trend = str(prog.get("reality_gap_trend") or "").upper()
    live_fill = prog.get("live_fill_rate")
    backtest_fill = prog.get("backtest_fill_rate")
    live_slip = prog.get("live_slippage")
    backtest_slip = prog.get("backtest_slippage")
    samples = int(prog.get("shadow_sample_count") or 0)
    gap_ok = (
        band in ALLOWED_BANDS
        and trend != "WIDENING"
        and live_fill is not None
        and backtest_fill is not None
        and live_slip is not None
        and backtest_slip is not None
        and samples > 0
    )
    return {
        "shadow_this_run": this_run and gap_ok,
        "shadow_sample_count": samples,
        "reality_gap_band": band,
        "reality_gap_trend": trend,
        "gap_ok": gap_ok,
    }
