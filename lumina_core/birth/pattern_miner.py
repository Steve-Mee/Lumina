"""Hindsight oracle pattern miner for Birth Research Oracle (BRO).

Stop/target are auto-calibrated to the tick universe. Fixed 0.75%/1.3% stops
never hit on 1-min MES (median move ~0.15%) and produced permanent patterns=0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from lumina_core.birth.bible_observation import bible_features_for_tick
from lumina_core.birth.birth_trade_geometry import (
    calibrate_oracle_stops,
    estimate_round_trip_cost_usd,
)
from lumina_core.birth.config import BirthRewardConfig, load_birth_v2_config
from lumina_core.birth.curriculum import CurriculumStage, filter_ticks_for_stage
from lumina_core.logging_utils import get_logger
from lumina_core.rl.observation_builder import build_observation_vector
from lumina_core.rl.reward_shaper import (
    RewardShapingState,
    TradeCloseContext,
    compute_expectancy_reward,
    trend_features_from_tick,
    update_trade_stats,
)

logger = get_logger("lumina.birth.pattern_miner")

# Legacy defaults — only used if auto-calib fails and caller forces fixed mode.
_LEGACY_STOP_PCT = 0.0075
_LEGACY_TARGET_PCT = 0.013
_POINT_VALUE = 5.0  # MES-like SIM scale for oracle PnL ranking


@dataclass(slots=True)
class PatternMineResult:
    patterns: list[dict[str, Any]]
    wins: int
    scanned: int
    regimes_seen: set[str]
    stop_pct: float = 0.0
    target_pct: float = 0.0
    max_hold_bars: int = 0
    reason: str = ""
    pool_size: int = 0


def _tick_price(tick: dict[str, Any]) -> float:
    try:
        return float(tick.get("last") or tick.get("close") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _simulate_outcome(
    ticks: list[dict[str, Any]],
    entry_idx: int,
    side: int,
    *,
    stop_pct: float,
    target_pct: float,
    max_hold_bars: int,
) -> tuple[float, int] | None:
    """Path-dependent stop/target; if neither hits, use end-of-horizon PnL (signed)."""
    entry = _tick_price(ticks[entry_idx])
    if entry <= 0:
        return None
    end = min(len(ticks), entry_idx + max_hold_bars + 1)
    last_j = entry_idx
    last_price = entry
    for j in range(entry_idx + 1, end):
        price = _tick_price(ticks[j])
        if price <= 0:
            continue
        last_j = j
        last_price = price
        if side > 0:
            move = (price - entry) / entry
            if move <= -stop_pct:
                return -stop_pct * entry * _POINT_VALUE, j
            if move >= target_pct:
                return target_pct * entry * _POINT_VALUE, j
        else:
            move = (entry - price) / entry
            if move <= -stop_pct:
                return -stop_pct * entry * _POINT_VALUE, j
            if move >= target_pct:
                return target_pct * entry * _POINT_VALUE, j
    if last_j <= entry_idx or last_price <= 0:
        return None
    # Horizon exit: signed PnL (only winners kept by caller via min_pnl_usd)
    if side > 0:
        pnl = (last_price - entry) * _POINT_VALUE
    else:
        pnl = (entry - last_price) * _POINT_VALUE
    return float(pnl), last_j


def mine_winning_patterns(
    *,
    ticks: list[dict[str, Any]],
    stage: CurriculumStage,
    runtime: Any,
    workspace_root: Any = None,
    max_patterns: int = 5000,
    min_pnl_usd: float = 0.01,
    scan_stride: int = 5,
    max_hold_bars: int = 90,
    stop_pct: float | None = None,
    target_pct: float | None = None,
    auto_calibrate: bool = True,
    net_of_cost: bool = True,
    min_net_pnl_usd: float | None = None,
) -> PatternMineResult:
    """Scan historical ticks for hindsight-profitable entries (oracle labeling).

    When ``net_of_cost`` is True (default), winners must clear round-trip cost
    (same fee/slip model as geometry) plus ``min_net_pnl_usd`` (or ``min_pnl_usd``).
    Prevents flooding PPO with gross-only micro "wins" that are -$EV after costs.
    """
    pool = filter_ticks_for_stage(stage, ticks)
    if not pool:
        pool = list(ticks)
    if len(pool) < 30:
        return PatternMineResult(
            patterns=[],
            wins=0,
            scanned=0,
            regimes_seen=set(),
            reason="pool_too_small",
            pool_size=len(pool),
            max_hold_bars=int(max_hold_bars),
        )

    hold = max(30, int(max_hold_bars))
    if auto_calibrate or stop_pct is None or target_pct is None:
        cal_stop, cal_target = calibrate_oracle_stops(pool, max_hold_bars=hold)
        use_stop = float(stop_pct) if stop_pct is not None and not auto_calibrate else cal_stop
        use_target = float(target_pct) if target_pct is not None and not auto_calibrate else cal_target
    else:
        use_stop = float(stop_pct)
        use_target = float(target_pct)

    # Guard against legacy mis-calibration when caller still passes 0.75%/1.3%.
    if use_stop >= 0.005 and auto_calibrate:
        cal_stop, cal_target = calibrate_oracle_stops(pool, max_hold_bars=hold)
        use_stop, use_target = cal_stop, cal_target
    # Explicit stage geometry that is still macro-scale: re-derive from pool
    # (never silently train oracle on 0.75% when ticks support micro stops).
    if use_stop >= 0.005 and not auto_calibrate and len(pool) >= 40:
        cal_stop, cal_target = calibrate_oracle_stops(pool, max_hold_bars=hold)
        if cal_stop < 0.005:
            use_stop, use_target = cal_stop, cal_target

    enriched: list[dict[str, Any]] = []
    for row in pool:
        tick = dict(row)
        c, n, s, m = bible_features_for_tick(tick, workspace_root=workspace_root)
        tick["bible_confluence"] = c
        tick["bible_news_proximity"] = n
        tick["bible_session_phase"] = s
        tick["bible_mtf_bias"] = m
        enriched.append(tick)

    patterns: list[dict[str, Any]] = []
    regimes_seen: set[str] = set()
    scanned = 0
    stride = max(1, int(scan_stride))
    cap = max(1, int(max_patterns))
    reward_cfg: BirthRewardConfig = load_birth_v2_config(workspace_root).reward
    reward_state = RewardShapingState()
    hits = 0
    winners = 0
    # Net edge floor: require positive edge after same cost model as gym/geometry.
    net_floor = float(min_net_pnl_usd) if min_net_pnl_usd is not None else float(min_pnl_usd)
    net_floor = max(0.0, net_floor)

    for i in range(20, len(enriched) - hold - 1, stride):
        scanned += 1
        for side, signal in ((1, "BUY"), (-1, "SELL")):
            outcome = _simulate_outcome(
                enriched,
                i,
                side,
                stop_pct=use_stop,
                target_pct=use_target,
                max_hold_bars=hold,
            )
            if outcome is None:
                continue
            hits += 1
            pnl, exit_idx = outcome
            entry_px = _tick_price(enriched[i])
            if bool(net_of_cost) and entry_px > 0:
                cost_usd = estimate_round_trip_cost_usd(price=entry_px)
                net_pnl = float(pnl) - float(cost_usd)
                if net_pnl < net_floor:
                    continue
                pnl = net_pnl  # store net for reward ranking / buffer priority
            elif pnl < min_pnl_usd:
                continue
            winners += 1

            row = enriched[i]
            regime = str(row.get("regime", "NEUTRAL"))
            regimes_seen.add(regime)
            try:
                obs = build_observation_vector(
                    row=row,
                    engine=runtime,
                    data=enriched,
                    idx=i,
                    position=0,
                    qty=1,
                    entry_price=_tick_price(row),
                    equity=50_000.0,
                    drawdown=0.0,
                    rolling_sharpe=0.0,
                    trade_mode="birth",
                )
                exit_row = enriched[min(exit_idx, len(enriched) - 1)]
                next_obs = build_observation_vector(
                    row=exit_row,
                    engine=runtime,
                    data=enriched,
                    idx=exit_idx,
                    position=side,
                    qty=1,
                    entry_price=_tick_price(row),
                    equity=50_000.0 + pnl,
                    drawdown=0.0,
                    rolling_sharpe=0.0,
                    trade_mode="birth",
                )
                obs_list = obs.tolist()
                next_list = next_obs.tolist()
            except Exception:
                # Fail soft: still count pattern with price-only stub for buffer learning.
                px = _tick_price(row)
                obs_list = [px, float(side), use_stop, use_target]
                next_list = [_tick_price(enriched[min(exit_idx, len(enriched) - 1)]), float(side), 0.0, 0.0]

            trend_strength, atr_norm = trend_features_from_tick(row)
            if reward_cfg.enabled:
                try:
                    ctx = TradeCloseContext(
                        net_pnl=float(pnl),
                        equity=50_000.0,
                        stop_pct=use_stop,
                        side=side,
                        trend_regime_strength=trend_strength,
                        trend_atr_norm=atr_norm,
                    )
                    reward_state.drawdown = 0.0
                    reward_state.sharpe = 0.0
                    reward, _components = compute_expectancy_reward(ctx, reward_state, reward_cfg)
                    update_trade_stats(reward_state, float(pnl), window=reward_cfg.rolling_trade_window)
                except Exception:
                    reward = float(np.clip(pnl / 50.0, -5.0, 5.0))
            else:
                reward = float(np.clip(pnl / 50.0, -5.0, 5.0))
            patterns.append(
                {
                    "observation": {"vector": obs_list, "price": _tick_price(row)},
                    "action": {"signal": signal},
                    "reward": reward,
                    "next_observation": {
                        "vector": next_list,
                        "price": _tick_price(enriched[min(exit_idx, len(enriched) - 1)]),
                    },
                    "done": True,
                    "pnl": pnl,
                    "regime": regime,
                    "source": "oracle",
                    "news_window_active": float(row.get("news_window_active", 0.0) or 0.0),
                }
            )
            if len(patterns) >= cap:
                reason = "ok_capped"
                logger.info(
                    "birth.oracle.mine scanned=%s patterns=%s wins=%s hits=%s "
                    "stop=%.4f%% target=%.4f%% hold=%s pool=%s reason=%s",
                    scanned,
                    len(patterns),
                    winners,
                    hits,
                    use_stop * 100.0,
                    use_target * 100.0,
                    hold,
                    len(enriched),
                    reason,
                )
                return PatternMineResult(
                    patterns=patterns,
                    wins=len(patterns),
                    scanned=scanned,
                    regimes_seen=regimes_seen,
                    stop_pct=use_stop,
                    target_pct=use_target,
                    max_hold_bars=hold,
                    reason=reason,
                    pool_size=len(enriched),
                )

    reason = "ok" if patterns else ("no_hits" if hits == 0 else "no_winners_above_min_pnl")
    logger.info(
        "birth.oracle.mine scanned=%s patterns=%s wins=%s hits=%s "
        "stop=%.4f%% target=%.4f%% hold=%s pool=%s reason=%s",
        scanned,
        len(patterns),
        winners,
        hits,
        use_stop * 100.0,
        use_target * 100.0,
        hold,
        len(enriched),
        reason,
    )
    return PatternMineResult(
        patterns=patterns,
        wins=len(patterns),
        scanned=scanned,
        regimes_seen=regimes_seen,
        stop_pct=use_stop,
        target_pct=use_target,
        max_hold_bars=hold,
        reason=reason,
        pool_size=len(enriched),
    )
