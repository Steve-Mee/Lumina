"""Expectancy-oriented RL training reward SSOT (ADR-0019).

Training signal only — never broker economic PnL.

Components on trade close (birth + sim):
  1. quality      — R-multiple with win-size bonus vs rolling avg loss
  2. risk_adjusted — quality scaled down in high ATR context
  3. trend_bonus  — small bonus when trade direction aligns with trend_regime_strength
  4. portfolio    — drawdown penalty + rolling sharpe bonus (configurable)
  5. var_es       — optional sim risk penalty (applied by caller)

Formula:
  r_multiple = net_pnl / max(min_risk_usd, equity * stop_pct)
  quality    = expectancy_coeff * r_multiple [+ win bonus if net_pnl > avg_loss]
               or expectancy_coeff * r_multiple * loss_asymmetry_coeff on losses
  risk_adj   = quality / (1 + volatility_penalty_coeff * max(atr_norm, atr_floor))
  trend_bonus = trend_align_bonus_coeff * max(0, side * trend_regime_strength)
  reward     = clip(risk_adj - dd*dd_coeff + sharpe*sh_coeff + trend_bonus - var_es, ±clip)
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


@dataclass(slots=True)
class RewardShapingState:
    avg_win: float = 0.0
    avg_loss: float = 0.0
    drawdown: float = 0.0
    sharpe: float = 0.0
    recent_pnls: list[float] = field(default_factory=list)


def _risk_usd(*, equity: float, stop_pct: float, min_risk_usd: float) -> float:
    return max(float(min_risk_usd), float(equity) * max(float(stop_pct), 1e-6))


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


def compute_expectancy_reward(
    ctx: TradeCloseContext,
    state: RewardShapingState,
    cfg: BirthRewardConfig,
) -> tuple[float, dict[str, float]]:
    risk = _risk_usd(equity=ctx.equity, stop_pct=ctx.stop_pct, min_risk_usd=cfg.min_risk_usd)
    r_multiple = float(ctx.net_pnl) / risk

    if ctx.net_pnl > 0:
        quality = float(cfg.expectancy_coeff) * r_multiple
        if state.avg_loss > 0 and ctx.net_pnl > state.avg_loss:
            quality += float(cfg.quality_win_bonus_coeff) * (
                ctx.net_pnl / max(state.avg_loss, cfg.min_risk_usd)
            )
    else:
        quality = float(cfg.expectancy_coeff) * r_multiple * float(cfg.loss_asymmetry_coeff)

    vol_denom = 1.0 + float(cfg.volatility_penalty_coeff) * max(
        float(ctx.trend_atr_norm), float(cfg.atr_floor)
    )
    risk_adjusted = quality / vol_denom

    alignment = float(ctx.side) * float(ctx.trend_regime_strength)
    trend_bonus = float(cfg.trend_align_bonus_coeff) * max(0.0, alignment)

    drawdown_penalty = float(state.drawdown) * float(cfg.drawdown_penalty_coeff)
    sharpe_bonus = float(state.sharpe) * float(cfg.sharpe_bonus_coeff)

    raw = risk_adjusted - drawdown_penalty + sharpe_bonus + trend_bonus - float(ctx.var_es_penalty)
    clip = max(0.1, float(cfg.reward_clip))
    reward = float(max(-clip, min(clip, raw)))

    components = {
        "r_multiple": r_multiple,
        "quality": quality,
        "risk_adjusted": risk_adjusted,
        "trend_bonus": trend_bonus,
        "drawdown_penalty": drawdown_penalty,
        "sharpe_bonus": sharpe_bonus,
        "var_es_penalty": float(ctx.var_es_penalty),
        "raw_reward": raw,
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


def _is_range_regime(regime: str) -> bool:
    upper = str(regime or "NEUTRAL").upper()
    return upper in {"NEUTRAL", "RANGING"} or "RANGE" in upper


def range_patience_step_reward(
    *,
    regime: str,
    position_flat: bool,
    trade_closed: bool,
    cfg: BirthRewardConfig,
    stage_flat_ratio: float | None = None,
    expectancy_gap: float | None = None,
    trade_r_multiple: float | None = None,
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
    # Over-active (under-flat): classic patience shaping.
    if ratio < 0.30:
        if position_flat:
            bonus += flat_bonus
        if trade_closed:
            bonus -= churn_pen
        return bonus

    # In band: quality-first when expectancy gap (need better WR/R), else mild keep-alive.
    gap = max(0.0, float(expectancy_gap) if expectancy_gap is not None else 0.0)
    quality_mode = gap > 1e-9
    if quality_mode:
        # Suppress pure flat bonus that dilutes quality learning near band edges.
        if position_flat:
            bonus += flat_bonus * 0.05
        if trade_closed:
            r_mult = float(trade_r_multiple) if trade_r_multiple is not None else 0.0
            quality_scale = float(getattr(cfg, "range_quality_boost_coeff", 0.15) or 0.15)
            # Positive R-multiple: reinforce; negative: asymmetric penalty (quality stack).
            if r_mult > 0.0:
                bonus += quality_scale * min(2.0, r_mult)
            else:
                bonus -= churn_pen * (1.0 + min(2.0, abs(r_mult)))
                bonus -= quality_scale * min(1.5, abs(r_mult))
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
