"""Birth SIM rollouts via RLTradingEnvironment (ADR-0012 SSOT)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.bible_observation import bible_features_for_tick
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment


@dataclass(slots=True)
class SimRolloutResult:
    trades: int
    wins: int
    hold_signals: int
    total_signals: int
    total_pnl: float
    trajectories: list[dict[str, Any]]
    pnl_series: list[float]
    constitution_violations: int
    regimes_seen: set[str]


def _predict_action(policy: Any, obs: np.ndarray) -> np.ndarray:
    if policy is None:
        return np.array([0.0, 0.5, 0.0075, 0.013], dtype=np.float32)
    predict = getattr(policy, "predict", None)
    if not callable(predict):
        return np.array([0.0, 0.5, 0.0075, 0.013], dtype=np.float32)
    try:
        action, _ = predict(obs, deterministic=True)
        return np.asarray(action, dtype=np.float32).reshape(-1)
    except Exception:
        return np.array([0.0, 0.5, 0.0075, 0.013], dtype=np.float32)


def run_policy_rollout(
    *,
    runtime: Any,
    data: list[dict[str, Any]],
    policy: Any,
    target_trades: int,
    workspace_root: Any = None,
    max_steps: int | None = None,
    constitution_guard: BirthConstitutionGuard | None = None,
) -> SimRolloutResult:
    guard = constitution_guard or BirthConstitutionGuard()
    enriched = []
    for row in data:
        tick = dict(row)
        c, n, s, m = bible_features_for_tick(tick, workspace_root=workspace_root)
        tick["bible_confluence"] = c
        tick["bible_news_proximity"] = n
        tick["bible_session_phase"] = s
        tick["bible_mtf_bias"] = m
        enriched.append(tick)

    cfg = RLConfig(trade_mode="birth", max_steps=max_steps or max(5000, target_trades * 80))
    env = RLTradingEnvironment(runtime, enriched, config=cfg)
    env.set_birth_context(workspace_root=workspace_root, constitution_guard=guard)

    obs, _ = env.reset()
    trades = 0
    wins = 0
    hold_signals = 0
    total_signals = 0
    total_pnl = 0.0
    pnl_series: list[float] = []
    trajectories: list[dict[str, Any]] = []
    regimes_seen: set[str] = set()
    prev_obs = obs

    while trades < target_trades:
        action = _predict_action(policy, obs)
        side_bucket = int(np.clip(np.round(action[0]), 0, 2))
        if side_bucket == 0:
            hold_signals += 1
        total_signals += 1

        obs, reward, terminated, _truncated, info = env.step(action)
        pnl = float(info.get("rl_close_accounting_net_usd", 0.0) or 0.0)
        if abs(pnl) > 1e-9 and float(info.get("model_close_gross_pnl_usd", 0.0) or 0.0) != 0.0:
            trades += 1
            total_pnl += pnl
            pnl_series.append(pnl)
            if pnl > 0:
                wins += 1
            idx = min(env._idx, len(enriched) - 1)
            regime = str(enriched[idx].get("regime", "NEUTRAL"))
            regimes_seen.add(regime)
            trajectories.append(
                {
                    "observation": {"vector": prev_obs.tolist()},
                    "action": {"signal": "BUY" if side_bucket == 1 else ("SELL" if side_bucket == 2 else "HOLD")},
                    "reward": float(reward),
                    "next_observation": {"vector": obs.tolist()},
                    "done": True,
                    "pnl": pnl,
                    "regime": regime,
                }
            )
        prev_obs = obs
        if terminated:
            obs, _ = env.reset()
            prev_obs = obs

    return SimRolloutResult(
        trades=trades,
        wins=wins,
        hold_signals=hold_signals,
        total_signals=total_signals,
        total_pnl=total_pnl,
        trajectories=trajectories,
        pnl_series=pnl_series,
        constitution_violations=guard.violations,
        regimes_seen=regimes_seen,
    )
