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


def live_stage_winrate(*, wins: int, trades: int) -> float:
    """Honest live WR from closed trades. Never getattr(session, 'stage_winrate')."""
    n = max(1, int(trades))
    return float(max(0, int(wins))) / float(n)


def _humanize_durable_lifetime_blocker(
    *,
    cfg: BirthCurriculumConfig,
    is_stage3: bool,
    is_stage2: bool,
    lifetime: float,
    rolling: float | None,
    score_pct: str,
    wr_label: str,
    hygiene: float,
) -> str:
    """Operator copy when rolling looks green but lifetime C-band fails."""
    if is_stage3:
        wr_floor = float(getattr(cfg, "stage3_winrate_floor", 0.35) or 0.35)
        delta = float(getattr(cfg, "stage3_pass_lifetime_delta", 0.05) or 0.05)
    elif is_stage2:
        wr_floor = float(hygiene)
        delta = float(getattr(cfg, "stage2_pass_lifetime_delta", 0.05) or 0.05)
    else:
        wr_floor = float(hygiene)
        delta = 0.05
    delta = max(0.0, min(0.15, delta))
    life_min = wr_floor - delta
    roll_txt = f"{float(rolling):.0%}" if rolling is not None else "n/a"
    return (
        f"Durable lifetime WR {lifetime:.1%} < {life_min:.0%} "
        f"(rolling {roll_txt} does not pass alone; need ≥{life_min:.0%} lifetime "
        f"when rolling lifts past {wr_floor:.0%} {wr_label}) | EdgeScore {score_pct}"
    )


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
    stage: str | None = None,
) -> str:
    """Operator-facing EdgeScore block reason (percentages, no debug dump)."""
    score_pct = f"{float(edge.score) * 100.0:.0f}%"
    exp = compute_expectancy_proxy(
        wins=int(wins),
        trades=int(trades),
        rolling_winrate=rolling_winrate,
    )
    stage_key = str(stage or "").strip().lower()
    is_stage2 = stage_key in {"stage2_range", "stage2", "range", "2"}
    is_stage3 = stage_key in {"stage3_mixed", "stage3", "mixed", "3"}
    survival = bool(getattr(cfg, "birth_survival_pass_enabled", True)) and not is_stage2 and not is_stage3
    if is_stage3:
        exp_floor = float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15)
        hygiene = float(getattr(cfg, "stage3_winrate_floor", 0.35) or 0.35)
        wr_label = "Mixed quality WR"
    elif is_stage2:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        exp_floor = stage2_expectancy_floor(cfg)
        hygiene = float(exp_floor) + 0.50  # WR−0.50 scale → hygiene WR equivalent
        wr_label = "Range quality WR"
    elif survival:
        exp_floor = float(getattr(cfg, "birth_survival_expectancy_floor", -0.50))
        hygiene = float(getattr(cfg, "birth_survival_wr_floor", 0.20))
        wr_label = "Survival WR"
    else:
        exp_floor = float(getattr(cfg, "stage1_expectancy_floor", -0.15))
        hygiene = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35))
        wr_label = "Hygiene WR"
    # Stage-2: activity before hygiene so occupancy is not mislabeled Survival WR
    # (S2 hygiene_ok is always True). Stage-3: hygiene WR is a real pass-gate —
    # report it before occupancy/settlement (matches compute_stage_blocker).
    if not edge.activity_ok and not is_stage3:
        msg_l = (edge.message or "").lower()
        if "settlement" in msg_l:
            return (
                f"Settlement honesty (need stop/target/time-stop share ≥70%) "
                f"| EdgeScore {score_pct}"
            )
        return f"Flat/hold outside 30–70% activity band | EdgeScore {score_pct}"
    if not edge.hygiene_ok:
        lifetime = float(wins) / float(max(1, int(trades)))
        roll_disp = (
            float(rolling_winrate_display)
            if rolling_winrate_display is not None
            else (float(rolling_winrate) if rolling_winrate is not None else None)
        )
        if not bool(getattr(edge, "durable_ok", True)):
            return _humanize_durable_lifetime_blocker(
                cfg=cfg,
                is_stage3=is_stage3,
                is_stage2=is_stage2,
                lifetime=lifetime,
                rolling=roll_disp,
                score_pct=score_pct,
                wr_label=wr_label,
                hygiene=hygiene,
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
                f"{wr_label} {detail} (need >={hygiene:.0%}; "
                f"rolling counts after {need}) | EdgeScore {score_pct}"
            )
        return f"{wr_label} {detail} (need >={hygiene:.0%}) | EdgeScore {score_pct}"
    if is_stage3 and not edge.activity_ok:
        msg_l = (edge.message or "").lower()
        if "settlement" in msg_l:
            return (
                f"Settlement honesty (need stop/target/time-stop share ≥70%) "
                f"| EdgeScore {score_pct}"
            )
        if "under-activity" in msg_l:
            return f"Occupancy too empty (flat >75%) | EdgeScore {score_pct}"
        if "over-trading" in msg_l or "flat" in msg_l:
            return f"Occupancy outside 25–75% mixed band | EdgeScore {score_pct}"
        return f"Occupancy/settlement outside early-quality band | EdgeScore {score_pct}"
    if not edge.entropy_ok:
        if entropy is None:
            return f"Entropy missing | EdgeScore {score_pct}"
        return f"Entropy dead (H={float(entropy):.3f}) | EdgeScore {score_pct}"
    if not edge.expectancy_ok:
        lifetime = float(wins) / float(max(1, int(trades)))
        roll_disp = (
            float(rolling_winrate_display)
            if rolling_winrate_display is not None
            else (float(rolling_winrate) if rolling_winrate is not None else None)
        )
        if not bool(getattr(edge, "durable_ok", True)):
            return _humanize_durable_lifetime_blocker(
                cfg=cfg,
                is_stage3=is_stage3,
                is_stage2=is_stage2,
                lifetime=lifetime,
                rolling=roll_disp,
                score_pct=score_pct,
                wr_label=wr_label,
                hygiene=hygiene,
            )
        # Prefer EdgeScore dual-truth leg when present (skill vs rolling).
        exp_use = float(exp)
        try:
            pe = getattr(edge, "pass_expectancy", None)
            if pe is not None:
                exp_use = float(pe)
        except Exception:
            pass
        wr_equiv = float(exp_use) + 0.50
        src = str(getattr(edge, "pass_expectancy_source", "") or "").strip()
        src_bit = f" src={src}" if src else ""
        return (
            f"Expectancy {exp_use * 100.0:.0f}% (need >= {exp_floor * 100.0:.0f}%; "
            f"≡ {wr_label} >={hygiene:.0%}, now {wr_equiv:.0%}{src_bit}) "
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


def publish_edgescore_champion_fields(
    *,
    best_edgescore: float,
    best_edgescore_at_trade: int,
    best_edgescore_policy_path: str = "",
    stage_trades: int,
    required: int,
    cfg: BirthCurriculumConfig,
) -> dict[str, object]:
    """Progress fields for champion EdgeScore — honest null until locked.

    Writing 0.0 before eligibility made the UI show "Champion EdgeScore 0%" which
    operators read as a real score. Prefer null + min-trades hint until a champion
    is actually frozen after pass-gate volume.
    """
    min_trades = edgescore_champion_min_trades(int(required), cfg)
    best = float(best_edgescore or 0.0)
    at_trade = int(best_edgescore_at_trade or 0)
    locked = best > 0.0 and at_trade > 0 and at_trade >= min_trades
    return {
        "best_edgescore": round(best, 4) if locked else None,
        "best_edgescore_at_trade": at_trade if locked else 0,
        "best_edgescore_policy_path": (
            str(best_edgescore_policy_path or "").strip() if locked else ""
        ),
        "edgescore_champion_min_trades": int(min_trades),
        "edgescore_champion_locked": bool(locked),
    }


def sanitize_edgescore_champion(
    *,
    best_edgescore: float,
    best_edgescore_at_trade: int,
    best_winrate: float,
    required: int,
    cfg: BirthCurriculumConfig,
    stage: str | None = None,
    live_winrate: float | None = None,
) -> tuple[float, int, bool]:
    """Clear poisoned early EdgeScore champions (noise on small N).

    Returns ``(best_edgescore, best_edgescore_at_trade, cleared)``.
    When ``cleared``, caller must also drop ``best_edgescore_policy_path``.
    """
    best = float(best_edgescore or 0.0)
    at_trade = int(best_edgescore_at_trade or 0)
    wr = float(best_winrate or 0.0)
    if live_winrate is not None:
        try:
            wr = min(wr, float(live_winrate)) if wr > 0 else float(live_winrate)
        except (TypeError, ValueError):
            wr = float(best_winrate or 0.0)
    if best <= 0.0:
        return 0.0, 0, False
    min_trades = edgescore_champion_min_trades(int(required), cfg)
    stage_key = str(stage or "").strip().lower()
    is_stage2 = stage_key in {"stage2_range", "stage2", "range", "2"}
    is_stage3 = stage_key in {"stage3_mixed", "stage3", "mixed", "3"}
    if is_stage2:
        try:
            from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

            hygiene = float(stage2_expectancy_floor(cfg)) + 0.50
        except Exception:
            hygiene = 0.35
    elif is_stage3:
        hygiene = float(getattr(cfg, "stage3_winrate_floor", 0.35) or 0.35)
    else:
        survival = bool(getattr(cfg, "birth_survival_pass_enabled", True))
        if survival:
            hygiene = float(getattr(cfg, "birth_survival_wr_floor", 0.20) or 0.20)
        else:
            hygiene = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35) or 0.35)
    # Occupancy+entropy without quality. Stage-2 used to saturate at 0.80 because
    # round_trips were double-counted (PID 33628 theater).
    occupancy_only_ceiling = 0.50
    poisoned_early = at_trade > 0 and at_trade < min_trades
    poisoned_missing_trade = at_trade <= 0 and best > occupancy_only_ceiling
    poisoned_inconsistent = best > occupancy_only_ceiling and wr + 1e-9 < hygiene
    if poisoned_early or poisoned_missing_trade or poisoned_inconsistent:
        reason = (
            "early_trades"
            if poisoned_early
            else ("missing_at_trade" if poisoned_missing_trade else "inconsistent_wr")
        )
        logger.warning(
            "birth.starship.champion_sanitized reason=%s best_edge=%.3f at_trade=%s "
            "min=%s wr=%.1f%% hygiene=%.0f%%",
            reason,
            best,
            at_trade,
            min_trades,
            wr * 100.0,
            hygiene * 100.0,
        )
        return 0.0, 0, True
    return best, at_trade, False
