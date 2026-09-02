"""Single-rollout cycle: pre-meta, sim rollout, post-update (thin orchestrator)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    update_stage1_intra_state,
    update_stage2_intra_state,
)

from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.birth.stage_loop_rollout_post import StageLoopRolloutPostMixin
from lumina_core.birth.stage_loop_rollout_pre import StageLoopRolloutPreMixin, RolloutPreState
from lumina_core.birth.stage_loop_rollout_tail import StageLoopRolloutTailMixin
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_rollout_cycle")


def _run_policy_rollout(**kwargs: Any) -> Any:
    """Late-bound so tests can monkeypatch stage_training_loop.run_policy_rollout."""
    from lumina_core.birth import stage_training_loop as _compat

    return _compat.run_policy_rollout(**kwargs)


class StageLoopRolloutCycleMixin(
    StageLoopRolloutPreMixin,
    StageLoopRolloutPostMixin,
    StageLoopRolloutTailMixin,
    StageLoopMixinBase,
):
    """Execute one curriculum rollout cycle (meta + sim + metrics update)."""

    def _execute_rollout_cycle(
        self, *, active_ticks: list[dict[str, Any]], chunk_target: int
    ) -> dict[str, Any] | None:
        """Returns a terminal stall dict to return from run(), or None to continue the loop."""
        pre = self._prepare_rollout_cycle(active_ticks=active_ticks, chunk_target=chunk_target)
        rollout, current_hold_ratio, range_flat_ratio, current_winrate, metric_band = (
            self._run_sim_and_apply_metrics(
                active_ticks=active_ticks,
                chunk_target=chunk_target,
                pre=pre,
            )
        )
        _ = range_flat_ratio
        self._apply_post_rollout_meta(rollout)
        return self._run_rollout_tail(
            rollout=rollout,
            chunk_target=chunk_target,
            current_winrate=current_winrate,
            current_hold_ratio=current_hold_ratio,
            metric_band=metric_band,
        )

    def _run_sim_and_apply_metrics(
        self,
        *,
        active_ticks: list[dict[str, Any]],
        chunk_target: int,
        pre: RolloutPreState,
    ) -> tuple[Any, float, float, float, float]:
        from lumina_core.birth.stage3_inband_ssot import apply_s3_inband_rollout_metrics, s3_inband_rollout_kwargs

        rollout_started_at = time.time()
        _occ_win = getattr(self, "_occupancy_control_window", None)
        if _occ_win is None:
            _occ_win = []
            self._occupancy_control_window = _occ_win
        rollout = _run_policy_rollout(
            runtime=self.host.runtime,
            data=active_ticks,
            policy=self.host.current_policy,
            target_trades=chunk_target,
            workspace_root=self.host.workspace_root,
            constitution_guard=self.host._constitution_guard,
            rollout_step_budget=self.chunk_budget,
            stall_probe_steps=max(200, self.cur_cfg.stall_probe_steps // (1 + self.escalation_level)),
            exploration_steps=pre.explore_steps,
            escalation_level=self.escalation_level,
            hold_cap_ratio=pre.hold_cap,
            position_flat_cap=pre.position_flat_cap,
            position_flat_floor=pre.position_flat_floor,
            range_patience_active=pre.range_patience_active,
            plateau_active=pre.plateau_recovery,
            on_progress=pre.progress_cb,
            reward_override=pre.reward_override,
            participation_envelope_enabled=bool(
                getattr(pre, "participation_envelope_enabled", False)
            ),
            participation_min_signals=int(
                getattr(pre, "participation_min_signals", 50) or 50
            ),
            participation_min_dwell_bars=int(
                getattr(pre, "participation_min_dwell_bars", 8) or 8
            ),
            participation_band_lo=float(getattr(pre, "participation_band_lo", 0.30) or 0.30),
            participation_band_hi=float(getattr(pre, "participation_band_hi", 0.70) or 0.70),
            participation_hysteresis=float(
                getattr(pre, "participation_hysteresis", 0.02)
                if getattr(pre, "participation_hysteresis", None) is not None
                else 0.02
            ),
            participation_under_band_release_hysteresis=(
                None
                if getattr(pre, "participation_under_band_release_hysteresis", None) is None
                else float(pre.participation_under_band_release_hysteresis)
            ),
            participation_stop_pct=float(
                getattr(pre, "participation_stop_pct", 0.0012) or 0.0012
            ),
            participation_target_pct=float(
                getattr(pre, "participation_target_pct", 0.0020) or 0.0020
            ),
            participation_qty_frac=float(
                getattr(pre, "participation_qty_frac", 0.15) or 0.15
            ),
            stage_range_flat_bars=int(getattr(pre, "stage_range_flat_bars", 0) or 0),
            stage_range_total_signals=int(
                getattr(pre, "stage_range_total_signals", 0) or 0
            ),
            expectancy_gap=float(getattr(pre, "expectancy_gap", 0.0) or 0.0),
            stage2_expectancy_floor=float(
                getattr(pre, "stage2_expectancy_floor", -0.15) or -0.15
            ),
            stall_max_hold_bars=int(
                self._stage2_effective_stall_max_hold_bars()
            ),
            force_exit_on_expectancy_gap=bool(
                getattr(self.cur_cfg, "stage2_force_exit_on_expectancy_gap", False)
            ),
            curriculum_regime=str(
                getattr(self.stage, "value", self.stage) or ""
            ),
            soft_prior_stops=True,
            trade_geometry=getattr(self, "_birth_trade_geometry", None),
            occupancy_control_window=_occ_win,
            occupancy_control_window_bars=int(
                getattr(pre, "occupancy_control_window_bars", 500) or 500
            ),
            **s3_inband_rollout_kwargs(self),
        )
        self.rollout_wall_clock_total_sec += max(0.0, time.time() - rollout_started_at)
        self.rollout_wall_clock_samples += 1
        self.sim_ticks_processed_cumulative += int(getattr(rollout, "rollout_steps", 0) or 0)

        self.stage_trades += rollout.trades
        self.stage_wins += rollout.wins
        self.stage_hold_signals += rollout.hold_signals
        self.stage_total_signals += rollout.total_signals
        self.stage_range_hold_signals += rollout.range_hold_signals
        self.stage_range_total_signals += rollout.range_total_signals
        self.stage_range_flat_bars += rollout.range_flat_bars
        self.stage_range_round_trips += rollout.range_round_trips
        try:
            self.occupancy_control_flat = float(
                getattr(rollout, "occupancy_control_flat", 0.0) or 0.0
            )
        except (TypeError, ValueError):
            self.occupancy_control_flat = 0.0
        self.host.cumulative_trades += rollout.trades
        # Pilot vs plant skill split (Stage-2 FORCE_OPEN does not grade pilot).
        self.stage_policy_trades = int(getattr(self, "stage_policy_trades", 0) or 0) + int(
            getattr(rollout, "policy_trades", rollout.trades) or 0
        )
        self.stage_policy_wins = int(getattr(self, "stage_policy_wins", 0) or 0) + int(
            getattr(rollout, "policy_wins", rollout.wins) or 0
        )
        self.stage_plant_trades = int(getattr(self, "stage_plant_trades", 0) or 0) + int(
            getattr(rollout, "plant_trades", 0) or 0
        )
        self.stage_plant_wins = int(getattr(self, "stage_plant_wins", 0) or 0) + int(
            getattr(rollout, "plant_wins", 0) or 0
        )
        apply_s3_inband_rollout_metrics(self, rollout)
        # Stage2 participation envelope telemetry (cumulative within stage).
        self.participation_force_open = int(
            getattr(self, "participation_force_open", 0) or 0
        ) + int(getattr(rollout, "participation_force_open", 0) or 0)
        self.participation_force_hold = int(
            getattr(self, "participation_force_hold", 0) or 0
        ) + int(getattr(rollout, "participation_force_hold", 0) or 0)
        self.participation_force_flat = int(
            getattr(self, "participation_force_flat", 0) or 0
        ) + int(getattr(rollout, "participation_force_flat", 0) or 0)
        self.participation_force_exit = int(
            getattr(self, "participation_force_exit", 0) or 0
        ) + int(getattr(rollout, "participation_force_exit", 0) or 0)
        self.participation_passthrough = int(
            getattr(self, "participation_passthrough", 0) or 0
        ) + int(getattr(rollout, "participation_passthrough", 0) or 0)
        # Mirror cum onto peak state for operator SSOT (stage lifetime exits).
        try:
            peak_st = getattr(self, "stage2_peak_state", None)
            if peak_st is not None:
                peak_st.participation_force_exit_cum = int(self.participation_force_exit)
        except Exception:
            pass
        self.participation_overrides_total = int(
            getattr(self, "participation_overrides_total", 0) or 0
        ) + int(getattr(rollout, "participation_overrides_total", 0) or 0)
        self.participation_last_mode = str(
            getattr(rollout, "participation_last_mode", "") or "PASSTHROUGH"
        )
        self.closes_stop = int(getattr(rollout, "closes_stop", 0) or 0)
        self.closes_target = int(getattr(rollout, "closes_target", 0) or 0)
        self.closes_flatten = int(getattr(rollout, "closes_flatten", 0) or 0)
        self.closes_time_stop = int(getattr(rollout, "closes_time_stop", 0) or 0)
        self.closes_unknown = int(getattr(rollout, "closes_unknown", 0) or 0)
        # Stage-wide exit forensics SSOT (Stage-2 peak + Stage-3 visibility).
        self.stage_closes_stop_cum = int(
            getattr(self, "stage_closes_stop_cum", 0) or 0
        ) + int(self.closes_stop)
        self.stage_closes_target_cum = int(
            getattr(self, "stage_closes_target_cum", 0) or 0
        ) + int(self.closes_target)
        self.stage_closes_flatten_cum = int(
            getattr(self, "stage_closes_flatten_cum", 0) or 0
        ) + int(self.closes_flatten)
        self.stage_closes_time_stop_cum = int(
            getattr(self, "stage_closes_time_stop_cum", 0) or 0
        ) + int(self.closes_time_stop)
        self.stage_closes_unknown_cum = int(
            getattr(self, "stage_closes_unknown_cum", 0) or 0
        ) + int(self.closes_unknown)
        self.mean_entry_stop_pct = float(getattr(rollout, "mean_entry_stop_pct", 0.0) or 0.0)
        self.mean_entry_target_pct = float(
            getattr(rollout, "mean_entry_target_pct", 0.0) or 0.0
        )
        # P0–P2: peak capture, exit forensics cum, near-miss, collapse restore.
        try:
            self._stage2_peak_after_rollout(rollout)
        except Exception as peak_exc:
            from lumina_core.logging_utils import get_logger

            get_logger("lumina.birth.stage_loop_rollout").debug(
                "birth.stage2.peak_after_rollout_failed: %s", peak_exc
            )
        # Raptor v10: count train laps for adaptation_stuck debounce.
        self.rollouts_since_last_adaptation = int(
            getattr(self, "rollouts_since_last_adaptation", 0) or 0
        ) + 1
        try:
            wa = getattr(self, "wa_state", None)
            if wa is not None and hasattr(wa, "rollouts_since_last_adaptation"):
                wa.rollouts_since_last_adaptation = self.rollouts_since_last_adaptation
            bus_wa = getattr(getattr(self, "bus", None), "wall_adaptation_state", None)
            if bus_wa is not None and hasattr(bus_wa, "rollouts_since_last_adaptation"):
                bus_wa.rollouts_since_last_adaptation = self.rollouts_since_last_adaptation
        except Exception:
            pass
        self._maybe_run_oos_proxy()
        self._maybe_record_and_advance_swarm(
            trades=rollout.trades,
            wins=rollout.wins,
            total_pnl=float(rollout.total_pnl),
        )
        # Starship: realized PnL for all stages (EdgeScore expectancy must not fall back to WR−0.5).
        self.stage_val_pnl.extend(rollout.pnl_series)
        self.stage_val_r.extend(list(getattr(rollout, "r_series", None) or []))

        if self.intra_state is not None and rollout.easy_trades > 0:
            update_stage1_intra_state(
                self.intra_state,
                chunk_easy_trades=rollout.easy_trades,
                chunk_easy_wins=rollout.easy_wins,
                cfg=self.cur_cfg,
            )
        if self.intra_s2_state is not None and rollout.range_total_signals > 0:
            easy_share = 0.0
            if self.current_intra_sample_pool:
                easy_count = sum(
                    1
                    for t in self.current_intra_sample_pool
                    if str(t.get("_intra_difficulty", "")).lower() == "easy"
                )
                easy_share = float(easy_count) / float(max(1, len(self.current_intra_sample_pool)))
            if easy_share > 0.0:
                update_stage2_intra_state(
                    self.intra_s2_state,
                    chunk_flat_bars=int(rollout.range_flat_bars * easy_share),
                    chunk_range_signals=max(
                        1, int(rollout.range_total_signals * easy_share)
                    ),
                    cfg=self.cur_cfg,
                    chunk_easy_trades=int(getattr(rollout, "easy_trades", 0) or 0),
                    chunk_easy_wins=int(getattr(rollout, "easy_wins", 0) or 0),
                )

        current_hold_ratio = float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
        range_flat_ratio = float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals))
        if self.stage == CurriculumStage.STAGE2_RANGE and rollout.range_total_signals > 0:
            rollout_flat = float(rollout.range_flat_bars) / float(max(1, rollout.range_total_signals))
            flat_delta = range_flat_ratio - self.last_range_flat_ratio
            logger.info(
                "birth.stage2.rollout_metrics rollout_flat=%.4f stage_flat=%.4f delta=%+.4f "
                "round_trips=%s trades=%s force_open=%s force_hold=%s force_flat=%s overrides=%s",
                rollout_flat,
                range_flat_ratio,
                flat_delta,
                rollout.range_round_trips,
                rollout.trades,
                int(getattr(rollout, "participation_force_open", 0) or 0),
                int(getattr(rollout, "participation_force_hold", 0) or 0),
                int(getattr(rollout, "participation_force_flat", 0) or 0),
                int(getattr(rollout, "participation_overrides_total", 0) or 0),
            )
            self.last_range_flat_ratio = range_flat_ratio
        if rollout.trades > 0:
            self.wins_at_trade_milestones[self.stage_trades] = self.stage_wins
            # Raptor v13: per-rollout chunks for true last-N rolling WR.
            chunks = getattr(self, "rolling_trade_chunks", None)
            if not isinstance(chunks, list):
                chunks = []
                self.rolling_trade_chunks = chunks
            chunks.append((int(rollout.trades), int(rollout.wins)))
            try:
                from lumina_core.birth.plateau_escalator import prune_rolling_trade_chunks
                from lumina_core.birth.plateau_rolling import stage_rolling_pass_window

                window = stage_rolling_pass_window(self.cur_cfg, self.stage)
                self.rolling_trade_chunks = prune_rolling_trade_chunks(
                    chunks, window=window
                )
            except Exception:
                if len(chunks) > 128:
                    self.rolling_trade_chunks = chunks[-128:]
        metric_band = range_flat_ratio if self.stage_range_total_signals >= 50 else current_hold_ratio
        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        if rollout.trades > 0:
            self.winrate_history.append(current_winrate)
            if len(self.winrate_history) > self.cur_cfg.winrate_trend_window:
                self.winrate_history.pop(0)
            mean_reward = float(rollout.total_pnl) / float(max(1, rollout.trades))
            self.reward_history.append(mean_reward)
            if len(self.reward_history) > self.cur_cfg.reward_trend_window:
                self.reward_history.pop(0)

        return rollout, current_hold_ratio, range_flat_ratio, current_winrate, metric_band

    def _ensure_stage2_peak_state(self) -> Any:
        from lumina_core.birth.stage2_peak_capture import Stage2PeakState

        st = getattr(self, "stage2_peak_state", None)
        if st is None:
            st = Stage2PeakState()
            self.stage2_peak_state = st
        return st

    def _stage2_effective_stall_max_hold_bars(self) -> int:
        """Max hold for FORCE_EXIT under expectancy gap.

        Root-cause 2026-08-12: flash/finish clamped hold to 35 while geometry
        needs ~120 bars → stop:target stuck at 3:1 and WR never reaches 35%.

        Honest law:
        - Occupancy IN band + quality gap → respect geometry/quality hold
          (let targets realize; never cut winners early to "protect" a hop).
        - Occupancy UNDER band (over-trading) → shorter hold OK to free flat.
        Floors unchanged.
        """
        base = int(getattr(self.cur_cfg, "stage2_stall_max_hold_bars", 80) or 80)
        base = max(20, min(180, base))
        quality_hold = int(
            getattr(self.cur_cfg, "stage2_quality_max_hold_bars", 100) or 100
        )
        quality_hold = max(60, min(180, quality_hold))
        # Prefer birth geometry hold when available (SSOT from move distribution).
        try:
            geom = int(getattr(self, "_birth_geometry_hold_bars", 0) or 0)
            if geom < 20:
                geom = int(
                    getattr(self.host, "_birth_geometry_hold_bars", 0) or 0
                ) if getattr(self, "host", None) is not None else 0
            if geom >= 20:
                quality_hold = max(quality_hold, min(180, geom))
        except Exception:
            pass
        try:
            signals = int(getattr(self, "stage_range_total_signals", 0) or 0)
            flat = float(self.stage_range_flat_bars) / float(max(1, signals))
        except Exception:
            signals = 0
            flat = 0.5
        # Warm-up (few occupancy samples): do not treat flat≈0 as under-band
        # (would clamp hold to 60 and recreate stop-magnet before band stabilizes).
        if signals < 50:
            return max(60, min(180, quality_hold))
        in_band = 0.30 - 1e-12 <= flat <= 0.70 + 1e-12
        under_band = flat < 0.30 - 1e-12
        try:
            peak_st = getattr(self, "stage2_peak_state", None)
            # Quality path (in-band expectancy problem): geometry hold, never 35.
            if in_band:
                hold = quality_hold
                # Only mild magnet trim when stop-heavy AND under-band would apply;
                # in-band magnet is usually *caused* by early exits — do not deepen it.
                if peak_st is not None:
                    stop_n = int(getattr(peak_st, "cumulative_closes_stop", 0) or 0)
                    tgt_n = int(getattr(peak_st, "cumulative_closes_target", 0) or 0)
                    thr = float(
                        getattr(
                            self.cur_cfg, "stage2_exit_magnet_stop_target_ratio", 2.5
                        )
                        or 2.5
                    )
                    if stop_n + tgt_n >= 40 and float(stop_n) / float(max(1, tgt_n)) > thr:
                        # Soft floor: never below 80 when quality is the blocker.
                        magnet = int(
                            getattr(
                                self.cur_cfg, "stage2_exit_magnet_max_hold_bars", 80
                            )
                            or 80
                        )
                        hold = max(80, min(hold, max(80, magnet)))
                return max(60, min(180, hold))
            # Under-band over-trading: shorter hold to free occupancy.
            if under_band:
                short = min(base, 60)
                if peak_st is not None:
                    stop_n = int(getattr(peak_st, "cumulative_closes_stop", 0) or 0)
                    tgt_n = int(getattr(peak_st, "cumulative_closes_target", 0) or 0)
                    thr = float(
                        getattr(
                            self.cur_cfg, "stage2_exit_magnet_stop_target_ratio", 2.5
                        )
                        or 2.5
                    )
                    if stop_n + tgt_n >= 40 and float(stop_n) / float(max(1, tgt_n)) > thr:
                        magnet = int(
                            getattr(
                                self.cur_cfg, "stage2_exit_magnet_max_hold_bars", 80
                            )
                            or 80
                        )
                        short = min(short, max(40, magnet))
                return max(20, min(180, short))
        except Exception:
            pass
        # Default / unknown flat: quality-leaning hold (prefer targets over thrash).
        return max(60, min(180, quality_hold))

    def _stage2_peak_after_rollout(self, rollout: Any) -> None:
        """P0–P2 peak capture, near-miss, collapse restore, exit forensics."""
        if self.stage != CurriculumStage.STAGE2_RANGE:
            return
        if not bool(getattr(self.cur_cfg, "stage2_peak_capture_enabled", True)):
            return
        from lumina_core.birth.stage2_peak_capture import (
            accumulate_exit_physics,
            best_policy_path_for_restore,
            evaluate_near_miss,
            mark_volume_rechallenge,
            maybe_arm_peak_graduation,
            maybe_arm_quality_lock,
            maybe_release_quality_lock,
            note_quality_rollout,
            record_restore,
            restore_policy_from_path,
            save_peak_policy_copy,
            should_restore_peak_policy,
            should_volume_rechallenge_peak,
            update_finish_mode,
            update_stage2_peak,
        )

        state = self._ensure_stage2_peak_state()
        # Clear same-cycle restore flag; set again if we restore this cycle.
        state.restored_this_cycle = False
        accumulate_exit_physics(
            state,
            closes_stop=int(getattr(rollout, "closes_stop", 0) or 0),
            closes_target=int(getattr(rollout, "closes_target", 0) or 0),
            closes_flatten=int(getattr(rollout, "closes_flatten", 0) or 0),
            closes_time_stop=int(getattr(rollout, "closes_time_stop", 0) or 0),
            closes_unknown=int(getattr(rollout, "closes_unknown", 0) or 0),
        )
        rolling = None
        rolling_src = None
        try:
            wr, src, covered = self._rolling_winrate_meta()
            min_cov = int(getattr(self.cur_cfg, "stage2_rolling_pass_min_covered", 80) or 80)
            if str(src or "") in ("true_window", "partial_window") and int(covered) >= min_cov:
                rolling = float(wr)
                rolling_src = str(src)
        except Exception:
            rolling = None
        flat = float(self.stage_range_flat_bars) / float(
            max(1, self.stage_range_total_signals)
        )
        edge = getattr(self, "_edge_vs_random", None)
        try:
            edge_f = float(edge) if edge is not None else None
        except (TypeError, ValueError):
            edge_f = None
        # Snapshot path for peak (best-effort).
        policy_hint = ""
        try:
            root = Path(self.host.workspace_root)
            policy_hint = str(
                root / "lumina_agents" / "ppo" / f"birth_best_{self.stage.value}.zip"
            )
        except Exception:
            policy_hint = ""
        # PR-L: last rollout chunk WR for flash-green capture (first hop 36% @ 50).
        chunk_wr = None
        chunk_tr = int(getattr(rollout, "trades", 0) or 0)
        chunk_wn = int(getattr(rollout, "wins", 0) or 0)
        if chunk_tr >= 40:
            chunk_wr = float(chunk_wn) / float(max(1, chunk_tr))
        new_peak = update_stage2_peak(
            state,
            stage_trades=int(self.stage_trades),
            stage_wins=int(self.stage_wins),
            range_flat_ratio=flat,
            edge_vs_random=edge_f,
            rolling_winrate=rolling,
            chunk_winrate=chunk_wr,
            chunk_trades=chunk_tr,
            policy_path=policy_hint,
            cfg=self.cur_cfg,
        )
        if new_peak:
            saved = save_peak_policy_copy(
                host=self.host,
                stage_value=str(self.stage.value),
                state=state,
            )
            # Also update plateau best early (peak min trades, not 200).
            try:
                from lumina_core.birth.plateau_terminal_ladder import maybe_update_best_winrate

                if getattr(self, "plateau_state", None) is not None and saved:
                    # Temporarily allow lower min for peak-aligned best (always restore).
                    old_min = int(
                        getattr(self.cur_cfg, "plateau_best_policy_min_trades", 200) or 200
                    )
                    try:
                        self.cur_cfg.plateau_best_policy_min_trades = int(
                            getattr(self.cur_cfg, "stage2_peak_min_trades", 50) or 50
                        )
                        maybe_update_best_winrate(
                            self.plateau_state,
                            stage_trades=int(self.stage_trades),
                            stage_wins=int(self.stage_wins),
                            policy_path=saved or policy_hint,
                            cfg=self.cur_cfg,
                            rolling_winrate=rolling,
                            rolling_source=rolling_src,
                        )
                    finally:
                        try:
                            self.cur_cfg.plateau_best_policy_min_trades = old_min
                        except Exception:
                            pass
            except Exception:
                pass
        # PR-G: arm graduation when peak cleared floor (even pre-volume).
        maybe_arm_peak_graduation(
            state,
            stage_trades=int(self.stage_trades),
            range_flat_ratio=flat,
            required=int(self.required),
            cfg=self.cur_cfg,
        )
        chunk_exp = None
        if chunk_wr is not None:
            chunk_exp = float(chunk_wr) - 0.50
        life_wr = float(self.stage_wins) / float(max(1, int(self.stage_trades)))
        maybe_arm_quality_lock(
            state,
            chunk_wr=chunk_wr,
            chunk_exp=chunk_exp,
            stage_trades=int(self.stage_trades),
            cfg=self.cur_cfg,
            rolling_winrate=rolling,
            lifetime_wr=life_wr,
            range_flat_ratio=flat,
        )
        maybe_release_quality_lock(
            state,
            lifetime_wr=life_wr,
            stage_trades=int(self.stage_trades),
            required=int(self.required),
            cfg=self.cur_cfg,
            rolling_winrate=rolling,
            consecutive_rolling_pass_windows=int(
                getattr(state, "consecutive_rolling_pass_windows", 0) or 0
            ),
            range_flat_ratio=flat,
        )
        evaluate_near_miss(
            state,
            stage_trades=int(self.stage_trades),
            stage_wins=int(self.stage_wins),
            required=int(self.required),
            range_flat_ratio=flat,
            rolling_winrate=rolling,
            cfg=self.cur_cfg,
        )
        update_finish_mode(state, rolling_winrate=rolling, cfg=self.cur_cfg)
        # PR-G: at volume gate after peak_grad, force reload peak policy once.
        if should_volume_rechallenge_peak(
            state,
            stage_trades=int(self.stage_trades),
            required=int(self.required),
            cfg=self.cur_cfg,
        ):
            path = best_policy_path_for_restore(
                state, getattr(self, "plateau_state", None)
            )
            if path and restore_policy_from_path(self.host, path):
                record_restore(
                    state,
                    stage_trades=int(self.stage_trades),
                    reason="volume_rechallenge_peak",
                )
                mark_volume_rechallenge(state, stage_trades=int(self.stage_trades))
            else:
                mark_volume_rechallenge(state, stage_trades=int(self.stage_trades))
                logger.warning(
                    "birth.stage2.volume_rechallenge_load_failed path=%s", path
                )
        do_restore, reason = should_restore_peak_policy(
            state,
            stage_trades=int(self.stage_trades),
            stage_wins=int(self.stage_wins),
            rolling_winrate=rolling,
            range_flat_ratio=flat,
            cfg=self.cur_cfg,
            required=int(self.required),
            chunk_winrate=chunk_wr,
            chunk_trades=chunk_tr,
        )
        if do_restore and not state.restored_this_cycle:
            path = best_policy_path_for_restore(
                state, getattr(self, "plateau_state", None)
            )
            if path and restore_policy_from_path(self.host, path):
                record_restore(state, stage_trades=int(self.stage_trades), reason=reason)
            else:
                logger.warning(
                    "birth.stage2.peak_restore_skipped path_missing_or_load_failed path=%s",
                    path,
                )
        elif not state.restored_this_cycle:
            # Never count a pure quality rollout on the same cycle as restore
            # (volume rechallenge or collapse) — that short-changed the PPO freeze window.
            note_quality_rollout(state)
