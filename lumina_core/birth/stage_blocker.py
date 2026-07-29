"""Stage pass blocker computation for birth scorecard UI."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage1_winrate_pass_threshold


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
) -> tuple[str | None, float | None, str | None]:
    """Return (blocker_metric_id, blocker_value, human pass/block reason)."""
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
            )
            if not edge.passed:
                reason = humanize_edgescore_blocker(
                    edge,
                    cfg=cfg,
                    wins=wins,
                    trades=trades,
                    entropy=policy_entropy,
                )
                if not edge.activity_ok:
                    return ("position_flat", round(flat, 4), reason)
                if not edge.entropy_ok:
                    return ("entropy", 0.0, reason)
                if not edge.expectancy_ok:
                    exp = compute_expectancy_proxy(wins=wins, trades=trades)
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
                    winrate = float(wins) / float(max(1, trades))
                    return ("winrate", round(winrate, 4), reason)
                if not edge.activity_ok:
                    return ("hold", round(float(hold_ratio), 4), reason)
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
        hold_cap = float(getattr(cfg, "stage3_hold_ratio_max", 0.70) if cfg else 0.70)
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
        if hold_ratio > hold_cap:
            return (
                "hold",
                round(hold_ratio, 4),
                f"hold {hold_ratio:.1%} > {hold_cap:.0%}",
            )
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
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
