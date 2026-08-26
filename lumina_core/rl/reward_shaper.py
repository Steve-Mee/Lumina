"""Expectancy-oriented RL training reward SSOT (ADR-0019).

Training signal only — never broker economic PnL.

Components on trade close (birth + sim):
  1. quality      — R-multiple with win-size bonus vs rolling avg loss
  2. risk_adjusted — quality scaled down in high ATR context
  3. direction_bonus — stage-aware:
       - trend curriculum: trend_align_bonus
       - range curriculum: mean-reversion (fade) bonus + WR-quality term
       - mixed: blend
  4. portfolio    — drawdown penalty + rolling sharpe bonus (configurable)
  5. var_es       — optional sim risk penalty (applied by caller)

When ``expectancy_gap`` > 0 (live WR−0.50 below floor), reinforce wins and
penalize losses more strongly so PPO optimizes the same physics as EdgeScore
pass (effective WR ≥ 35%), without lowering floors or faking wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.config import BirthRewardConfig


@dataclass(frozen=True, slots=True)
class TradeCloseContext:
    net_pnl: float
    equity: float
    stop_pct: float
    side: int
    trend_regime_strength: float = 0.0
    trend_atr_norm: float = 0.0
    var_es_penalty: float = 0.0
    curriculum_regime: str = ""
    expectancy_gap: float = 0.0
    tick_regime: str = ""
    risk_usd: float | None = None
    qty: int | None = None


@dataclass(slots=True)
class RewardShapingState:
    avg_win: float = 0.0
    avg_loss: float = 0.0
    drawdown: float = 0.0
    sharpe: float = 0.0
    recent_pnls: list[float] = field(default_factory=list)


def _risk_usd(
    *,
    equity: float,
    stop_pct: float,
    intended_risk_usd: float | None = None,
) -> float:
    """R denominator: intended stop risk, else equity × stop. Never a $25 floor."""
    if intended_risk_usd is not None and float(intended_risk_usd) > 1e-12:
        return float(intended_risk_usd)
    return abs(float(equity)) * max(abs(float(stop_pct)), 1e-9)


def update_trade_stats(state: RewardShapingState, net_pnl: float, *, window: int) -> None:
    if abs(net_pnl) <= 1e-12:
        return
    state.recent_pnls.append(float(net_pnl))
    cap = max(1, int(window))
    if len(state.recent_pnls) > cap:
        state.recent_pnls = state.recent_pnls[-cap:]
    wins = [p for p in state.recent_pnls if p > 0]
    losses = [abs(p) for p in state.recent_pnls if p < 0]
    state.avg_win = float(sum(wins) / len(wins)) if wins else 0.0
    state.avg_loss = float(sum(losses) / len(losses)) if losses else 0.0


def trend_features_from_tick(row: dict[str, Any]) -> tuple[float, float]:
    strength = float(row.get("trend_regime_strength", 0.0) or 0.0)
    atr_norm = float(row.get("trend_atr_norm", 0.0) or 0.0)
    return strength, atr_norm


def _is_range_regime(regime: str) -> bool:
    upper = str(regime or "NEUTRAL").upper()
    return upper in {"NEUTRAL", "RANGING"} or "RANGE" in upper


def _is_trend_regime(regime: str) -> bool:
    return "TREND" in str(regime or "").upper()


def _curriculum_is_range(curriculum_regime: str, tick_regime: str) -> bool:
    cur = str(curriculum_regime or "").strip().lower()
    if cur in {"range", "stage2_range", "stage2"}:
        return True
    if cur in {"trend", "stage1_trend", "stage1"}:
        return False
    if cur in {"mixed", "stage3_mixed", "stage3"}:
        return _is_range_regime(tick_regime)
    # Curriculum unset: only switch to mean-reversion when tick is explicitly range.
    # Empty tick → legacy trend_align (preserves ADR-0019 default for generic closes).
    tick = str(tick_regime or "").strip()
    if not tick:
        return False
    return _is_range_regime(tick) and not _is_trend_regime(tick)


def _direction_bonus(
    *,
    side: int,
    trend_regime_strength: float,
    cfg: BirthRewardConfig,
    curriculum_regime: str,
    tick_regime: str,
) -> tuple[float, str]:
    """Stage-aware directional bonus.

    Trend: reward with-trend entries.
    Range: reward fade (mean-reversion against short-horizon strength).
    """
    align_coeff = float(cfg.trend_align_bonus_coeff)
    if align_coeff <= 0.0:
        return 0.0, "none"
    strength = float(trend_regime_strength)
    side_f = float(side)
    if _curriculum_is_range(curriculum_regime, tick_regime):
        # Fade: long when strength negative (was selling off), short when positive.
        fade = side_f * (-strength)
        return align_coeff * max(0.0, fade), "mean_reversion"
    # Trend / default: classic alignment.
    alignment = side_f * strength
    return align_coeff * max(0.0, alignment), "trend_align"


def _wr_quality_term(
    *,
    net_pnl: float,
    state: RewardShapingState,
    expectancy_gap: float,
    cfg: BirthRewardConfig,
) -> float:
    """Extra signal when live expectancy is below floor — pure realized outcomes."""
    gap = max(0.0, float(expectancy_gap))
    if gap <= 1e-12:
        return 0.0
    # Scale with gap (0.05 gap → moderate; 0.20 gap → strong) and quality coeff.
    scale = float(getattr(cfg, "range_quality_boost_coeff", 0.15) or 0.15)
    intensity = min(1.0, gap / 0.20) * (1.0 + scale)
    recent = list(state.recent_pnls or [])
    if net_pnl > 0:
        # Reinforce wins more when window WR is weak.
        wins = sum(1 for p in recent if p > 0)
        n = max(1, len(recent))
        window_wr = float(wins) / float(n) if recent else 0.0
        under = max(0.0, 0.35 - window_wr)
        return intensity * (0.15 + 0.5 * under)
    # Losses: asymmetric quality penalty when under floor.
    return -intensity * (0.20 + 0.15 * min(1.0, abs(float(net_pnl)) / max(cfg.min_risk_usd, 1.0)))


def compute_expectancy_reward(
    ctx: TradeCloseContext,
    state: RewardShapingState,
    cfg: BirthRewardConfig,
) -> tuple[float, dict[str, float]]:
    intended = getattr(ctx, "risk_usd", None)
    risk = _risk_usd(
        equity=ctx.equity,
        stop_pct=ctx.stop_pct,
        intended_risk_usd=float(intended) if intended is not None else None,
    )
    r_multiple = float(ctx.net_pnl) / risk

    if ctx.net_pnl > 0:
        quality = float(cfg.expectancy_coeff) * r_multiple
        if state.avg_loss > 0 and ctx.net_pnl > state.avg_loss:
            quality += float(cfg.quality_win_bonus_coeff) * (
                ctx.net_pnl / max(state.avg_loss, cfg.min_risk_usd)
            )
    else:
        quality = float(cfg.expectancy_coeff) * r_multiple * float(cfg.loss_asymmetry_coeff)

    # When expectancy gap is open, amplify quality (wins up, losses more painful).
    gap = max(0.0, float(getattr(ctx, "expectancy_gap", 0.0) or 0.0))
    if gap > 1e-12:
        boost = 1.0 + min(0.75, gap / 0.20)
        if ctx.net_pnl > 0:
            quality *= boost
        else:
            quality *= 1.0 + min(0.50, gap / 0.25)

    vol_denom = 1.0 + float(cfg.volatility_penalty_coeff) * max(
        float(ctx.trend_atr_norm), float(cfg.atr_floor)
    )
    risk_adjusted = quality / vol_denom

    dir_bonus, dir_mode = _direction_bonus(
        side=int(ctx.side),
        trend_regime_strength=float(ctx.trend_regime_strength),
        cfg=cfg,
        curriculum_regime=str(getattr(ctx, "curriculum_regime", "") or ""),
        tick_regime=str(getattr(ctx, "tick_regime", "") or ""),
    )

    wr_term = _wr_quality_term(
        net_pnl=float(ctx.net_pnl),
        state=state,
        expectancy_gap=gap,
        cfg=cfg,
    )

    drawdown_penalty = float(state.drawdown) * float(cfg.drawdown_penalty_coeff)
    sharpe_bonus = float(state.sharpe) * float(cfg.sharpe_bonus_coeff)

    raw = (
        risk_adjusted
        - drawdown_penalty
        + sharpe_bonus
        + dir_bonus
        + wr_term
        - float(ctx.var_es_penalty)
    )
    clip = max(0.1, float(cfg.reward_clip))
    reward = float(max(-clip, min(clip, raw)))

    components = {
        "r_multiple": r_multiple,
        "quality": quality,
        "risk_adjusted": risk_adjusted,
        "trend_bonus": dir_bonus,  # legacy key for telemetry
        "direction_bonus": dir_bonus,
        "direction_mode": 1.0 if dir_mode == "mean_reversion" else 0.0,
        "wr_quality_term": wr_term,
        "drawdown_penalty": drawdown_penalty,
        "sharpe_bonus": sharpe_bonus,
        "var_es_penalty": float(ctx.var_es_penalty),
        "raw_reward": raw,
        "expectancy_gap": gap,
    }
    return reward, components


def hold_action_penalty(
    *,
    is_hold: bool,
    regime: str,
    plateau_active: bool,
    coeff: float = 0.002,
) -> float:
    """Small penalty for HOLD in trend regime during plateau recovery."""
    if not plateau_active or not is_hold:
        return 0.0
    if "TREND" not in str(regime or "").upper():
        return 0.0
    return -abs(float(coeff))


def range_patience_step_reward(
    *,
    regime: str,
    position_flat: bool,
    trade_closed: bool,
    cfg: BirthRewardConfig,
    stage_flat_ratio: float | None = None,
    expectancy_gap: float | None = None,
    trade_r_multiple: float | None = None,
    first_touch_training_pressure: float | None = None,
) -> float:
    """Birth stage 2 shaping: keep flat band 30–70% — not pure flat or pure churn.

    Forensics 2026-08-07/08: unconditional flat-bonus trained chronic 95%+ flat
    and blocked EdgeScore activity. Shape *toward* the band using live flat ratio.

    When occupancy is in-band but expectancy is below floor (``expectancy_gap`` > 0),
    shift from flat keep-alive to **quality** (R-multiple on close) so Stage-2 can
    graduate on the WR−0.50 expectancy gate without re-entering the 95% flat trap.
    """
    if not cfg.enabled or not _is_range_regime(regime):
        return 0.0
    flat_bonus = float(cfg.range_flat_bonus_coeff)
    churn_pen = float(cfg.range_churn_penalty_coeff)
    ratio = float(stage_flat_ratio) if stage_flat_ratio is not None else 0.5
    bonus = 0.0
    # Over-flat (under-activity): penalize remaining flat; reward being in a position.
    if ratio > 0.70:
        if position_flat:
            bonus -= flat_bonus * 1.5
        else:
            bonus += flat_bonus
        # Mild churn cost only — do not fight participation recovery.
        if trade_closed:
            bonus -= churn_pen * 0.25
        return bonus
    gap = max(0.0, float(expectancy_gap) if expectancy_gap is not None else 0.0)
    ft_press = max(
        0.0,
        float(first_touch_training_pressure)
        if first_touch_training_pressure is not None
        else 0.0,
    )
    r_mult = float(trade_r_multiple) if trade_r_multiple is not None else 0.0
    quality_scale = float(getattr(cfg, "range_quality_boost_coeff", 0.15) or 0.15)
    quality_scale *= 1.0 + min(1.0, gap / 0.15) if gap > 1e-9 else 1.0
    # Beat-random first-touch pressure (truthful intermediate; floors unchanged).
    if ft_press > 1e-9:
        quality_scale *= 1.0 + min(1.0, ft_press / 0.10)

    # Over-active (under-flat): free empty time + punish stop-outs / thrash re-entry.
    if ratio < 0.30:
        if position_flat:
            bonus += flat_bonus * (1.25 if gap > 1e-9 else 1.0)
        if trade_closed:
            # Mild churn when closing to free occupancy; heavy if closed as a loss/stop.
            if r_mult < 0.0:
                # Stop-out epidemic pressure (live: stops ≫ targets under over-trading).
                bonus -= churn_pen * (1.5 + min(2.5, abs(r_mult)))
                if gap > 1e-9:
                    bonus -= quality_scale * min(2.5, abs(r_mult))
            else:
                # Positive exit while under-band: good (freed risk + maybe win).
                bonus -= churn_pen * 0.35
                if r_mult > 0.0 and gap > 1e-9:
                    bonus += quality_scale * min(2.0, r_mult) * 0.5
        return bonus

    # In band: quality-first when expectancy gap or first-touch pressure.
    quality_mode = gap > 1e-9 or ft_press > 1e-9
    if quality_mode:
        # Suppress pure flat bonus that dilutes quality learning near band edges.
        if position_flat:
            bonus += flat_bonus * 0.05
        if trade_closed:
            # Positive R-multiple: reinforce targets; negative: asymmetric stop penalty.
            # Live forensics: stop:target ~4:1 — exit skill is the ceiling at −20% exp.
            if r_mult > 0.0:
                # PR-J/N: stronger target-taking bias near floor / flash-green hold.
                tgt_boost = 1.35 if (gap > 1e-9 or ft_press > 1e-9) else 1.25
                if gap > 1e-9 and ft_press > 1e-9:
                    tgt_boost = 1.45  # both pressures: keep first green hop
                bonus += quality_scale * min(2.5, r_mult) * tgt_boost
            else:
                bonus -= churn_pen * (1.35 + min(2.5, abs(r_mult)))
                bonus -= quality_scale * min(2.5, abs(r_mult)) * 1.15
        return bonus

    if position_flat:
        bonus += flat_bonus * 0.25
    if trade_closed:
        bonus -= churn_pen * 0.5
    return bonus


def compute_legacy_reward(
    *,
    net_pnl: float,
    drawdown: float,
    sharpe: float,
    drawdown_penalty_coeff: float,
    sharpe_bonus_coeff: float,
    var_es_penalty: float = 0.0,
) -> float:
    """REAL-mode and fallback: raw net PnL with portfolio shaping."""
    drawdown_penalty = float(drawdown) * float(drawdown_penalty_coeff)
    sharpe_bonus = float(sharpe) * float(sharpe_bonus_coeff)
    return float(net_pnl - drawdown_penalty + sharpe_bonus - var_es_penalty)
