"""Starship Stage-3 EdgeScore evaluator."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
    evaluate_settlement_honesty,
)


def evaluate_stage3_edgescore(
    *,
    trades: int,
    wins: int,
    hold_signals: int = 0,
    total_signals: int = 0,
    constitution_violations: int,
    required: int,
    cfg: BirthCurriculumConfig,
    entropy: float | None = None,
    total_pnl: float | None = None,
    rolling_winrate: float | None = None,
    hold_ratio: float | None = None,
    ppo_steps: int = 0,
    range_flat_ratio: float | None = None,
    range_total_signals: int = 0,
    range_round_trips: int = 0,
    consecutive_rolling_pass_windows: int = 0,
    closes_stop: int = 0,
    closes_target: int = 0,
    closes_time_stop: int = 0,
    closes_flatten: int = 0,
    closes_unknown: int = 0,
) -> EdgeScoreResult:
    """Stage-3 EdgeScore: WR hygiene + occupancy + settlement + expectancy.

    Live forensics 2026-08-13: hold_ratio ≤ 70% fought 120-bar geometry (hold ~90%
    is normal when occupancy is in band). Activity is occupancy 25–75% +
    stop/target/time-stop share, not action-HOLD%. Floors unchanged (hygiene 35%,
    exp ≥ −0.15).
    """
    _ = hold_signals  # diagnostic only — not a pass gate
    trades_i = max(0, int(trades))
    wins_i = max(0, int(wins))
    winrate = float(wins_i) / float(max(1, trades_i))
    roll = float(rolling_winrate) if rolling_winrate is not None else winrate
    if hold_ratio is not None:
        hold_v = float(hold_ratio)
    else:
        hold_v = float(hold_signals) / float(max(1, total_signals))
    wr_floor = float(getattr(cfg, "stage3_winrate_floor", 0.35))
    entropy_floor = float(getattr(cfg, "stage1_entropy_floor", 0.05))
    # Early-quality floor (same WR−0.50 scale as Stage-2); never survival −0.50.
    raw_exp = getattr(cfg, "stage2_expectancy_floor", None)
    if raw_exp is None:
        raw_exp = getattr(cfg, "stage1_expectancy_floor", -0.15)
    exp_floor = float(raw_exp if raw_exp is not None else -0.15)
    expectancy = compute_expectancy_proxy(
        wins=wins_i,
        trades=trades_i,
        total_pnl=total_pnl,
        rolling_winrate=rolling_winrate,
    )
    constitution_ok = int(constitution_violations) == 0
    volume_ok = trades_i >= max(1, int(required))
    use_rolling = bool(getattr(cfg, "stage3_use_rolling_pass", True))
    durable_enabled = bool(getattr(cfg, "stage3_pass_durable_enabled", True))
    durable_delta = float(getattr(cfg, "stage3_pass_lifetime_delta", 0.05) or 0.05)
    durable_delta = max(0.0, min(0.15, durable_delta))
    life_min = wr_floor - durable_delta
    need_streak = max(1, int(getattr(cfg, "stage3_pass_rolling_streak", 2) or 2))
    life_clears = winrate + 1e-12 >= wr_floor
    roll_lift = bool(
        use_rolling
        and rolling_winrate is not None
        and float(rolling_winrate) + 1e-12 >= wr_floor
        and winrate + 1e-12 < wr_floor
    )
    durable_reason = "lifetime"
    s3_durable_ok = True
    if not durable_enabled:
        hygiene_ok = winrate >= wr_floor or (use_rolling and roll >= wr_floor)
        durable_reason = "legacy"
    elif life_clears:
        hygiene_ok = True
        durable_reason = "lifetime"
    elif roll_lift:
        streak_ok = int(consecutive_rolling_pass_windows) >= need_streak
        life_band_ok = winrate + 1e-12 >= life_min
        hygiene_ok = bool(streak_ok and life_band_ok)
        s3_durable_ok = hygiene_ok
        if not streak_ok:
            durable_reason = f"rolling_streak_{consecutive_rolling_pass_windows}<{need_streak}"
        elif not life_band_ok:
            durable_reason = f"lifetime_wr_{winrate:.3f}<{life_min:.3f}"
        else:
            durable_reason = "rolling_durable"
    else:
        hygiene_ok = False
        durable_reason = "hygiene"
    # Occupancy: mixed-flat in 25–75% once the sample is warm.
    # Fail-closed when signals≥50 but flat SSOT missing.
    flat_min = float(getattr(cfg, "stage3_position_flat_min", 0.25) or 0.25)
    flat_min = max(0.15, min(0.45, flat_min))
    flat_max = float(getattr(cfg, "stage3_position_flat_max", 0.75) or 0.75)
    flat_max = max(flat_min + 0.10, min(0.90, flat_max))
    signals = int(range_total_signals)
    occupancy_enabled = bool(getattr(cfg, "stage3_occupancy_pass_enabled", True))
    if not occupancy_enabled or signals < 50:
        flat_v = float(range_flat_ratio) if range_flat_ratio is not None else -1.0
        flat_ok = True  # warm-up or disabled
    elif range_flat_ratio is None:
        flat_v = -1.0
        flat_ok = False
    else:
        flat_v = float(range_flat_ratio)
        flat_ok = bool(flat_min - 1e-12 <= flat_v <= flat_max + 1e-12)
    min_rt = max(3, int(required) // 10)
    round_trips_ok = signals < 50 or int(range_round_trips) >= min_rt
    share_floor = float(getattr(cfg, "settlement_min_decisive_share", 0.70) or 0.70)
    settlement_ok, settle_share, settle_reason = evaluate_settlement_honesty(
        closes_stop=int(closes_stop),
        closes_target=int(closes_target),
        closes_time_stop=int(closes_time_stop),
        closes_flatten=int(closes_flatten),
        closes_unknown=int(closes_unknown),
        trades=trades_i,
        required=int(required),
        min_share=share_floor,
    )
    if not bool(getattr(cfg, "settlement_honesty_enabled", True)):
        settlement_ok = True
        settle_reason = "disabled"
    activity_ok = bool(flat_ok and round_trips_ok and settlement_ok)
    entropy_required_after = int(getattr(cfg, "starship_entropy_required_after_ppo_steps", 500))
    if entropy is None:
        entropy_ok = int(ppo_steps) < max(0, entropy_required_after)
    else:
        entropy_ok = float(entropy) >= entropy_floor
    expectancy_ok = expectancy >= exp_floor
    passed = bool(
        volume_ok and constitution_ok and hygiene_ok and activity_ok and entropy_ok and expectancy_ok
    )
    effective_wr = max(winrate, float(roll))
    score = max(
        0.0,
        min(
            1.0,
            0.30 * max(0.0, min(1.0, (effective_wr - wr_floor) / max(1e-6, 0.50 - wr_floor)))
            + 0.20 * (1.0 if flat_ok else 0.0)
            + 0.15 * (1.0 if settlement_ok else 0.0)
            + 0.15 * (1.0 if entropy_ok else 0.0)
            + 0.20 * max(0.0, min(1.0, (expectancy - exp_floor) / max(1e-6, abs(exp_floor) + 0.25))),
        ),
    )
    blockers: list[str] = []
    if not volume_ok:
        blockers.append(f"trades {trades_i}<{required}")
    if not constitution_ok:
        blockers.append(f"constitution_violations={constitution_violations}")
    if not hygiene_ok:
        blockers.append(
            f"hygiene wr {winrate:.1%}/{roll:.1%} < {wr_floor:.0%} durable[{durable_reason}]"
        )
    if not flat_ok:
        if range_flat_ratio is None and signals >= 50:
            blockers.append(f"flat SSOT missing (need {flat_min:.0%}–{flat_max:.0%})")
        elif flat_v + 1e-12 < flat_min:
            blockers.append(f"flat {flat_v:.1%} < {flat_min:.0%} (over-trading)")
        else:
            blockers.append(f"flat {flat_v:.1%} > {flat_max:.0%} (under-activity)")
    if not round_trips_ok:
        blockers.append(f"round_trips {range_round_trips}<{min_rt}")
    if not settlement_ok:
        blockers.append(f"settlement {settle_reason} share={settle_share:.1%}")
    if not entropy_ok:
        blockers.append("entropy dead/missing")
    if not expectancy_ok:
        blockers.append(f"expectancy {expectancy:.3f} < {exp_floor:.3f}")
    message = (
        f"s3_edgescore={score:.3f} wr={winrate:.1%} hold={hold_v:.1%} "
        f"flat={flat_v:.1%} exp={expectancy:.3f} trades={trades_i}/{required} "
        f"durable={durable_reason} settle={settle_reason}"
        + (f" blockers={';'.join(blockers)}" if blockers else " PASS")
    )
    return EdgeScoreResult(
        passed=passed,
        score=score,
        hygiene_ok=hygiene_ok,
        activity_ok=activity_ok,
        entropy_ok=entropy_ok,
        expectancy_ok=expectancy_ok,
        constitution_ok=constitution_ok,
        message=message,
        pass_expectancy=float(expectancy),
        pass_expectancy_source="rolling" if rolling_winrate is not None else "lifetime",
        pass_wr_equiv=float(expectancy) + 0.50,
        durable_ok=bool(s3_durable_ok),
        durable_reason=str(durable_reason),
    )
