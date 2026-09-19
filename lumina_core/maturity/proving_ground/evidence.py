"""PromotionGate evidence for THIS Proving Ground clock. Never fabricate samples."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES

MIN_SAMPLE = int(POLICY_EDGE_MIN_TRADES)
CRITERIA_N = 4


def fabrication_reasons(payload: dict[str, Any]) -> tuple[str, ...]:
    """Detect known cheats from the evolution evidence mixin. Any hit = reject."""
    reasons: list[str] = []
    live = _float_list(payload.get("live_pnl_samples"))
    backtest = _float_list(payload.get("backtest_pnl_samples"))
    if len(live) == 1 and payload.get("shadow_total_pnl") is not None:
        if abs(live[0] - float(payload.get("shadow_total_pnl") or 0.0)) < 1e-12:
            reasons.append("live_samples_are_shadow_total_scalar")
    if len(backtest) >= 2 and len(set(round(x, 10) for x in backtest)) == 1:
        reasons.append("backtest_samples_repeated_baseline")
    if int(payload.get("min_sample_trades") or 0) < MIN_SAMPLE:
        reasons.append(f"min_sample_trades<{MIN_SAMPLE}")
    if len(live) < MIN_SAMPLE:
        reasons.append(f"live_pnl_samples={len(live)} < {MIN_SAMPLE}")
    if len(backtest) < MIN_SAMPLE:
        reasons.append(f"backtest_pnl_samples={len(backtest)} < {MIN_SAMPLE}")
    return tuple(reasons)


def evidence_complete(payload: dict[str, Any]) -> bool:
    if fabrication_reasons(payload):
        return False
    cpcv = payload.get("cv_combinatorial")
    pwf = payload.get("cv_walk_forward")
    if not isinstance(cpcv, dict) or not isinstance(pwf, dict):
        return False
    if int(cpcv.get("combinations") or 0) < 5:
        return False
    gap = payload.get("reality_gap_stats")
    stress = payload.get("stress_report")
    if not isinstance(gap, dict) or not isinstance(stress, dict):
        return False
    if payload.get("live_fill_rate") is None or payload.get("backtest_fill_rate") is None:
        return False
    if payload.get("live_slippage") is None or payload.get("backtest_slippage") is None:
        return False
    dna = str(payload.get("dna_hash") or "").strip()
    return len(dna) >= 8


def promotion_from_progress(prog: dict[str, Any]) -> dict[str, Any]:
    """Read this-run PromotionGate decision. Foreign audit rows are ignored."""
    this_run = bool(prog.get("promotion_this_run"))
    criteria = int(prog.get("promotion_criteria_passed") or 0)
    clock = str(prog.get("clock_id") or "")
    decision_clock = str(prog.get("promotion_clock_id") or "")
    if clock and decision_clock and clock != decision_clock:
        this_run = False
    if bool(prog.get("promotion_from_audit_scan")):
        this_run = False
    return {
        "promotion_this_run": this_run and criteria >= CRITERIA_N,
        "promotion_criteria_passed": criteria,
        "promotion_clock_match": (not clock) or clock == decision_clock,
    }


def _float_list(raw: Any) -> list[float]:
    if not isinstance(raw, list):
        return []
    out: list[float] = []
    for item in raw:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            continue
    return out
