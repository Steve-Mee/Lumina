"""Starship Stage-1 EdgeScore evaluator."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
)


def evaluate_stage1_edgescore(
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
    soft_block_rate_per_1k: float | None = None,
) -> EdgeScoreResult:
    """Fail-closed Stage-1 EdgeScore.

    Birth survival mode (default): grade *reflex/survival* (legal plant, entropy,
    loose expectancy) — not pro daytrader hygiene 35%. Skill floors apply when
    ``birth_survival_pass_enabled`` is false (Playground+).
    """
    trades_i = max(0, int(trades))
    wins_i = max(0, int(wins))
    winrate = float(wins_i) / float(max(1, trades_i))
    roll = float(rolling_winrate) if rolling_winrate is not None else winrate
    if hold_ratio is not None:
        hold_ratio_v = float(hold_ratio)
    else:
        hold_ratio_v = float(hold_signals) / float(max(1, total_signals))
    hold_ratio = hold_ratio_v
    survival = bool(getattr(cfg, "birth_survival_pass_enabled", True))
    if survival:
        hygiene = float(getattr(cfg, "birth_survival_wr_floor", 0.20))
        exp_floor = float(getattr(cfg, "birth_survival_expectancy_floor", -0.50))
    else:
        hygiene = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35))
        exp_floor = float(getattr(cfg, "stage1_expectancy_floor", -0.15))
    hold_min = float(getattr(cfg, "stage1_hold_ratio_min", 0.05))
    hold_max = float(getattr(cfg, "stage1_hold_ratio_max", 0.85))
    entropy_floor = float(getattr(cfg, "stage1_entropy_floor", 0.05))
    plant_max = float(getattr(cfg, "birth_plant_soft_block_rate_max_per_1k", 100.0))
    expectancy = compute_expectancy_proxy(
        wins=wins_i,
        trades=trades_i,
        total_pnl=total_pnl,
        rolling_winrate=rolling_winrate,
    )

    constitution_ok = int(constitution_violations) == 0
    volume_ok = trades_i >= max(1, int(required))
    hygiene_ok = winrate >= hygiene or roll >= hygiene
    activity_ok = hold_min <= hold_ratio <= hold_max
    # Cold start / unit tests: unknown entropy OK until PPO has produced steps.
    entropy_required_after = int(getattr(cfg, "starship_entropy_required_after_ppo_steps", 500))
    if entropy is None:
        entropy_ok = int(ppo_steps) < max(0, entropy_required_after)
    else:
        entropy_ok = float(entropy) >= entropy_floor
    expectancy_ok = expectancy >= exp_floor
    if soft_block_rate_per_1k is None:
        plant_ok = True
    else:
        plant_ok = float(soft_block_rate_per_1k) <= plant_max

    passed = bool(
        volume_ok
        and constitution_ok
        and hygiene_ok
        and activity_ok
        and entropy_ok
        and expectancy_ok
        and plant_ok
    )
    # Score in [0, 1] for swarm ranking / lift checks. WR term uses effective hygiene WR.
    effective_wr = max(winrate, float(roll))
    score = max(
        0.0,
        min(
            1.0,
            0.35 * max(0.0, min(1.0, (effective_wr - hygiene) / max(1e-6, 0.50 - hygiene)))
            + 0.25 * (1.0 if activity_ok else 0.0)
            + 0.20 * (1.0 if entropy_ok else 0.0)
            + 0.20 * max(0.0, min(1.0, (expectancy - exp_floor) / max(1e-6, abs(exp_floor) + 0.25))),
        ),
    )
    blockers: list[str] = []
    if not volume_ok:
        blockers.append(f"trades {trades_i}<{required}")
    if not constitution_ok:
        blockers.append(f"constitution_violations={constitution_violations}")
    if not hygiene_ok:
        mode = "survival" if survival else "skill"
        blockers.append(f"{mode} wr {winrate:.1%}/{roll:.1%} < {hygiene:.0%}")
    if not activity_ok:
        blockers.append(f"hold {hold_ratio:.1%} outside {hold_min:.0%}–{hold_max:.0%}")
    if not entropy_ok:
        if entropy is None:
            blockers.append(
                f"entropy missing after ppo_steps={int(ppo_steps)}>={entropy_required_after}"
            )
        else:
            blockers.append(f"entropy {float(entropy):.3f} < {entropy_floor:.3f}")
    if not expectancy_ok:
        blockers.append(f"expectancy {expectancy:.3f} < {exp_floor:.3f}")
    if not plant_ok:
        blockers.append(
            f"plant soft_block_rate {float(soft_block_rate_per_1k):.1f}/1k > {plant_max:.0f}"
        )
    message = (
        f"edgescore={score:.3f} wr={winrate:.1%} hold={hold_ratio:.1%} "
        f"exp={expectancy:.3f} entropy={entropy if entropy is not None else 'n/a'} "
        f"trades={trades_i}/{required}"
        + (f" mode={'survival' if survival else 'skill'}")
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
