"""Starship Stage-2 EdgeScore evaluator."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
    evaluate_settlement_honesty,
)


def stage2_expectancy_floor(cfg: BirthCurriculumConfig) -> float:
    """Stage-2 pass floor (WR−0.50 scale). Default −0.15 ≡ 35% hygiene WR.

    Never uses birth survival −0.50 — that is Stage-1 survival only.
    """
    raw = getattr(cfg, "stage2_expectancy_floor", None)
    if raw is None:
        raw = getattr(cfg, "stage1_expectancy_floor", -0.15)
    return float(raw)


def evaluate_stage2_edgescore(
    *,
    trades: int,
    wins: int,
    range_flat_ratio: float,
    range_round_trips: int,
    range_total_signals: int,
    constitution_violations: int,
    required: int,
    cfg: BirthCurriculumConfig,
    entropy: float | None = None,
    total_pnl: float | None = None,
    ppo_steps: int = 0,
    rolling_winrate: float | None = None,
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
) -> EdgeScoreResult:
    """Stage-2 EdgeScore: flat-band + round-trips + expectancy + entropy.

    Expectancy is WR−0.50 (same SSOT as stage1 proxy). When skill-metric
    policy-only is enabled, expectancy grades **pilot** trades only (FORCE_OPEN
    plant trades excluded). Floor never moves.

    When ``rolling_winrate`` is eligible, pass uses max(lifetime, rolling).
    """
    trades_i = max(0, int(trades))
    wins_i = max(0, int(wins))
    flat = float(range_flat_ratio)
    min_rt = max(3, int(required) // 10)
    entropy_floor = float(getattr(cfg, "stage1_entropy_floor", 0.05))
    exp_floor = stage2_expectancy_floor(cfg)

    skill_only = bool(getattr(cfg, "stage2_skill_metric_policy_only", True))
    skill_sample_ok = True
    exp_trades, exp_wins = trades_i, wins_i
    try:
        from lumina_core.birth.stage2_skill_metric import (
            resolve_stage2_skill_counts,
            skill_expectancy_for_pass,
        )

        counts = resolve_stage2_skill_counts(
            total_trades=trades_i,
            total_wins=wins_i,
            policy_trades=policy_trades,
            policy_wins=policy_wins,
            plant_trades=plant_trades,
            plant_wins=plant_wins,
            skill_only=skill_only,
            required=int(required),
            skill_min_trades=getattr(cfg, "stage2_skill_min_trades", None),
        )
        exp_trades, exp_wins = counts.skill_trades, counts.skill_wins
        exp_pack = skill_expectancy_for_pass(counts, rolling_winrate=rolling_winrate)
        # Backward-compatible: (exp, ok) or (exp, ok, source).
        if len(exp_pack) >= 3:
            expectancy, skill_sample_ok, exp_source = (
                float(exp_pack[0]),
                bool(exp_pack[1]),
                str(exp_pack[2]),
            )
        else:
            expectancy, skill_sample_ok = float(exp_pack[0]), bool(exp_pack[1])
            exp_source = "skill"
        # When not skill-only path, keep classic proxy (incl. total_pnl path).
        if not skill_only:
            expectancy = compute_expectancy_proxy(
                wins=wins_i,
                trades=trades_i,
                total_pnl=total_pnl,
                rolling_winrate=rolling_winrate,
            )
            skill_sample_ok = True
            exp_source = "total_or_rolling"
    except Exception:
        expectancy = compute_expectancy_proxy(
            wins=wins_i,
            trades=trades_i,
            total_pnl=total_pnl,
            rolling_winrate=rolling_winrate,
        )
        skill_sample_ok = True
        exp_source = "fallback"

    constitution_ok = int(constitution_violations) == 0
    # Volume = full loop activity (plant + pilot). Skill grades expectancy separately.
    volume_ok = trades_i >= max(1, int(required))
    flat_ok = 0.30 <= flat <= 0.70
    round_trips_ok = int(range_total_signals) < 50 or int(range_round_trips) >= min_rt
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
    # Stage-2 "activity" = range patience band + round-trips + honest settlement.
    # Hold-ratio is not a pass gate (120-bar geometry makes HOLD% high).
    activity_ok = bool(flat_ok and round_trips_ok and settlement_ok)
    hygiene_ok = True  # stage-2 does not use WR hygiene; WR is diagnostic only here
    entropy_required_after = int(getattr(cfg, "starship_entropy_required_after_ppo_steps", 500))
    if entropy is None:
        entropy_ok = int(ppo_steps) < max(0, entropy_required_after)
    else:
        entropy_ok = float(entropy) >= entropy_floor
    expectancy_ok = bool(skill_sample_ok) and (expectancy >= exp_floor)
    # Durable graduation (A+C, plan 2026-08):
    # A: if pass relies on rolling lift, need ≥2 consecutive rolling pass windows.
    # C: lifetime WR must be ≥ floor_equiv − δ (default 5pp → life ≥ 30% at −0.15 floor).
    # Lifetime-only clear is NOT durable on a single hop (PID 33628: 38% @ 350
    # latched durable, then diluted). Need rolling streak like the lift path.
    wr_floor = float(exp_floor) + 0.50
    life_wr = float(wins_i) / float(max(1, trades_i)) if trades_i > 0 else 0.0
    durable_delta = float(getattr(cfg, "stage2_pass_lifetime_delta", 0.05) or 0.05)
    durable_delta = max(0.0, min(0.15, durable_delta))
    life_min = wr_floor - durable_delta
    need_streak = max(1, int(getattr(cfg, "stage2_pass_rolling_streak", 2) or 2))
    durable_enabled = bool(getattr(cfg, "stage2_pass_durable_enabled", True))
    durable_ok = True
    durable_reason = "lifetime"
    if durable_enabled and expectancy_ok:
        life_clears = life_wr + 1e-12 >= wr_floor
        roll_lift = str(exp_source) == "skill_lifted_by_rolling" or (
            rolling_winrate is not None
            and float(rolling_winrate) + 1e-12 >= wr_floor
            and life_wr + 1e-12 < wr_floor
        )
        if life_clears:
            streak_ok = int(consecutive_rolling_pass_windows) >= need_streak
            durable_ok = bool(streak_ok)
            durable_reason = (
                "lifetime_durable"
                if streak_ok
                else f"lifetime_flash_streak_{consecutive_rolling_pass_windows}<{need_streak}"
            )
        elif roll_lift:
            streak_ok = int(consecutive_rolling_pass_windows) >= need_streak
            life_band_ok = life_wr + 1e-12 >= life_min
            durable_ok = bool(streak_ok and life_band_ok)
            if not streak_ok:
                durable_reason = f"rolling_streak_{consecutive_rolling_pass_windows}<{need_streak}"
            elif not life_band_ok:
                durable_reason = f"lifetime_wr_{life_wr:.3f}<{life_min:.3f}"
            else:
                durable_reason = "rolling_durable"
        else:
            durable_ok = True
            durable_reason = str(exp_source or "skill")
    expectancy_ok = bool(expectancy_ok and durable_ok)
    passed = bool(
        volume_ok and constitution_ok and hygiene_ok and activity_ok and entropy_ok and expectancy_ok
    )
    # Occupancy theater (PID 33628): activity already includes round_trips;
    # adding them again pinned EdgeScore at 80% while expectancy was −20%.
    exp_progress = max(
        0.0,
        min(1.0, (expectancy - exp_floor) / max(1e-6, abs(exp_floor) + 0.25)),
    )
    if expectancy_ok:
        quality_term = 0.45 * max(0.40, exp_progress)
    else:
        quality_term = 0.0
    score = max(
        0.0,
        min(
            1.0,
            0.30 * (1.0 if activity_ok else 0.0)
            + 0.25 * (1.0 if entropy_ok else 0.0)
            + quality_term,
        ),
    )
    if not expectancy_ok:
        score = min(score, 0.49)
    blockers: list[str] = []
    if not volume_ok:
        blockers.append(f"trades {trades_i}<{required}")
    if not constitution_ok:
        blockers.append(f"constitution_violations={constitution_violations}")
    if not flat_ok:
        blockers.append(f"flat {flat:.1%} outside 30–70%")
    elif not round_trips_ok:
        blockers.append(f"round_trips {range_round_trips}<{min_rt}")
    if not settlement_ok:
        blockers.append(f"settlement {settle_reason} share={settle_share:.1%}")
    if not entropy_ok:
        blockers.append("entropy dead/missing")
    if not skill_sample_ok:
        blockers.append(
            f"skill_sample policy_trades={exp_trades}<min (pilot sample thin)"
        )
    elif not durable_ok and skill_sample_ok:
        blockers.append(f"durable[{durable_reason}] life={life_wr:.1%}")
    elif not expectancy_ok:
        tag = str(exp_source) if exp_source else ("skill" if skill_only else "total")
        blockers.append(f"expectancy[{tag}] {expectancy:.3f} < {exp_floor:.3f}")
    message = (
        f"s2_edgescore={score:.3f} flat={flat:.1%} rt={range_round_trips} "
        f"exp={expectancy:.3f} src={exp_source} durable={durable_reason} "
        f"wr_eq={expectancy + 0.50:.1%} life={life_wr:.1%} "
        f"trades={trades_i}/{required} settle={settle_reason}"
        f" skill={exp_wins}/{exp_trades}"
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
        pass_expectancy_source=str(exp_source),
        pass_wr_equiv=float(expectancy) + 0.50,
        durable_ok=bool(durable_ok),
        durable_reason=str(durable_reason),
    )
