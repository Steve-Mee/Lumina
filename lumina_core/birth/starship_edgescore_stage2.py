"""Starship Stage-2 EdgeScore evaluator."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
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
) -> EdgeScoreResult:
    """Stage-2 EdgeScore: flat-band + round-trips + expectancy + entropy.

    Expectancy is WR−0.50 (same SSOT as stage1 proxy). When ``rolling_winrate``
    is eligible, pass uses max(lifetime, rolling) so recovery is possible without
    wiping a long weak lifetime history.
    """
    trades_i = max(0, int(trades))
    wins_i = max(0, int(wins))
    flat = float(range_flat_ratio)
    min_rt = max(3, int(required) // 10)
    entropy_floor = float(getattr(cfg, "stage1_entropy_floor", 0.05))
    exp_floor = stage2_expectancy_floor(cfg)
    expectancy = compute_expectancy_proxy(
        wins=wins_i,
        trades=trades_i,
        total_pnl=total_pnl,
        rolling_winrate=rolling_winrate,
    )
    constitution_ok = int(constitution_violations) == 0
    volume_ok = trades_i >= max(1, int(required))
    flat_ok = 0.30 <= flat <= 0.70
    round_trips_ok = int(range_total_signals) < 50 or int(range_round_trips) >= min_rt
    # Stage-2 "activity" = range patience band (flat 30–70%) + enough round-trips.
    # Do NOT alias hygiene_ok to activity_ok — humanize_edgescore_blocker treats
    # hygiene as Survival/Hygiene WR and would show a false WR blocker.
    activity_ok = bool(flat_ok and round_trips_ok)
    hygiene_ok = True  # stage-2 does not use WR hygiene; WR is diagnostic only here
    entropy_required_after = int(getattr(cfg, "starship_entropy_required_after_ppo_steps", 500))
    if entropy is None:
        entropy_ok = int(ppo_steps) < max(0, entropy_required_after)
    else:
        entropy_ok = float(entropy) >= entropy_floor
    expectancy_ok = expectancy >= exp_floor
    passed = bool(
        volume_ok and constitution_ok and hygiene_ok and activity_ok and entropy_ok and expectancy_ok
    )
    score = max(
        0.0,
        min(
            1.0,
            0.30 * (1.0 if activity_ok else 0.0)
            + 0.25 * (1.0 if round_trips_ok else 0.0)
            + 0.25 * (1.0 if entropy_ok else 0.0)
            + 0.20 * max(0.0, min(1.0, (expectancy - exp_floor) / max(1e-6, abs(exp_floor) + 0.25))),
        ),
    )
    blockers: list[str] = []
    if not volume_ok:
        blockers.append(f"trades {trades_i}<{required}")
    if not constitution_ok:
        blockers.append(f"constitution_violations={constitution_violations}")
    if not flat_ok:
        blockers.append(f"flat {flat:.1%} outside 30–70%")
    elif not round_trips_ok:
        blockers.append(f"round_trips {range_round_trips}<{min_rt}")
    if not entropy_ok:
        blockers.append("entropy dead/missing")
    if not expectancy_ok:
        blockers.append(f"expectancy {expectancy:.3f} < {exp_floor:.3f}")
    message = (
        f"s2_edgescore={score:.3f} flat={flat:.1%} rt={range_round_trips} "
        f"exp={expectancy:.3f} trades={trades_i}/{required}"
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
    )
