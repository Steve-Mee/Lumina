"""Birth SIM rollouts via RLTradingEnvironment (ADR-0012 SSOT)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.bible_observation import bible_features_for_tick
from lumina_core.birth.birth_trade_geometry import (
    BirthTradeGeometry,
    calibrate_birth_stops,
    geometry_action,
    soft_prior_action_stops,
)
from lumina_core.birth.config import BirthRewardConfig, load_birth_v2_config
from lumina_core.birth.sim_runner_actions import (
    exploration_action as _exploration_action,
    hold_ratio as _hold_ratio,
    predict_action as _predict_action,
)
from lumina_core.birth.sim_runner_entry_telem import close_open_telem, stamp_open_host, update_open_telem
from lumina_core.logging_utils import get_logger
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment
from lumina_core.rl.gym_stop_fill import birth_force_qty_one

logger = get_logger("lumina.birth.sim_runner")

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
    participation_force_exit: int = 0
    participation_passthrough: int = 0
    participation_overrides_total: int = 0
    participation_last_mode: str = "PASSTHROUGH"
    # Exit physics telemetry (truthful expectancy forensics).
    closes_stop: int = 0
    closes_target: int = 0
    closes_flatten: int = 0
    closes_time_stop: int = 0
    mean_entry_stop_pct: float = 0.0
    mean_entry_target_pct: float = 0.0
    # Plant (FORCE_OPEN entry) vs pilot (policy-initiated) skill split.
    policy_trades: int = 0
    policy_wins: int = 0
    plant_trades: int = 0
    plant_wins: int = 0
    closes_unknown: int = 0
    occupancy_control_flat: float = 0.0
    last_force_open_stop_pct: float = 0.0
    r_series: list[float] = field(default_factory=list)
    s3_inband_explore: int = 0
    s3_inband_hold_tax_steps: int = 0
    s3_inband_idle_armed: bool = False
    force_open_refractory_active: bool = False
    occupancy_in_band_seen: bool = False
    last_cap_usd: float = 0.0
    last_close_gap: bool = False
    occ_floor_band_bars: int = 0
    occ_total_bars: int = 0


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
    participation_under_band_release_hysteresis: float | None = None,
    participation_stop_pct: float | None = None,
    participation_target_pct: float | None = None,
    participation_qty_frac: float = 0.15,
    # Stage SSOT for envelope law (pre-rollout cumulative). When set, warmup and
    # band decisions use stage+this-rollout occupancy — not a per-chunk reset.
    stage_range_flat_bars: int = 0,
    stage_range_total_signals: int = 0,
    # Stage-2 quality stack seed: max(0, floor − live expectancy on WR−0.50 scale).
    expectancy_gap: float = 0.0,
    stage2_expectancy_floor: float = -0.15,
    # P2: under expectancy_gap > 0, clamp FORCE_EXIT max-hold (bars). 0 = default 60.
    stall_max_hold_bars: int = 0,
    # In-band FORCE_EXIT under exp gap. Default OFF (geometry time-stop theater).
    force_exit_on_expectancy_gap: bool = False,
    # When True (default birth), soft-prior policy stop/target toward calibrated geometry.
    soft_prior_stops: bool = True,
    # Optional precomputed geometry; otherwise calibrated from ``data``.
    trade_geometry: BirthTradeGeometry | None = None,
    # Stage context for reward: "trend" | "range" | "mixed" | "".
    curriculum_regime: str = "",
    # Rolling occupancy IMU (mutated in place; 1=flat, 0=in position).
    occupancy_control_window: list[int] | None = None,
    occupancy_control_window_bars: int = 500,
    stage_policy_trades_prior: int = 0,
    s3_inband_min_idle_hold_bars: int | None = None,
    occupancy_in_band_seen: bool = False,
) -> SimRolloutResult:
    from lumina_core.birth.stage2_participation_envelope import (
        MODE_FORCE_EXIT,
        MODE_FORCE_FLAT,
        MODE_FORCE_HOLD,
        MODE_FORCE_OPEN,
        MODE_PASSTHROUGH,
        decide_stage2_participation,
        occupancy_control_flat,
        participation_telemetry,
    )
    from lumina_core.birth.force_open_plant import ForceOpenChatterBound, apply_force_open_side, apply_force_open_stop
    from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
    from lumina_core.birth.stage3_inband_idle import (
        S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS,
        S3InbandIdleState,
        maybe_s3_passthrough_mask,
        plant_tag_for_entry,
    )

    if not data:
        # Fail closed with a clear stall reason — never IndexError on empty universe.
        logger.error(
            "birth.rollout.empty_data target_trades=%s — history/expansion returned 0 ticks",
            target_trades,
        )
        return SimRolloutResult(
            trades=0,
            wins=0,
            hold_signals=0,
            total_signals=0,
            total_pnl=0.0,
            trajectories=[],
            pnl_series=[],
            r_series=[],
            constitution_violations=0,
            regimes_seen=set(),
            rollout_steps=0,
            stalled=True,
            stall_reason="empty_data",
            partial_complete=True,
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

    # Prefer frozen stage geometry. Never overwrite with peak-move on shuffled
    # rollout ``data`` (would re-poison to 0.8%/1.5% macro caps).
    if trade_geometry is not None and float(getattr(trade_geometry, "stop_pct", 0.0) or 0.0) > 0:
        geometry = trade_geometry
    else:
        geometry = calibrate_birth_stops(enriched)
    part_stop = (
        float(participation_stop_pct)
        if participation_stop_pct is not None
        else float(geometry.stop_pct)
    )
    part_target = (
        float(participation_target_pct)
        if participation_target_pct is not None
        else float(geometry.target_pct)
    )
    # Never allow legacy macro envelope stops to silently reappear when caller
    # still passes 0.75%/1.5% without an explicit override intent: if passed
    # values are macro-scale and data-calibrated is micro, prefer calibrated.
    if part_stop >= 0.005 and geometry.stop_pct < 0.004:
        part_stop = float(geometry.stop_pct)
        part_target = float(geometry.target_pct)

    step_budget = max(10_000, target_trades * 40) if rollout_step_budget is None else int(rollout_step_budget)
    base_probe = min(5_000, max(1, step_budget // 4)) if stall_probe_steps is None else int(stall_probe_steps)
    base_explore = 2_000 if exploration_steps is None else int(exploration_steps)
    level = max(0, int(escalation_level))
    probe_steps = max(200, base_probe // (1 + level))
    explore_budget = base_explore * (1 + level)

    # First-touch pressure seed from live exp gap (thr often ~0.33–0.40 on MES).
    # wr_est = floor - gap + 0.50; pressure = max(0, thr - wr_est). Floors unchanged.
    ft_press = 0.0
    try:
        thr = float(getattr(geometry, "first_touch_target_hit_rate", 0.0) or 0.0)
        if thr <= 0:
            thr = 0.334  # diagnostic default ≈ live forensics thr; not a pass floor
        if float(expectancy_gap) > 1e-12:
            wr_est = float(stage2_expectancy_floor) - float(expectancy_gap) + 0.50
            ft_press = max(0.0, thr - wr_est)
    except Exception:
        ft_press = 0.0
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
        first_touch_training_pressure=float(ft_press),
        default_stop_pct=float(geometry.stop_pct),
        default_target_pct=float(geometry.target_pct),
        soft_prior_stops=bool(soft_prior_stops),
        curriculum_regime=str(curriculum_regime or ""),
        force_qty_one=bool(birth_force_qty_one(str(curriculum_regime or ""))),
    )
    env = RLTradingEnvironment(runtime, enriched, config=cfg)
    env.set_birth_context(workspace_root=workspace_root, constitution_guard=guard)
    logger.info(
        "birth.rollout.geometry stop=%.4f%% target=%.4f%% source=%s regime=%s exp_gap=%.4f "
        "ordered=%s frozen=%s",
        geometry.stop_pct * 100.0,
        geometry.target_pct * 100.0,
        geometry.source,
        curriculum_regime or "unset",
        float(expectancy_gap),
        bool(getattr(geometry, "time_ordered", True)),
        trade_geometry is not None,
    )

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
    r_series: list[float] = []
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
        MODE_FORCE_EXIT: 0,
        MODE_PASSTHROUGH: 0,
    }
    max_hold_bars = int(getattr(geometry, "hold_bars", 0) or 0)
    if max_hold_bars < 20:
        max_hold_bars = 120
    # In-band stall-cut only when the opt-in FORCE_EXIT flag is on. Default: keep
    # geometry hold (~120) so stop/target can realize (live 2026-08-12 flatten-murder).
    if float(expectancy_gap) > 1e-12 and bool(force_exit_on_expectancy_gap):
        stall_hold = int(stall_max_hold_bars) if int(stall_max_hold_bars or 0) > 0 else 60
        stall_hold = max(20, min(180, int(stall_hold)))
        max_hold_bars = min(max_hold_bars, stall_hold)
    # PR-D: when caller reports exit-magnet (stop:target bad), clamp hold further.
    # Sim runner itself accumulates closes; clamp is re-applied after enough samples below.
    last_participation_mode = MODE_PASSTHROUGH
    closes_stop = 0
    closes_target = 0
    closes_flatten = 0
    closes_time_stop = 0
    occ_floor_band_bars = 0
    occ_total_bars = 0
    stop_pct_sum = 0.0
    target_pct_sum = 0.0
    stop_pct_n = 0
    # Exit-magnet hold clamp (updated after enough decisive closes this rollout).
    exit_magnet_hold = max(
        20,
        min(120, int(stall_max_hold_bars) if int(stall_max_hold_bars or 0) > 0 else 50),
    )
    # Entry attribution: FORCE_OPEN plant vs policy pilot (skill metric).
    entry_is_plant = False
    open_telem: dict[str, Any] | None = None
    policy_trades = 0
    policy_wins = 0
    plant_trades = 0
    plant_wins = 0
    closes_unknown = 0
    last_force_open_stop_pct = 0.0
    chatter = ForceOpenChatterBound()
    from lumina_core.birth.foundation_occupancy_envelope import (
        foundation_cumulative_in_band_passthrough,
    )

    occupancy_all_ticks = foundation_cumulative_in_band_passthrough(curriculum_regime)
    occ_win = occupancy_control_window
    occ_cap = max(50, int(occupancy_control_window_bars or 500))
    envelope_flat_bars = max(0, int(stage_range_flat_bars))
    envelope_signals = max(0, int(stage_range_total_signals))
    s3_idle = S3InbandIdleState()
    policy_trades_prior = max(0, int(stage_policy_trades_prior))
    min_idle_hold = (
        int(s3_inband_min_idle_hold_bars)
        if s3_inband_min_idle_hold_bars is not None
        else int(getattr(cfg.reward, "s3_inband_min_idle_hold_bars", S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS) or S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS)
    )

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
                "s3_inband_idle_armed": bool(s3_idle.last_armed),
                "s3_inband_explore": int(s3_idle.explore_count),
                "s3_inband_hold_tax_steps": int(
                    getattr(env, "_s3_inband_hold_tax_steps", 0) or 0
                ),
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

        idx_preview = min(getattr(env, "_idx", 0), len(enriched) - 1)
        # Multi-window truth: never hold a position across a segment boundary
        # (price path is discontinuous there by construction).
        _segment_flat = False
        try:
            from lumina_core.birth.birth_trade_geometry import SEGMENT_BREAK_KEY

            tick_here = enriched[idx_preview] if enriched else {}
            if (
                bool(tick_here.get(SEGMENT_BREAK_KEY))
                and int(getattr(env, "_position", 0) or 0) != 0
            ):
                _segment_flat = True
        except Exception:
            _segment_flat = False

        use_exploration = False
        if not _segment_flat and exploration_steps_used < explore_budget:
            if trades == 0 and rollout_steps >= probe_steps:
                use_exploration = True
            elif level >= 2 and trades < target_trades:
                use_exploration = True
            elif level >= 1 and _hold_ratio(hold_signals, total_signals) > 0.65:
                use_exploration = True
            elif _hold_ratio(hold_signals, total_signals) > 0.80:
                use_exploration = True

        if _segment_flat:
            exploration_active = False
            action = geometry_action(0.0, 0.5, geometry)
        elif use_exploration:
            exploration_active = True
            action = _exploration_action(exploration_steps_used, geometry)
            exploration_steps_used += 1
        else:
            exploration_active = False
            tick_regime_preview = str(enriched[idx_preview].get("regime", "NEUTRAL")).upper()
            is_range_preview = (
                tick_regime_preview in {"NEUTRAL", "RANGING"} or "RANGE" in tick_regime_preview
            )
            action = _predict_action(policy, obs)
            # Soft-prior: pull grossly mis-scaled policy stops toward market geometry.
            if soft_prior_stops and action is not None and len(action) >= 4:
                from lumina_core.birth.birth_trade_geometry import (
                    SOFT_PRIOR_DEFAULT_MULTIPLE,
                )

                adj_s, adj_t = soft_prior_action_stops(
                    float(action[2]),
                    float(action[3]),
                    geometry=geometry,
                    max_multiple=SOFT_PRIOR_DEFAULT_MULTIPLE,
                )
                action = np.array(
                    [float(action[0]), float(action[1]), adj_s, adj_t],
                    dtype=np.float32,
                )
            if hold_cap_ratio is not None and total_signals > 0:
                side_preview = int(np.clip(np.round(action[0]), 0, 2))
                if side_preview == 0 and _hold_ratio(hold_signals, total_signals) >= float(hold_cap_ratio):
                    exploration_active = True
                    action = _exploration_action(exploration_steps_used, geometry)
                    exploration_steps_used += 1
            if position_flat_cap is not None and range_total_signals > 50 and is_range_preview:
                current_flat_ratio = float(range_flat_bars) / float(max(1, range_total_signals))
                side_preview = int(np.clip(np.round(action[0]), 0, 2))
                if current_flat_ratio < float(position_flat_cap) and side_preview != 0:
                    action = geometry_action(0.0, 0.5, geometry)
            # Under-activity: force exploration entries when range flat is above band.
            # Also inject when already non-hold but position-flat stays high (entries
            # dying immediately) — use calibrated safe stop/target for birth SIM.
            if position_flat_floor is not None and range_total_signals > 50 and is_range_preview:
                current_flat_ratio = float(range_flat_bars) / float(max(1, range_total_signals))
                side_preview = int(np.clip(np.round(action[0]), 0, 2))
                if current_flat_ratio > float(position_flat_floor):
                    if side_preview == 0 or (exploration_steps_used % 3 == 0):
                        exploration_active = True
                        action = _exploration_action(exploration_steps_used, geometry)
                        action = geometry_action(float(action[0]), 0.25, geometry)
                        exploration_steps_used += 1

        # Stage2 Participation Envelope — hard occupancy physics (overrides soft explore).
        # SSOT: stage cumulative + this rollout so chronic under-activity cannot
        # re-warmup (PASSTHROUGH) every chunk while stage_flat stays ~95%.
        stage_flat_prior = max(0, int(stage_range_flat_bars))
        stage_sig_prior = max(0, int(stage_range_total_signals))
        envelope_flat_bars = stage_flat_prior + int(range_flat_bars)
        envelope_signals = stage_sig_prior + int(range_total_signals)
        envelope_flat_ratio = float(envelope_flat_bars) / float(max(1, envelope_signals))
        occ_total_bars += 1
        if 0.25 - 1e-12 <= envelope_flat_ratio <= 0.30 + 1e-12:
            occ_floor_band_bars += 1
        if (
            float(participation_band_lo) - 1e-12
            <= envelope_flat_ratio
            <= float(participation_band_hi) + 1e-12
        ):
            occupancy_in_band_seen = True
        pos_now = int(getattr(env, "_position", 0) or 0)
        if pos_now != 0:
            bars_in_position += 1
        else:
            bars_in_position = 0
        occ_win = occupancy_control_window
        occ_cap = max(50, int(occupancy_control_window_bars or 500))
        rolling_flat: float | None = None
        if occ_win is not None and len(occ_win) >= min(50, occ_cap):
            slice_win = occ_win[-occ_cap:]
            rolling_flat = float(sum(slice_win)) / float(max(1, len(slice_win)))
        release_hyst = (
            0.02
            if participation_under_band_release_hysteresis is None
            else float(participation_under_band_release_hysteresis)
        )
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
            under_band_release_hysteresis=release_hyst,
            stop_pct=float(part_stop),
            target_pct=float(part_target),
            qty_frac=float(participation_qty_frac),
            max_hold_bars=int(max_hold_bars),
            expectancy_gap=float(expectancy_gap),
            force_exit_on_sticky_under=True,
            force_exit_on_expectancy_gap=bool(force_exit_on_expectancy_gap),
            rolling_flat_ratio=rolling_flat,
            # Mixed/S3: occupancy_all_ticks. Exam-in-band → policy PASSTHROUGH.
            cumulative_in_band_passthrough=bool(occupancy_all_ticks),
            force_open_refractory=chatter.blocks(int(participation_min_dwell_bars)),
            in_band_seen=bool(occupancy_in_band_seen),
        )
        last_participation_mode = decision.mode
        participation_counts[decision.mode] = int(participation_counts.get(decision.mode, 0) or 0) + 1
        force_open_this_step = False
        if decision.action_override is not None:
            action = np.array(decision.action_override, dtype=np.float32)
            if decision.mode == MODE_FORCE_OPEN:
                force_open_this_step = True
                force_open_step += 1
                exploration_active = True
                idx_sel = min(int(getattr(env, "_idx", 0) or 0), len(enriched) - 1)
                row_sel = enriched[idx_sel]
                action = apply_force_open_side(action, row_sel)
                action, stop = apply_force_open_stop(
                    action,
                    row_sel,
                    geometry,
                    min_dwell_bars=int(participation_min_dwell_bars),
                    equity=float(getattr(env, "_equity", 0.0) or 0.0),
                )
                last_force_open_stop_pct = float(stop)
            elif decision.mode == MODE_FORCE_EXIT:
                action = np.array([0.0, 0.5, float(part_stop), float(part_target)], dtype=np.float32)
        else:
            idx_mask = min(int(getattr(env, "_idx", 0) or 0), len(enriched) - 1)
            action = maybe_s3_passthrough_mask(
                state=s3_idle,
                action=action,
                participation_mode=decision.mode,
                action_override=decision.action_override,
                curriculum_regime=str(curriculum_regime or ""),
                position=pos_now,
                cumulative_flat=float(envelope_flat_ratio),
                band_lo=float(participation_band_lo),
                band_hi=float(participation_band_hi),
                policy_trades=int(policy_trades_prior) + int(policy_trades),
                min_idle_hold_bars=int(min_idle_hold),
                policy_edge_min_trades=int(POLICY_EDGE_MIN_TRADES),
                geometry=geometry,
                row=enriched[idx_mask],
                equity=float(getattr(env, "_equity", 0.0) or 0.0),
                min_dwell_bars=int(participation_min_dwell_bars),
                resample_hold=lambda: _predict_action(policy, obs, deterministic=False),
            )
        # Per-step occupancy protect: only while envelope is correcting (over-flat).
        env.config.suppress_random_flatten = bool(decision.suppress_flatten)
        env.config.participation_min_dwell_bars = (
            int(participation_min_dwell_bars) if decision.suppress_flatten else 0
        )
        env.config.force_flatten_this_step = bool(getattr(decision, "force_flatten", False))
        env.config.force_time_stop_this_step = bool(getattr(decision, "force_time_stop", False))
        # Occupancy plant: do not let gym soft-prior shrink ATR×√dwell stops.
        env.config.soft_prior_stops = False if force_open_this_step else bool(soft_prior_stops)
        env.config.participation_mode = str(decision.mode)
        env.config.stage_policy_trades = int(policy_trades_prior) + int(policy_trades)
        env.config.participation_band_lo = float(participation_band_lo)
        env.config.participation_band_hi = float(participation_band_hi)
        env.config.stage_cumulative_flat = float(envelope_flat_ratio)

        idx = min(env._idx, len(enriched) - 1)
        tick_regime = str(enriched[idx].get("regime", "NEUTRAL")).upper()
        is_range_tick = tick_regime in {"NEUTRAL", "RANGING"} or "RANGE" in tick_regime

        side_bucket = int(np.clip(np.round(action[0]), 0, 2))
        if side_bucket == 0:
            hold_signals += 1
        total_signals += 1
        occupancy_tick = bool(occupancy_all_ticks or is_range_tick)
        if occupancy_tick:
            range_total_signals += 1
            if side_bucket == 0:
                range_hold_signals += 1

        pos_before = int(getattr(env, "_position", 0) or 0)
        obs, reward, terminated, _truncated, info = env.step(action)
        # One-shot occupancy/time-stop flags (do not stick across steps).
        env.config.force_flatten_this_step = False
        env.config.force_time_stop_this_step = False
        env.config.soft_prior_stops = bool(soft_prior_stops)
        rollout_steps += 1
        pos_after = int(getattr(env, "_position", 0) or 0)
        # Attribute entry: FORCE_OPEN that opens a flat→position is plant, not pilot.
        if pos_before == 0 and pos_after != 0:
            entry_is_plant = plant_tag_for_entry(force_open_this_step=force_open_this_step)
        stamp_open_host(
            env, occupancy_control_flat(cumulative_flat=envelope_flat_ratio, rolling_flat=rolling_flat),
            occupancy_in_band_seen, envelope_flat_bars, envelope_signals, range_flat_bars, range_total_signals, geometry)
        open_telem = update_open_telem(
            open_telem, env, info, pos_before, pos_after, enriched[idx], enriched,
            policy_signals=getattr(policy, "last_open_signal", None),
        )
        if occupancy_tick and pos_after == 0:
            range_flat_bars += 1
        if occupancy_tick and occ_win is not None:
            occ_win.append(1 if pos_after == 0 else 0)
            if len(occ_win) > occ_cap:
                del occ_win[:-occ_cap]
        if pos_after == 0:
            bars_in_position = 0
        if info.get("blocked_by_birth_constitution"):
            constitution_blocks += 1

        pnl = float(info.get("rl_close_accounting_net_usd", 0.0) or 0.0)
        trade_closed = bool(info.get("trade_closed"))
        gross = float(info.get("model_close_gross_pnl_usd", 0.0) or 0.0)
        settled = bool(trade_closed) or (abs(pnl) > 1e-9 and gross != 0.0)
        closed_was_plant = False
        if settled:
            trades += 1
            total_pnl += pnl
            pnl_series.append(pnl)
            trade_r_raw = info.get("trade_r")
            if trade_r_raw is not None:
                r_series.append(float(trade_r_raw))
            else:
                risk_raw = float(info.get("risk_usd", 0.0) or 0.0)
                if risk_raw > 1e-12:
                    r_series.append(float(pnl) / risk_raw)
            is_win = pnl > 0
            if is_win:
                wins += 1
            # Skill split: FORCE_OPEN plant entries do not grade the pilot.
            closed_was_plant = bool(entry_is_plant)
            if closed_was_plant:
                plant_trades += 1
                if is_win:
                    plant_wins += 1
            else:
                policy_trades += 1
                if is_win:
                    policy_wins += 1
            entry_is_plant = False
            reason = str(info.get("close_reason", "") or "")
            if reason == "stop":
                closes_stop += 1
            elif reason == "target":
                closes_target += 1
            elif reason == "time_stop":
                closes_time_stop += 1
            elif reason in {"flatten", "force_exit"}:
                closes_flatten += 1
            else:
                closes_unknown += 1
                logger.warning(
                    "birth.rollout.close_reason_missing reason=%r pnl=%.4f",
                    reason,
                    pnl,
                )
            # PR-D: clamp max-hold while stop-magnet (real settlement, shorter zombies).
            # Quality floor 80: never re-introduce 35–50 bar thrash that kills targets
            # (live forensics 2026-08-12: stop:target 3:1 while geometry needs ~120).
            decisive = int(closes_stop) + int(closes_target)
            if decisive >= 20:
                ratio = float(closes_stop) / float(max(1, closes_target))
                if ratio > 2.5:
                    magnet_cap = max(80, int(exit_magnet_hold))
                    max_hold_bars = min(int(max_hold_bars), magnet_cap)
            e_stop = float(info.get("entry_stop_pct", 0.0) or 0.0)
            e_tgt = float(info.get("entry_target_pct", 0.0) or 0.0)
            if e_stop > 0:
                stop_pct_sum += e_stop
                target_pct_sum += e_tgt
                stop_pct_n += 1
            idx = min(env._idx, len(enriched) - 1)
            if str(enriched[idx].get("_intra_difficulty", "")).lower() == "easy":
                easy_trades += 1
                if is_win:
                    easy_wins += 1
            regime = str(enriched[idx].get("regime", "NEUTRAL"))
            regimes_seen.add(regime)
            if occupancy_tick:
                range_round_trips += 1
            trajectories.append(
                {
                    "observation": {"vector": prev_obs.tolist()},
                    "action": {
                        "signal": "BUY"
                        if side_bucket == 1
                        else ("SELL" if side_bucket == 2 else "HOLD")
                    },
                    "reward": float(reward),
                    "reward_on_close": float(reward),
                    "next_observation": {"vector": obs.tolist()},
                    "done": True,
                    "pnl": pnl,
                    "trade_r": info.get("trade_r"),
                    "qty": info.get("qty"),
                    "risk_usd": info.get("risk_usd"),
                    "regime": regime,
                    "close_regime": regime,
                    "close_reason": reason,
                    "plant_entry": bool(closed_was_plant),
                    "skill_grade": "plant" if closed_was_plant else "policy",
                    "cap_usd": info.get("cap_usd"),
                    "gap": info.get("gap"),
                    "entry_price": info.get("entry_price"),
                    "point_value": info.get("point_value"),
                    **close_open_telem(open_telem, idx, regime, info, host=env, closed_was_plant=closed_was_plant),
                }
            )
            open_telem = None
        chatter.on_bar(trade_closed=settled, closed_was_plant=closed_was_plant)
        prev_obs = obs
        if terminated:
            open_telem = None
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
    control_flat = occupancy_control_flat(
        cumulative_flat=float(envelope_flat_bars) / float(max(1, envelope_signals))
        if envelope_signals > 0
        else 0.0,
        rolling_flat=(
            float(sum(occ_win[-occ_cap:])) / float(max(1, len(occ_win[-occ_cap:])))
            if occ_win is not None and len(occ_win) >= min(50, occ_cap)
            else None
        ),
    )
    mean_entry_stop = (stop_pct_sum / float(stop_pct_n)) if stop_pct_n > 0 else 0.0
    mean_entry_target = (target_pct_sum / float(stop_pct_n)) if stop_pct_n > 0 else 0.0
    # Honesty assert + hard clip: mean entry stop must stay within soft-prior band.
    try:
        from lumina_core.birth.birth_trade_geometry import SOFT_PRIOR_DEFAULT_MULTIPLE

        geo_s = float(geometry.stop_pct or 0.0)
        geo_t = float(geometry.target_pct or 0.0)
        mult = float(SOFT_PRIOR_DEFAULT_MULTIPLE)
        cap_s = geo_s * mult if geo_s > 0 else 0.0
        if mean_entry_stop > 0 and cap_s > 0 and mean_entry_stop > cap_s * 1.05:
            logger.warning(
                "birth.rollout.mean_entry_stop_drift mean=%.6f geo=%.6f mult=%.2f source=%s — hard_clip",
                mean_entry_stop,
                geo_s,
                mult,
                geometry.source,
            )
            mean_entry_stop = min(mean_entry_stop, cap_s)
            if mean_entry_target > 0 and geo_t > 0:
                mean_entry_target = min(mean_entry_target, geo_t * mult * 1.5)
    except Exception:
        pass
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
        r_series=r_series,
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
        participation_force_exit=int(telem.get("participation_force_exit", 0) or 0),
        participation_passthrough=int(telem["participation_passthrough"]),
        participation_overrides_total=int(telem["participation_overrides_total"]),
        participation_last_mode=str(last_participation_mode),
        closes_stop=closes_stop,
        closes_target=closes_target,
        closes_flatten=closes_flatten,
        closes_time_stop=closes_time_stop,
        closes_unknown=int(closes_unknown),
        mean_entry_stop_pct=mean_entry_stop,
        mean_entry_target_pct=mean_entry_target,
        policy_trades=int(policy_trades),
        policy_wins=int(policy_wins),
        plant_trades=int(plant_trades),
        plant_wins=int(plant_wins),
        occupancy_control_flat=float(control_flat),
        last_force_open_stop_pct=float(last_force_open_stop_pct),
        s3_inband_explore=int(s3_idle.explore_count),
        s3_inband_hold_tax_steps=int(getattr(env, "_s3_inband_hold_tax_steps", 0) or 0),
        s3_inband_idle_armed=bool(s3_idle.last_armed),
        force_open_refractory_active=chatter.blocks(int(participation_min_dwell_bars)),
        occupancy_in_band_seen=bool(occupancy_in_band_seen),
        occ_floor_band_bars=int(occ_floor_band_bars),
        occ_total_bars=int(occ_total_bars),
    )
