"""Live process-R kwargs for certified stall blocker recompute."""
from __future__ import annotations

from typing import Any


def fill_pending_stage_blocker(loop: Any, pending: dict[str, Any]) -> dict[str, Any]:
    """Fill wall/plateau pending with a live HUD-grade blocker. Never invent None/days=0."""
    pending = dict(pending or {})
    failure_key = str(pending.get("failure_key") or "stage_stalled")
    blocker_metric = pending.get("blocker_metric")
    blocker_value = pending.get("blocker_value")
    blocker_reason = pending.get("blocker_reason")
    engineering_stuck = (
        failure_key == "adaptation_stuck"
        or str(blocker_metric or "") == "adaptation_stuck"
        or str(blocker_reason or "") == "adaptation_loop_blocked"
    )
    need_skill_fill = (
        blocker_metric is None
        or blocker_value is None
        or engineering_stuck
        or "None" in str(blocker_reason or "")
        or "days=0" in str(blocker_reason or "")
    )
    if not need_skill_fill:
        pending["failure_key"] = failure_key
        pending["blocker_metric"] = blocker_metric
        pending["blocker_value"] = blocker_value
        if blocker_reason:
            pending["blocker_reason"] = blocker_reason
        return pending
    try:
        from lumina_core.birth.history_loader import session_unique_calendar_days
        from lumina_core.birth.stage_loop_meta import _observe_mean_r, _observe_median_loss_r
        from lumina_core.birth.stage_scorecard import compute_stage_blocker

        hold_ratio = float(loop.stage_hold_signals) / float(
            max(1, loop.stage_total_signals)
        )
        range_flat_ratio = float(loop.stage_range_flat_bars) / float(
            max(1, loop.stage_range_total_signals)
        )
        unique_days = session_unique_calendar_days(
            cached=int(getattr(loop, "_unique_calendar_days", 0) or 0),
            host=getattr(loop, "host", None),
            ticks=getattr(loop, "stage_ticks", None),
        )
        occupancy = _live_occupancy(loop, range_flat_ratio)
        geo = getattr(loop, "_birth_trade_geometry", None)
        stop_pct = float(getattr(geo, "stop_pct", 0.0) or 0.0) if geo is not None else None
        ref_price = float(getattr(geo, "ref_price", 0.0) or 0.0) if geo is not None else None
        net_rr = (
            float(getattr(geo, "net_rr_after_cost", 0.0) or 0.0) if geo is not None else None
        )
        p_ft = getattr(loop, "_first_touch_target_hit_rate", None)
        bm, bv, br = compute_stage_blocker(
            loop.stage,
            stage_trades=loop.stage_trades,
            stage_wins=loop.stage_wins,
            hold_ratio=hold_ratio,
            required=loop.required,
            constitution_violations=loop.host._constitution_guard.violations,
            range_flat_ratio=range_flat_ratio,
            range_round_trips=loop.stage_range_round_trips,
            range_total_signals=loop.stage_range_total_signals,
            cfg=loop.cur_cfg,
            policy_entropy=loop._resolve_policy_entropy(),
            ppo_steps=int(getattr(loop.host, "ppo_steps", 0) or 0),
            policy_trades=int(getattr(loop, "stage_policy_trades", 0) or 0),
            policy_wins=int(getattr(loop, "stage_policy_wins", 0) or 0),
            plant_trades=int(getattr(loop, "stage_plant_trades", 0) or 0),
            plant_wins=int(getattr(loop, "stage_plant_wins", 0) or 0),
            median_loss_r=_observe_median_loss_r(loop),
            mean_r=_observe_mean_r(loop),
            first_touch_hit_rate=float(p_ft) if p_ft is not None else None,
            geometry_net_rr=net_rr,
            unique_calendar_days=unique_days,
            occupancy=occupancy,
            pnl_series=list(getattr(loop, "stage_val_pnl", None) or []) or None,
            r_series=list(getattr(loop, "stage_val_r", None) or []) or None,
            stop_pct=stop_pct,
            ref_price=ref_price,
        )
        if engineering_stuck and bm is not None:
            pending["engineering_blocker"] = "adaptation_stuck"
            blocker_metric = bm
            blocker_value = bv if bv is not None else 0.0
            blocker_reason = br or blocker_reason
        else:
            if blocker_metric is None or "None" in str(blocker_reason or "") or "days=0" in str(
                blocker_reason or ""
            ):
                blocker_metric = bm or failure_key or "stage_stalled"
                blocker_reason = br or blocker_reason
            if blocker_value is None:
                blocker_value = bv if bv is not None else 0.0
            if not blocker_reason:
                blocker_reason = br or failure_key
    except Exception:
        blocker_metric = blocker_metric or failure_key or "stage_stalled"
        blocker_value = 0.0 if blocker_value is None else blocker_value
        blocker_reason = blocker_reason or failure_key
    pending["failure_key"] = failure_key
    pending["blocker_metric"] = blocker_metric
    pending["blocker_value"] = blocker_value
    if blocker_reason:
        pending["blocker_reason"] = blocker_reason
    return pending


def _live_occupancy(loop: Any, range_flat_ratio: float) -> float | None:
    try:
        from lumina_core.birth.foundation_occupancy_envelope import (
            OccupancyExamWindow,
            occupancy_for_foundation_pass,
        )

        win_raw = getattr(loop, "occupancy_exam_window", None)
        win = win_raw if isinstance(win_raw, OccupancyExamWindow) else OccupancyExamWindow()
        return occupancy_for_foundation_pass(
            stage=loop.stage,
            range_flat_bars=int(getattr(loop, "stage_range_flat_bars", 0) or 0),
            range_total_signals=int(getattr(loop, "stage_range_total_signals", 0) or 0),
            passthrough_flat_bars=int(getattr(loop, "passthrough_range_flat_bars", 0) or 0),
            passthrough_total_signals=int(getattr(loop, "passthrough_range_total_signals", 0) or 0),
            exam_armed=bool(win.armed),
            exam_passthrough_flat_bars=int(win.passthrough_flat),
            exam_passthrough_total_signals=int(win.passthrough_signals),
            exam_flat_bars=int(win.exam_flat),
            exam_total_signals=int(win.exam_signals),
        )
    except Exception:
        if int(getattr(loop, "stage_range_total_signals", 0) or 0) >= 50:
            return float(range_flat_ratio)
        return None
