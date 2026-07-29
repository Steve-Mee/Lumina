"""Starship EdgeScore champion eligibility + poison sanitize + humanize."""
from __future__ import annotations


from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_edgescore_core import (
    EdgeScoreResult,
    compute_expectancy_proxy,
    rolling_pass_min_covered,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.starship_edgescore")


def humanize_edgescore_blocker(
    edge: EdgeScoreResult,
    *,
    cfg: BirthCurriculumConfig,
    wins: int,
    trades: int,
    entropy: float | None = None,
    rolling_winrate: float | None = None,
    rolling_winrate_display: float | None = None,
    rolling_wr_eligible: bool | None = None,
    rolling_min_covered: int | None = None,
) -> str:
    """Operator-facing EdgeScore block reason (percentages, no debug dump)."""
    score_pct = f"{float(edge.score) * 100.0:.0f}%"
    exp = compute_expectancy_proxy(
        wins=int(wins),
        trades=int(trades),
        rolling_winrate=rolling_winrate,
    )
    exp_floor = float(getattr(cfg, "stage1_expectancy_floor", -0.15))
    hygiene = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35))
    if not edge.hygiene_ok:
        lifetime = float(wins) / float(max(1, int(trades)))
        roll_disp = (
            float(rolling_winrate_display)
            if rolling_winrate_display is not None
            else (float(rolling_winrate) if rolling_winrate is not None else None)
        )
        parts = [f"lifetime {lifetime:.0%}"]
        if roll_disp is not None:
            parts.append(f"rolling {roll_disp:.0%}")
        detail = " / ".join(parts)
        if rolling_wr_eligible is False:
            need = int(rolling_min_covered) if rolling_min_covered is not None else rolling_pass_min_covered(
                int(getattr(cfg, "stage1_rolling_pass_window", 500) or 500)
            )
            return (
                f"Hygiene WR {detail} (need >={hygiene:.0%}; "
                f"rolling counts after {need}) | EdgeScore {score_pct}"
            )
        return f"Hygiene WR {detail} (need >={hygiene:.0%}) | EdgeScore {score_pct}"
    if not edge.activity_ok:
        return f"Hold outside activity band | EdgeScore {score_pct}"
    if not edge.entropy_ok:
        if entropy is None:
            return f"Entropy missing | EdgeScore {score_pct}"
        return f"Entropy dead (H={float(entropy):.3f}) | EdgeScore {score_pct}"
    if not edge.expectancy_ok:
        return (
            f"Expectancy {exp * 100.0:.0f}% (need >= {exp_floor * 100.0:.0f}%) "
            f"| EdgeScore {score_pct}"
        )
    if not edge.constitution_ok:
        return f"Constitution violations | EdgeScore {score_pct}"
    return f"EdgeScore {score_pct} incomplete"


def edgescore_champion_min_trades(required: int, cfg: BirthCurriculumConfig) -> int:
    """Min stage trades before an EdgeScore champion may be locked / frozen."""
    min_snap = max(1, int(getattr(cfg, "plateau_best_policy_min_trades", 200) or 200))
    return max(max(1, int(required)), min_snap)


def is_edgescore_champion_eligible(
    *,
    stage_trades: int,
    required: int,
    cfg: BirthCurriculumConfig,
) -> bool:
    """True only after pass-gate volume — blocks early noise champions."""
    return int(stage_trades) >= edgescore_champion_min_trades(int(required), cfg)


def sanitize_edgescore_champion(
    *,
    best_edgescore: float,
    best_edgescore_at_trade: int,
    best_winrate: float,
    required: int,
    cfg: BirthCurriculumConfig,
) -> tuple[float, int, bool]:
    """Clear poisoned early EdgeScore champions (noise on small N).

    Returns ``(best_edgescore, best_edgescore_at_trade, cleared)``.
    When ``cleared``, caller must also drop ``best_edgescore_policy_path``.
    """
    best = float(best_edgescore or 0.0)
    at_trade = int(best_edgescore_at_trade or 0)
    wr = float(best_winrate or 0.0)
    if best <= 0.0:
        return 0.0, 0, False
    min_trades = edgescore_champion_min_trades(int(required), cfg)
    hygiene = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35) or 0.35)
    # Score with activity+entropy only (no WR term) saturates at 0.45.
    activity_entropy_floor = 0.45
    poisoned_early = at_trade > 0 and at_trade < min_trades
    poisoned_missing_trade = at_trade <= 0 and best > activity_entropy_floor
    # High EdgeScore implies WR above hygiene; plateau WR far below → inconsistent.
    poisoned_inconsistent = best > activity_entropy_floor and wr + 1e-9 < hygiene
    if poisoned_early or poisoned_missing_trade or poisoned_inconsistent:
        reason = (
            "early_trades"
            if poisoned_early
            else ("missing_at_trade" if poisoned_missing_trade else "inconsistent_wr")
        )
        logger.warning(
            "birth.starship.champion_sanitized reason=%s best_edge=%.3f at_trade=%s "
            "min=%s best_wr=%.1f%%",
            reason,
            best,
            at_trade,
            min_trades,
            wr * 100.0,
        )
        return 0.0, 0, True
    return best, at_trade, False
