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
    participation_force_open: int = 0
    participation_force_hold: int = 0
    participation_force_flat: int = 0
    participation_passthrough: int = 0
    participation_overrides_total: int = 0
    participation_last_mode: str = "PASSTHROUGH"


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
    position_flat_floor: float | None = None,
    range_patience_active: bool = False,
    plateau_active: bool = False,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    reward_override: BirthRewardConfig | None = None,
    participation_envelope_enabled: bool = False,
    participation_min_signals: int = 50,
    participation_min_dwell_bars: int = 8,
    participation_band_lo: float = 0.30,
    participation_band_hi: float = 0.70,
    participation_hysteresis: float = 0.02,
    participation_stop_pct: float = 0.0075,
    participation_target_pct: float = 0.015,
    participation_qty_frac: float = 0.15,
    # Stage SSOT for envelope law (pre-rollout cumulative). When set, warmup and
    # band decisions use stage+this-rollout occupancy — not a per-chunk reset.
    stage_range_flat_bars: int = 0,
    stage_range_total_signals: int = 0,
    # Stage-2 quality stack seed: max(0, floor − live expectancy on WR−0.50 scale).
    expectancy_gap: float = 0.0,
    stage2_expectancy_floor: float = -0.15,
) -> SimRolloutResult:
    from lumina_core.birth.stage2_participation_envelope import (
        MODE_FORCE_FLAT,
        MODE_FORCE_HOLD,
        MODE_FORCE_OPEN,
        MODE_PASSTHROUGH,
        decide_stage2_participation,
        participation_telemetry,
    )

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
        # Per-step envelope toggles suppress/dwell; start open until first decide.
        suppress_random_flatten=False,
        participation_min_dwell_bars=0,
        expectancy_gap=max(0.0, float(expectancy_gap)),
        stage2_expectancy_floor=float(stage2_expectancy_floor),
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
    bars_in_position = 0
    force_open_step = 0
    participation_counts: dict[str, int] = {
        MODE_FORCE_OPEN: 0,
        MODE_FORCE_HOLD: 0,
        MODE_FORCE_FLAT: 0,
        MODE_PASSTHROUGH: 0,
    }
    last_participation_mode = MODE_PASSTHROUGH

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
            # Under-activity: force exploration entries when range flat is above band.
            # Also inject when already non-hold but position-flat stays high (entries
            # dying immediately) — use explicit safe stop/target for birth SIM.
            if position_flat_floor is not None and range_total_signals > 50 and is_range_preview:
                current_flat_ratio = float(range_flat_bars) / float(max(1, range_total_signals))
                side_preview = int(np.clip(np.round(action[0]), 0, 2))
                if current_flat_ratio > float(position_flat_floor):
                    if side_preview == 0 or (exploration_steps_used % 3 == 0):
                        exploration_active = True
                        action = _exploration_action(exploration_steps_used)
                        # Guaranteed constitution-safe stop band (≤1%).
                        action = np.array(
                            [float(action[0]), 0.25, 0.0075, 0.015],
                            dtype=np.float32,
                        )
                        exploration_steps_used += 1

        # Stage2 Participation Envelope — hard occupancy physics (overrides soft explore).
        # SSOT: stage cumulative + this rollout so chronic under-activity cannot
        # re-warmup (PASSTHROUGH) every chunk while stage_flat stays ~95%.
        stage_flat_prior = max(0, int(stage_range_flat_bars))
        stage_sig_prior = max(0, int(stage_range_total_signals))
        envelope_flat_bars = stage_flat_prior + int(range_flat_bars)
        envelope_signals = stage_sig_prior + int(range_total_signals)
        envelope_flat_ratio = float(envelope_flat_bars) / float(max(1, envelope_signals))
        pos_now = int(getattr(env, "_position", 0) or 0)
        if pos_now != 0:
            bars_in_position += 1
        else:
            bars_in_position = 0
        decision = decide_stage2_participation(
            enabled=bool(participation_envelope_enabled) and bool(range_patience_active),
            range_flat_ratio=envelope_flat_ratio,
            range_total_signals=envelope_signals,
            position=pos_now,
            bars_in_position=bars_in_position,
            force_open_step=force_open_step,
            min_signals=int(participation_min_signals),
            min_dwell_bars=int(participation_min_dwell_bars),
            band_lo=float(participation_band_lo),
            band_hi=float(participation_band_hi),
            hysteresis=float(participation_hysteresis),
            stop_pct=float(participation_stop_pct),
            target_pct=float(participation_target_pct),
            qty_frac=float(participation_qty_frac),
        )
        last_participation_mode = decision.mode
        participation_counts[decision.mode] = int(participation_counts.get(decision.mode, 0) or 0) + 1
        if decision.action_override is not None:
            action = np.array(decision.action_override, dtype=np.float32)
            if decision.mode == MODE_FORCE_OPEN:
                force_open_step += 1
                exploration_active = True
        # Per-step occupancy protect: only while envelope is correcting (over-flat).
        env.config.suppress_random_flatten = bool(decision.suppress_flatten)
        env.config.participation_min_dwell_bars = (
            int(participation_min_dwell_bars) if decision.suppress_flatten else 0
        )

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
        pos_after = int(getattr(env, "_position", 0) or 0)
        if is_range_tick and pos_after == 0:
            range_flat_bars += 1
        if pos_after == 0:
            bars_in_position = 0
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

    telem = participation_telemetry(participation_counts)
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
        participation_force_open=int(telem["participation_force_open"]),
        participation_force_hold=int(telem["participation_force_hold"]),
        participation_force_flat=int(telem["participation_force_flat"]),
        participation_passthrough=int(telem["participation_passthrough"]),
        participation_overrides_total=int(telem["participation_overrides_total"]),
        participation_last_mode=str(last_participation_mode),
    )
