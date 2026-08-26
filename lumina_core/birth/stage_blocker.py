"""Stage pass blocker computation for birth scorecard UI."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage1_winrate_pass_threshold


def _settlement_blocker(
    cfg: BirthCurriculumConfig | None,
    *,
    trades: int,
    required: int,
    closes_stop: int,
    closes_target: int,
    closes_time_stop: int,
    closes_flatten: int,
    closes_unknown: int,
) -> tuple[str, float, str] | None:
    """Fail-closed settlement honesty for EdgeScore-off fallbacks."""
    from lumina_core.birth.starship_edgescore_core import evaluate_settlement_honesty

    if cfg is not None and not bool(getattr(cfg, "settlement_honesty_enabled", True)):
        return None
    ok, share, reason = evaluate_settlement_honesty(
        closes_stop=int(closes_stop),
        closes_target=int(closes_target),
        closes_time_stop=int(closes_time_stop),
        closes_flatten=int(closes_flatten),
        closes_unknown=int(closes_unknown),
        trades=int(trades),
        required=int(required),
        min_share=float(getattr(cfg, "settlement_min_decisive_share", 0.70) or 0.70)
        if cfg
        else 0.70,
    )
    if ok:
        return None
    return (
        "settlement",
        round(float(share), 4),
        f"settlement {reason} share={share:.1%}",
    )


def compute_stage_blocker(
    stage: CurriculumStage,
    *,
    stage_trades: int,
    stage_wins: int,
    hold_ratio: float,
    required: int,
    constitution_violations: int,
    range_flat_ratio: float,
    range_round_trips: int,
    range_total_signals: int,
    cfg: BirthCurriculumConfig | None = None,
    rolling_winrate: float | None = None,
    rolling_winrate_display: float | None = None,
    rolling_wr_eligible: bool | None = None,
    policy_entropy: float | None = None,
    ppo_steps: int = 0,
    policy_trades: int | None = None,
    policy_wins: int | None = None,
    plant_trades: int | None = None,
    plant_wins: int | None = None,
    consecutive_rolling_pass_windows: int = 0,
    closes_stop: int = 0,
    closes_target: int = 0,
    closes_time_stop: int = 0,
    closes_flatten: int = 0,
    closes_unknown: int = 0,
    median_loss_r: float | None = None,
    mean_r: float | None = None,
    first_touch_hit_rate: float | None = None,
    geometry_net_rr: float | None = None,
    unique_calendar_days: int | None = None,
    oos_sharpe: float | None = None,
    oos_dd_pct: float | None = None,
    pnl_series: list[float] | None = None,
    stop_pct: float | None = None,
    ref_price: float | None = None,
    settlement_ok: bool = True,
    settlement_share: float = 1.0,
    entropy_alive: bool = True,
    r_series: list[float] | None = None,
) -> tuple[str | None, float | None, str | None]:
    """Return (blocker_metric_id, blocker_value, human pass/block reason)."""
    from lumina_core.birth.stage_blocker_foundation import compute_foundation_hud_blocker

    foundation = compute_foundation_hud_blocker(
        stage,
        trades=max(0, int(stage_trades)),
        wins=max(0, int(stage_wins)),
        required=int(required),
        constitution_violations=int(constitution_violations),
        occupancy=(
            float(range_flat_ratio)
            if int(range_total_signals) >= 50
            else None
        ),
        median_loss_r=median_loss_r,
        mean_r=mean_r,
        first_touch_hit_rate=first_touch_hit_rate,
        geometry_net_rr=geometry_net_rr,
        unique_calendar_days=unique_calendar_days,
        oos_sharpe=oos_sharpe,
        oos_dd_pct=oos_dd_pct,
        range_round_trips=int(range_round_trips),
        pnl_series=pnl_series,
        r_series=r_series,
        stop_pct=stop_pct,
        ref_price=ref_price,
        settlement_ok=bool(settlement_ok),
        settlement_share=float(settlement_share),
        entropy_alive=bool(entropy_alive),
    )
    if foundation is not None:
        return foundation
    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    if stage == CurriculumStage.STAGE1_TREND:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_gate = stage1_winrate_pass_threshold(cfg) if cfg is not None else 0.45
        edgescore_on = bool(getattr(cfg, "stage1_edgescore_enabled", False)) if cfg else False
        if edgescore_on and cfg is not None:
            from lumina_core.birth.starship_birth import (
                compute_expectancy_proxy,
                evaluate_stage1_edgescore,
                humanize_edgescore_blocker,
                rolling_pass_min_covered,
            )

            hold_ratio_local = float(hold_ratio)
            edge = evaluate_stage1_edgescore(
                trades=trades,
                wins=wins,
                constitution_violations=constitution_violations,
                required=required,
                cfg=cfg,
                rolling_winrate=rolling_winrate,
                hold_ratio=hold_ratio_local,
                entropy=policy_entropy,
                ppo_steps=int(ppo_steps),
            )
            if not edge.passed:
                reason = humanize_edgescore_blocker(
                    edge,
                    cfg=cfg,
                    wins=wins,
                    trades=trades,
                    entropy=policy_entropy,
                    rolling_winrate=rolling_winrate,
                    rolling_winrate_display=rolling_winrate_display,
                    rolling_wr_eligible=rolling_wr_eligible,
                    rolling_min_covered=rolling_pass_min_covered(
                        int(getattr(cfg, "stage1_rolling_pass_window", 500) or 500)
                    ),
                )
                if not edge.hygiene_ok:
                    return ("winrate", round(winrate, 4), reason)
                if not edge.activity_ok:
                    return ("hold", round(hold_ratio_local, 4), reason)
                if not edge.entropy_ok:
                    return ("entropy", 0.0, reason)
                if not edge.expectancy_ok:
                    exp = compute_expectancy_proxy(
                        wins=wins,
                        trades=trades,
                        rolling_winrate=rolling_winrate,
                    )
                    return ("expectancy", round(float(exp), 4), reason)
                if not edge.constitution_ok:
                    return (
                        "constitution_violations",
                        float(constitution_violations),
                        reason,
                    )
                return ("edgescore", round(edge.score, 4), reason)
            return (None, None, None)
        if winrate < wr_gate:
            return (
                "winrate",
                round(winrate, 4),
                f"winrate {winrate:.1%} < {wr_gate:.0%}",
            )
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        return (None, None, None)
    if stage == CurriculumStage.STAGE2_RANGE:
        if trades < required:
            return (None, None, None)
        s2_edge = bool(getattr(cfg, "stage2_edgescore_enabled", False)) if cfg else False
        if s2_edge and cfg is not None:
            from lumina_core.birth.starship_birth import (
                compute_expectancy_proxy,
                evaluate_stage2_edgescore,
                humanize_edgescore_blocker,
            )

            flat = float(range_flat_ratio) if range_total_signals >= 50 else float(hold_ratio)
            edge = evaluate_stage2_edgescore(
                trades=trades,
                wins=wins,
                range_flat_ratio=flat,
                range_round_trips=range_round_trips,
                range_total_signals=range_total_signals,
                constitution_violations=constitution_violations,
                required=required,
                cfg=cfg,
                entropy=policy_entropy,
                ppo_steps=int(ppo_steps),
                rolling_winrate=rolling_winrate,
                policy_trades=policy_trades,
                policy_wins=policy_wins,
                plant_trades=plant_trades,
                plant_wins=plant_wins,
                consecutive_rolling_pass_windows=int(
                    consecutive_rolling_pass_windows or 0
                ),
                closes_stop=int(closes_stop),
                closes_target=int(closes_target),
                closes_time_stop=int(closes_time_stop),
                closes_flatten=int(closes_flatten),
                closes_unknown=int(closes_unknown),
            )
            if not edge.passed:
                reason = humanize_edgescore_blocker(
                    edge,
                    cfg=cfg,
                    wins=wins,
                    trades=trades,
                    entropy=policy_entropy,
                    rolling_winrate=rolling_winrate,
                    rolling_winrate_display=rolling_winrate_display,
                    rolling_wr_eligible=rolling_wr_eligible,
                    stage="stage2_range",
                )
                if not edge.activity_ok:
                    msg_l = (edge.message or "").lower()
                    if "settlement" in msg_l:
                        return ("settlement", 0.0, reason)
                    # flat = empty-bar ratio: low = over-trading, high = under-activity.
                    # Never tell the operator "need more activity" when already over-trading.
                    min_rt = max(3, int(required) // 10)
                    flat_ok = 0.30 <= flat <= 0.70
                    if not flat_ok and flat < 0.30:
                        flat_reason = (
                            f"position_flat {flat:.1%} below 30% band "
                            f"(over-trading: need more empty time / selective entries) "
                            f"| EdgeScore {edge.score:.0%}"
                        )
                        return ("position_flat", round(flat, 4), flat_reason)
                    if not flat_ok and flat > 0.70:
                        flat_reason = (
                            f"position_flat {flat:.1%} above 70% band "
                            f"(under-activity: need more in-range participation) "
                            f"| EdgeScore {edge.score:.0%}"
                        )
                        return ("position_flat", round(flat, 4), flat_reason)
                    # Flat in band but round-trips insufficient.
                    rt_reason = (
                        f"round_trips {range_round_trips}<{min_rt} "
                        f"(flat {flat:.1%} in band) | EdgeScore {edge.score:.0%}"
                    )
                    return ("round_trips", float(range_round_trips), rt_reason)
                if not edge.entropy_ok:
                    return ("entropy", 0.0, reason)
                if not edge.expectancy_ok:
                    # Durable C-band fail: report lifetime WR, not rolling-lifted expectancy.
                    if not bool(getattr(edge, "durable_ok", True)):
                        life_wr = float(wins) / float(max(1, trades))
                        return ("durable_lifetime", round(life_wr, 4), reason)
                    # Prefer skill (pilot) expectancy when policy counts present.
                    try:
                        from lumina_core.birth.stage2_skill_metric import (
                            resolve_stage2_skill_counts,
                            skill_expectancy_for_pass,
                        )

                        sc = resolve_stage2_skill_counts(
                            total_trades=trades,
                            total_wins=wins,
                            policy_trades=policy_trades,
                            policy_wins=policy_wins,
                            plant_trades=plant_trades,
                            plant_wins=plant_wins,
                            skill_only=bool(
                                getattr(cfg, "stage2_skill_metric_policy_only", True)
                            ),
                            required=required,
                        )
                        exp, _, *_rest = skill_expectancy_for_pass(
                            sc, rolling_winrate=rolling_winrate
                        )
                    except Exception:
                        exp = compute_expectancy_proxy(
                            wins=wins, trades=trades, rolling_winrate=rolling_winrate
                        )
                    return ("expectancy", round(float(exp), 4), reason)
                if not edge.constitution_ok:
                    return (
                        "constitution_violations",
                        float(constitution_violations),
                        reason,
                    )
                return ("edgescore", round(edge.score, 4), reason)
            return (None, None, None)
        if range_total_signals >= 50:
            metric = range_flat_ratio
            label = "position_flat"
            min_round_trips = max(3, required // 10)
            if range_round_trips < min_round_trips:
                return (
                    "round_trips",
                    float(range_round_trips),
                    f"round_trips {range_round_trips} < {min_round_trips}",
                )
        else:
            metric = hold_ratio
            label = "hold"
        if metric < 0.30 or metric > 0.70:
            return (label, round(metric, 4), f"{label} {metric:.1%} outside 30–70%")
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        settle_block = _settlement_blocker(
            cfg,
            trades=trades,
            required=required,
            closes_stop=closes_stop,
            closes_target=closes_target,
            closes_time_stop=closes_time_stop,
            closes_flatten=closes_flatten,
            closes_unknown=closes_unknown,
        )
        if settle_block is not None:
            return settle_block
        return (None, None, None)
    if stage == CurriculumStage.STAGE3_MIXED:
        if trades < required:
            return (None, None, None)
        s3_edge = bool(getattr(cfg, "stage3_edgescore_enabled", False)) if cfg else False
        if s3_edge and cfg is not None:
            from lumina_core.birth.starship_birth import (
                compute_expectancy_proxy,
                evaluate_stage3_edgescore,
                humanize_edgescore_blocker,
                rolling_pass_min_covered,
            )

            edge = evaluate_stage3_edgescore(
                trades=trades,
                wins=wins,
                constitution_violations=constitution_violations,
                required=required,
                cfg=cfg,
                rolling_winrate=rolling_winrate,
                hold_ratio=float(hold_ratio),
                entropy=policy_entropy,
                ppo_steps=int(ppo_steps),
                range_flat_ratio=float(range_flat_ratio),
                range_total_signals=int(range_total_signals),
                range_round_trips=int(range_round_trips),
                consecutive_rolling_pass_windows=int(
                    consecutive_rolling_pass_windows or 0
                ),
                closes_stop=int(closes_stop),
                closes_target=int(closes_target),
                closes_time_stop=int(closes_time_stop),
                closes_flatten=int(closes_flatten),
                closes_unknown=int(closes_unknown),
            )
            if not edge.passed:
                reason = humanize_edgescore_blocker(
                    edge,
                    cfg=cfg,
                    wins=wins,
                    trades=trades,
                    entropy=policy_entropy,
                    rolling_winrate=rolling_winrate,
                    rolling_winrate_display=rolling_winrate_display,
                    rolling_wr_eligible=rolling_wr_eligible,
                    rolling_min_covered=rolling_pass_min_covered(
                        int(getattr(cfg, "stage1_rolling_pass_window", 500) or 500)
                    ),
                    stage="stage3_mixed",
                )
                if not edge.hygiene_ok:
                    winrate = float(wins) / float(max(1, trades))
                    if not bool(getattr(edge, "durable_ok", True)):
                        return ("durable_lifetime", round(winrate, 4), reason)
                    return ("winrate", round(winrate, 4), reason)
                if not edge.activity_ok:
                    msg_l = (edge.message or "").lower()
                    if "settlement" in msg_l:
                        return ("settlement", 0.0, reason)
                    if "flat" in msg_l or "over-trading" in msg_l or "under-activity" in msg_l:
                        return ("occupancy", round(float(range_flat_ratio), 4), reason)
                    if "round_trips" in msg_l:
                        return ("round_trips", float(range_round_trips), reason)
                    return ("occupancy", round(float(range_flat_ratio), 4), reason)
                if not edge.entropy_ok:
                    return ("entropy", 0.0, reason)
                if not edge.expectancy_ok:
                    exp = compute_expectancy_proxy(
                        wins=wins,
                        trades=trades,
                        rolling_winrate=rolling_winrate,
                    )
                    return ("expectancy", round(float(exp), 4), reason)
                if not edge.constitution_ok:
                    return (
                        "constitution_violations",
                        float(constitution_violations),
                        reason,
                    )
                return ("edgescore", round(edge.score, 4), reason)
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_floor = float(getattr(cfg, "stage3_winrate_floor", 0.35) if cfg else 0.35)
        roll = float(rolling_winrate) if rolling_winrate is not None else None
        use_rolling = bool(getattr(cfg, "stage3_use_rolling_pass", True)) if cfg else True
        lifetime_ok = winrate >= wr_floor
        rolling_ok = (
            use_rolling and roll is not None and float(roll) >= wr_floor
        )
        if not lifetime_ok and not rolling_ok:
            if roll is not None:
                reason = (
                    f"mixed lifetime {winrate:.1%} / rolling {float(roll):.1%} "
                    f"< {wr_floor:.0%}"
                )
            else:
                reason = (
                    f"mixed lifetime {winrate:.1%} < {wr_floor:.0%} "
                    f"(rolling window still building)"
                )
            return (
                "winrate",
                round(winrate, 4),
                reason,
            )
        occupancy_enabled = bool(getattr(cfg, "stage3_occupancy_pass_enabled", True)) if cfg else True
        if occupancy_enabled and range_total_signals >= 50:
            flat_min = float(getattr(cfg, "stage3_position_flat_min", 0.25) or 0.25) if cfg else 0.25
            flat_max = float(getattr(cfg, "stage3_position_flat_max", 0.75) or 0.75) if cfg else 0.75
            if range_flat_ratio + 1e-12 < flat_min:
                return (
                    "occupancy",
                    round(float(range_flat_ratio), 4),
                    f"flat {range_flat_ratio:.1%} < {flat_min:.0%} (over-trading)",
                )
            if range_flat_ratio > flat_max + 1e-12:
                return (
                    "occupancy",
                    round(float(range_flat_ratio), 4),
                    f"flat {range_flat_ratio:.1%} > {flat_max:.0%} (under-activity)",
                )
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        min_rt = max(3, int(required) // 10)
        if range_total_signals >= 50 and int(range_round_trips) < min_rt:
            return (
                "round_trips",
                float(range_round_trips),
                f"round_trips {range_round_trips}<{min_rt}",
            )
        settle_block = _settlement_blocker(
            cfg,
            trades=trades,
            required=required,
            closes_stop=closes_stop,
            closes_target=closes_target,
            closes_time_stop=closes_time_stop,
            closes_flatten=closes_flatten,
            closes_unknown=closes_unknown,
        )
        if settle_block is not None:
            return settle_block
        return (None, None, None)
    if stage == CurriculumStage.STAGE5_PROFIT_VAL:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_gate = float(getattr(cfg, "runway_stage5_winrate_pass", 0.40) if cfg else 0.40)
        hold_cap = float(getattr(cfg, "runway_stage5_hold_ratio_max", 0.55) if cfg else 0.55)
        if winrate < wr_gate:
            return ("winrate", round(winrate, 4), f"val winrate {winrate:.1%} < {wr_gate:.0%}")
        if hold_ratio > hold_cap:
            return ("hold", round(hold_ratio, 4), f"hold {hold_ratio:.1%} > {hold_cap:.0%}")
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        return (None, None, None)
    if stage == CurriculumStage.STAGE6_RISK_DISCIPLINE:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_gate = float(getattr(cfg, "runway_stage6_winrate_min", 0.42) if cfg else 0.42)
        if winrate < wr_gate:
            return ("winrate", round(winrate, 4), f"val winrate {winrate:.1%} < {wr_gate:.0%}")
        return (None, None, None)
    if stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_gate = float(getattr(cfg, "runway_stage7_winrate_min", 0.45) if cfg else 0.45)
        if winrate < wr_gate:
            return (
                "winrate",
                round(winrate, 4),
                f"profile winrate {winrate:.1%} < {wr_gate:.0%}",
            )
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        return (None, None, None)
    return (None, None, None)
