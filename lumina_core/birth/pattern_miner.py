"""Hindsight oracle pattern miner for Birth Research Oracle (BRO)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from lumina_core.birth.bible_observation import bible_features_for_tick
from lumina_core.birth.curriculum import CurriculumStage, filter_ticks_for_stage
from lumina_core.rl.observation_builder import build_observation_vector

_DEFAULT_STOP_PCT = 0.0075
_DEFAULT_TARGET_PCT = 0.013
_POINT_VALUE = 5.0  # MES-like SIM scale for oracle PnL ranking


@dataclass(slots=True)
class PatternMineResult:
    patterns: list[dict[str, Any]]
    wins: int
    scanned: int
    regimes_seen: set[str]


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
    entry = _tick_price(ticks[entry_idx])
    if entry <= 0:
        return None
    end = min(len(ticks), entry_idx + max_hold_bars + 1)
    for j in range(entry_idx + 1, end):
        price = _tick_price(ticks[j])
        if price <= 0:
            continue
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
    return None


def mine_winning_patterns(
    *,
    ticks: list[dict[str, Any]],
    stage: CurriculumStage,
    runtime: Any,
    workspace_root: Any = None,
    max_patterns: int = 5000,
    min_pnl_usd: float = 0.01,
    scan_stride: int = 5,
    max_hold_bars: int = 120,
    stop_pct: float = _DEFAULT_STOP_PCT,
    target_pct: float = _DEFAULT_TARGET_PCT,
) -> PatternMineResult:
    """Scan historical ticks for hindsight-profitable entries (oracle labeling)."""
    pool = filter_ticks_for_stage(stage, ticks)
    if not pool:
        pool = list(ticks)
    if len(pool) < 30:
        return PatternMineResult(patterns=[], wins=0, scanned=0, regimes_seen=set())

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

    for i in range(20, len(enriched) - max_hold_bars - 1, stride):
        scanned += 1
        for side, signal in ((1, "BUY"), (-1, "SELL")):
            outcome = _simulate_outcome(
                enriched,
                i,
                side,
                stop_pct=stop_pct,
                target_pct=target_pct,
                max_hold_bars=max_hold_bars,
            )
            if outcome is None:
                continue
            pnl, exit_idx = outcome
            if pnl < min_pnl_usd:
                continue

            row = enriched[i]
            regime = str(row.get("regime", "NEUTRAL"))
            regimes_seen.add(regime)
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
            reward = float(np.clip(pnl / 100.0, -5.0, 5.0))
            patterns.append(
                {
                    "observation": {"vector": obs.tolist(), "price": _tick_price(row)},
                    "action": {"signal": signal},
                    "reward": reward,
                    "next_observation": {"vector": next_obs.tolist(), "price": _tick_price(exit_row)},
                    "done": True,
                    "pnl": pnl,
                    "regime": regime,
                    "source": "oracle",
                    "news_window_active": float(row.get("news_window_active", 0.0) or 0.0),
                }
            )
            if len(patterns) >= cap:
                return PatternMineResult(
                    patterns=patterns,
                    wins=len(patterns),
                    scanned=scanned,
                    regimes_seen=regimes_seen,
                )

    return PatternMineResult(
        patterns=patterns,
        wins=len(patterns),
        scanned=scanned,
        regimes_seen=regimes_seen,
    )
