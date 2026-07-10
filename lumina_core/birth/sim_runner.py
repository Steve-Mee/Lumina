"""Birth SIM rollouts via RLTradingEnvironment (ADR-0012 SSOT)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.bible_observation import bible_features_for_tick
from lumina_core.birth.config import BirthRewardConfig, load_birth_v2_config
from lumina_core.logging_utils import get_logger
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment

logger = get_logger("lumina.birth.sim_runner")

_DEFAULT_ACTION = np.array([0.0, 0.5, 0.0075, 0.013], dtype=np.float32)
_LOG_INTERVAL_STEPS = 10_000
_PROGRESS_INTERVAL_STEPS = 5_000
_PROGRESS_INTERVAL_SEC = 30.0


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
    range_hold_signals: int = 0
    range_total_signals: int = 0
    range_flat_bars: int = 0
    range_round_trips: int = 0
    rollout_steps: int = 0
    stalled: bool = False
    stall_reason: str | None = None
    exploration_steps_used: int = 0
    constitution_blocks: int = 0
    partial_complete: bool = False
    easy_trades: int = 0
    easy_wins: int = 0


def _predict_action(policy: Any, obs: np.ndarray) -> np.ndarray:
    if policy is None:
        return _DEFAULT_ACTION.copy()
    predict = getattr(policy, "predict", None)
    if not callable(predict):
        return _DEFAULT_ACTION.copy()
    try:
        action, _ = predict(obs, deterministic=True)
        return np.asarray(action, dtype=np.float32).reshape(-1)
    except Exception:
        return _DEFAULT_ACTION.copy()


def _exploration_action(exploration_step: int) -> np.ndarray:
    side = 1.0 if exploration_step % 2 == 0 else 2.0
    return np.array([side, 0.5, 0.0075, 0.013], dtype=np.float32)


def _hold_ratio(hold_signals: int, total_signals: int) -> float:
    return float(hold_signals) / float(max(1, total_signals))


def run_policy_rollout(
    *,
    runtime: Any,
    data: list[dict[str, Any]],
    policy: Any,
    target_trades: int,
    workspace_root: Any = None,
    max_steps: int | None = None,
    constitution_guard: BirthConstitutionGuard | None = None,
    rollout_step_budget: int | None = None,
    stall_probe_steps: int | None = None,
    exploration_steps: int | None = None,
    escalation_level: int = 0,
    hold_cap_ratio: float | None = None,
    position_flat_cap: float | None = None,
    range_patience_active: bool = False,
    plateau_active: bool = False,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    reward_override: BirthRewardConfig | None = None,
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

    step_budget = max(10_000, target_trades * 40) if rollout_step_budget is None else int(rollout_step_budget)
    base_probe = min(5_000, max(1, step_budget // 4)) if stall_probe_steps is None else int(stall_probe_steps)
    base_explore = 2_000 if exploration_steps is None else int(exploration_steps)
    level = max(0, int(escalation_level))
    probe_steps = max(200, base_probe // (1 + level))
    explore_budget = base_explore * (1 + level)

    cfg = RLConfig(
        trade_mode="birth",
        max_steps=max_steps or max(5000, target_trades * 80),
        reward=reward_override or load_birth_v2_config(workspace_root).reward,
        plateau_active=bool(plateau_active),
        range_patience_active=bool(range_patience_active),
    )
    env = RLTradingEnvironment(runtime, enriched, config=cfg)
    env.set_birth_context(workspace_root=workspace_root, constitution_guard=guard)

    obs, _ = env.reset()
    trades = 0
    wins = 0
    easy_trades = 0
    easy_wins = 0
    hold_signals = 0
    total_signals = 0
    range_hold_signals = 0
    range_total_signals = 0
    range_flat_bars = 0
    range_round_trips = 0
    total_pnl = 0.0
    pnl_series: list[float] = []
    trajectories: list[dict[str, Any]] = []
    regimes_seen: set[str] = set()
    prev_obs = obs
    rollout_steps = 0
    constitution_blocks = 0
    exploration_active = False
    exploration_steps_used = 0
    last_progress_at = time.monotonic()
    last_logged_step = 0

    def _emit_progress() -> None:
        if on_progress is None:
            return
        on_progress(
            {
                "rollout_trades": trades,
                "rollout_steps": rollout_steps,
                "hold_ratio": _hold_ratio(hold_signals, total_signals),
                "exploration_active": exploration_active,
                "constitution_blocks": constitution_blocks,
            }
        )

    def _maybe_log_progress() -> None:
        nonlocal last_progress_at, last_logged_step
        if rollout_steps - last_logged_step >= _LOG_INTERVAL_STEPS:
            last_logged_step = rollout_steps
            logger.info(
                "birth.rollout.progress",
                extra={
                    "event_data": {
                        "rollout_steps": rollout_steps,
                        "trades": trades,
                        "hold_ratio": round(_hold_ratio(hold_signals, total_signals), 4),
                        "exploration_active": exploration_active,
                        "constitution_blocks": constitution_blocks,
                    }
                },
            )
        now = time.monotonic()
        if rollout_steps > 0 and (
            rollout_steps % _PROGRESS_INTERVAL_STEPS == 0 or (now - last_progress_at) >= _PROGRESS_INTERVAL_SEC
        ):
            last_progress_at = now
            _emit_progress()

    while trades < target_trades:
        if rollout_steps >= step_budget:
            break

        use_exploration = False
        if exploration_steps_used < explore_budget:
            if trades == 0 and rollout_steps >= probe_steps:
                use_exploration = True
            elif level >= 2 and trades < target_trades:
                use_exploration = True
            elif level >= 1 and _hold_ratio(hold_signals, total_signals) > 0.65:
                use_exploration = True
            elif _hold_ratio(hold_signals, total_signals) > 0.80:
                use_exploration = True

        if use_exploration:
            exploration_active = True
            action = _exploration_action(exploration_steps_used)
            exploration_steps_used += 1
        else:
            exploration_active = False
            idx_preview = min(env._idx, len(enriched) - 1)
            tick_regime_preview = str(enriched[idx_preview].get("regime", "NEUTRAL")).upper()
            is_range_preview = (
                tick_regime_preview in {"NEUTRAL", "RANGING"} or "RANGE" in tick_regime_preview
            )
            action = _predict_action(policy, obs)
            if hold_cap_ratio is not None and total_signals > 0:
                side_preview = int(np.clip(np.round(action[0]), 0, 2))
                if side_preview == 0 and _hold_ratio(hold_signals, total_signals) >= float(hold_cap_ratio):
                    exploration_active = True
                    action = _exploration_action(exploration_steps_used)
                    exploration_steps_used += 1
            if position_flat_cap is not None and range_total_signals > 50 and is_range_preview:
                current_flat_ratio = float(range_flat_bars) / float(max(1, range_total_signals))
                side_preview = int(np.clip(np.round(action[0]), 0, 2))
                if current_flat_ratio < float(position_flat_cap) and side_preview != 0:
                    action = np.array([0.0, 0.5, 0.0075, 0.013], dtype=np.float32)

        idx = min(env._idx, len(enriched) - 1)
        tick_regime = str(enriched[idx].get("regime", "NEUTRAL")).upper()
        is_range_tick = tick_regime in {"NEUTRAL", "RANGING"} or "RANGE" in tick_regime

        side_bucket = int(np.clip(np.round(action[0]), 0, 2))
        if side_bucket == 0:
            hold_signals += 1
        total_signals += 1
        if is_range_tick:
            range_total_signals += 1
            if side_bucket == 0:
                range_hold_signals += 1

        obs, reward, terminated, _truncated, info = env.step(action)
        rollout_steps += 1
        if is_range_tick and int(getattr(env, "_position", 0) or 0) == 0:
            range_flat_bars += 1
        if info.get("blocked_by_birth_constitution"):
            constitution_blocks += 1

        pnl = float(info.get("rl_close_accounting_net_usd", 0.0) or 0.0)
        if abs(pnl) > 1e-9 and float(info.get("model_close_gross_pnl_usd", 0.0) or 0.0) != 0.0:
            trades += 1
            total_pnl += pnl
            pnl_series.append(pnl)
            if pnl > 0:
                wins += 1
            idx = min(env._idx, len(enriched) - 1)
            if str(enriched[idx].get("_intra_difficulty", "")).lower() == "easy":
                easy_trades += 1
                if pnl > 0:
                    easy_wins += 1
            regime = str(enriched[idx].get("regime", "NEUTRAL"))
            regimes_seen.add(regime)
            if is_range_tick:
                range_round_trips += 1
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

        _maybe_log_progress()

    _emit_progress()

    partial_complete = trades > 0 and trades < target_trades and rollout_steps >= step_budget
    stalled = trades == 0 and rollout_steps >= step_budget
    stall_reason: str | None = None
    if stalled:
        if exploration_steps_used > 0:
            stall_reason = "hold_only_after_exploration"
        else:
            stall_reason = "step_budget_exhausted"

    return SimRolloutResult(
        trades=trades,
        wins=wins,
        hold_signals=hold_signals,
        total_signals=total_signals,
        range_hold_signals=range_hold_signals,
        range_total_signals=range_total_signals,
        range_flat_bars=range_flat_bars,
        range_round_trips=range_round_trips,
        total_pnl=total_pnl,
        trajectories=trajectories,
        pnl_series=pnl_series,
        constitution_violations=guard.violations,
        regimes_seen=regimes_seen,
        rollout_steps=rollout_steps,
        stalled=stalled,
        stall_reason=stall_reason,
        exploration_steps_used=exploration_steps_used,
        constitution_blocks=constitution_blocks,
        partial_complete=partial_complete,
        easy_trades=easy_trades,
        easy_wins=easy_wins,
    )
