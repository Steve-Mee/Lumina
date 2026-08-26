"""Stage-loop metrics payload builder."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.plateau_escalator import (
    plateau_min_stage_trades,
    quarantine_progress_payload,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")

STAGE_VAL_PNL_CHECKPOINT_CAP = 2000


def serialize_stage_val_pnl(
    series: list[float] | None,
    *,
    cap: int = STAGE_VAL_PNL_CHECKPOINT_CAP,
) -> list[float]:
    """Persist closed-trade USD PnL for process-R after resume. Cap keeps checkpoint bounded."""
    vals = [float(x) for x in (series or []) if isinstance(x, (int, float))]
    limit = max(1, int(cap))
    if len(vals) > limit:
        return vals[-limit:]
    return vals


def restore_stage_val_pnl(
    raw: object,
    *,
    cap: int = STAGE_VAL_PNL_CHECKPOINT_CAP,
) -> list[float]:
    if not isinstance(raw, list):
        return []
    return serialize_stage_val_pnl(
        [float(x) for x in raw if isinstance(x, (int, float))],
        cap=cap,
    )


def restore_stage_val_pnl_from_buffer(
    trajectories: object,
    *,
    stage_trades: int | None = None,
    cap: int = STAGE_VAL_PNL_CHECKPOINT_CAP,
) -> list[float]:
    """Rebuild closed-trade USD PnL from persisted trajectories (pre-PR checkpoints).

    Never invents values. Uses ``pnl`` on completed episodes only. Prefers the
    last ``stage_trades`` closes so oracle-research prefix does not dominate.
    """
    if not isinstance(trajectories, list):
        return []
    pnls: list[float] = []
    for item in trajectories:
        if not isinstance(item, dict):
            continue
        if item.get("done") is False:
            continue
        pnl = item.get("pnl")
        if isinstance(pnl, (int, float)):
            pnls.append(float(pnl))
    prefer = int(stage_trades) if stage_trades is not None and int(stage_trades) > 0 else cap
    return serialize_stage_val_pnl(pnls[-max(1, prefer) :], cap=cap)


def serialize_stage_val_r(
    series: list[float] | None,
    *,
    cap: int = STAGE_VAL_PNL_CHECKPOINT_CAP,
) -> list[float]:
    """Persist per-trade R (qty-normalized). Same cap as stage_val_pnl."""
    return serialize_stage_val_pnl(series, cap=cap)


def restore_stage_val_r(
    raw: object,
    *,
    cap: int = STAGE_VAL_PNL_CHECKPOINT_CAP,
) -> list[float]:
    return restore_stage_val_pnl(raw, cap=cap)


def restore_stage_val_r_from_buffer(
    trajectories: object,
    *,
    stage_trades: int | None = None,
    cap: int = STAGE_VAL_PNL_CHECKPOINT_CAP,
) -> list[float]:
    """Rebuild per-trade R from persisted trajectories. Never invents from USD PnL."""
    if not isinstance(trajectories, list):
        return []
    rs: list[float] = []
    for item in trajectories:
        if not isinstance(item, dict):
            continue
        if item.get("done") is False:
            continue
        raw_r = item.get("trade_r")
        if isinstance(raw_r, (int, float)):
            rs.append(float(raw_r))
    prefer = int(stage_trades) if stage_trades is not None and int(stage_trades) > 0 else cap
    return serialize_stage_val_r(rs[-max(1, prefer) :], cap=cap)


class StageLoopProgressMetricsMixin:
    """Builds stage_metrics dict for checkpoint/progress."""

    def _stage_metrics_payload(self) -> dict[str, Any]:
        payload = self.host._stage_metrics_snapshot(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            stage_hold_signals=self.stage_hold_signals,
            stage_total_signals=self.stage_total_signals,
            stage_range_hold_signals=self.stage_range_hold_signals,
            stage_range_total_signals=self.stage_range_total_signals,
            stage_range_flat_bars=self.stage_range_flat_bars,
            stage_range_round_trips=self.stage_range_round_trips,
            patterns_mined=self.patterns_mined,
        )
        payload["winrate_history"] = list(self.winrate_history)
        payload["stage_val_pnl"] = serialize_stage_val_pnl(
            list(getattr(self, "stage_val_pnl", None) or [])
        )
        payload["stage_val_r"] = serialize_stage_val_r(
            list(getattr(self, "stage_val_r", None) or [])
        )
        payload["reward_history"] = list(self.reward_history)
        payload["velocity_stall_attempts"] = int(self.low_velocity_attempts)
        payload["strong_recovery_mode"] = bool(self.strong_recovery_mode)
        payload["strong_recovery_attempts"] = int(self.strong_recovery_attempts)
        payload["retries_this_stage"] = int(self.retries_this_stage)
        payload["adaptation_tier"] = int(self.adaptation_tier)
        payload["adaptation_history"] = list(self.adaptation_history)
        payload["escalation_level"] = int(self.escalation_level)
        payload["rollouts_since_last_adaptation"] = int(
            getattr(self, "rollouts_since_last_adaptation", 0) or 0
        )
        payload["last_adaptation_stage_trades"] = int(
            getattr(self, "last_adaptation_stage_trades", -1) or -1
        )
        # Raptor v12/v13: persist rolling milestones + chunks.
        wins_at = getattr(self, "wins_at_trade_milestones", None)
        if isinstance(wins_at, dict) and wins_at:
            items = sorted(
                ((int(k), int(v)) for k, v in wins_at.items() if int(k) > 0),
                key=lambda kv: kv[0],
            )
            if len(items) > 64:
                items = items[-64:]
            payload["wins_at_trade_milestones"] = {str(k): v for k, v in items}
        chunks = getattr(self, "rolling_trade_chunks", None)
        if isinstance(chunks, list) and chunks:
            payload["rolling_trade_chunks"] = [
                [int(t), int(w)] for t, w in chunks[-128:] if int(t) > 0
            ]
        payload["curriculum_stage_scope"] = self.stage.value
        if self.intra_state is not None:
            payload["intra_stage1_hard_pct"] = round(float(self.intra_state.hard_pct), 4)
            payload["intra_stage1_easy_trades"] = int(self.intra_state.easy_trades)
            payload["intra_stage1_easy_wins"] = int(self.intra_state.easy_wins)
            payload["intra_stage1_easy_winrate_history"] = list(self.intra_state.easy_winrate_history)
            payload["intra_stage1_meta"] = dict(self.intra_meta)
        if self.intra_s2_state is not None:
            payload["intra_stage2_hard_pct"] = round(float(self.intra_s2_state.hard_pct), 4)
            payload["intra_stage2_easy_flat_bars"] = int(self.intra_s2_state.easy_flat_bars)
            payload["intra_stage2_easy_range_signals"] = int(self.intra_s2_state.easy_range_signals)
            payload["intra_stage2_easy_flat_ratio_history"] = list(
                self.intra_s2_state.easy_flat_ratio_history
            )
            payload["intra_stage2_easy_trades"] = int(
                getattr(self.intra_s2_state, "easy_trades", 0) or 0
            )
            payload["intra_stage2_easy_wins"] = int(
                getattr(self.intra_s2_state, "easy_wins", 0) or 0
            )
            payload["intra_stage2_easy_winrate_history"] = list(
                getattr(self.intra_s2_state, "easy_winrate_history", []) or []
            )
            payload["intra_stage2_meta"] = dict(self.intra_s2_meta)
        if self.cur_cfg.meta_controller_enabled:
            payload.update(self.bus.meta_metrics_payload(self.stage))
        payload.update(self.plateau_state.to_metrics())
        payload.update(self.remediation_state.to_metrics())
        payload.update(self.organism_autonomy_state.to_metrics())
        payload.update(self.bus.adaptation_recovery_metrics(self.stage))
        payload.update(self.swarm_state.to_metrics())
        payload.update(
            quarantine_progress_payload(
                self.plateau_quarantine,
                stage_trades=self.stage_trades,
                cfg=self.cur_cfg,
            )
        )
        payload["plateau_min_stage_trades"] = plateau_min_stage_trades(self.stage, self.cur_cfg)
        payload["stage_pass_gate_trades"] = self.required
        payload["stage_budget_trades"] = self.target
        payload["expectancy_quality_step"] = int(
            getattr(self, "expectancy_quality_step", 0) or 0
        )
        # P0–P1 peak capture SSOT for checkpoint/resume (truthful, floors unchanged).
        try:
            peak_st = getattr(self, "stage2_peak_state", None)
            if peak_st is not None and hasattr(peak_st, "as_progress_fields"):
                payload.update(peak_st.as_progress_fields())
                # Compact restore blob so resume does not lose peak path/counts.
                payload["stage2_peak_state"] = {
                    "peak_winrate": float(getattr(peak_st, "peak_winrate", 0.0) or 0.0),
                    "peak_expectancy": float(getattr(peak_st, "peak_expectancy", -1.0) or -1.0),
                    "peak_at_trade": int(getattr(peak_st, "peak_at_trade", 0) or 0),
                    "peak_policy_path": str(getattr(peak_st, "peak_policy_path", "") or ""),
                    "peak_flat": float(getattr(peak_st, "peak_flat", 0.0) or 0.0),
                    "peak_edge_vs_random": float(
                        getattr(peak_st, "peak_edge_vs_random", 0.0) or 0.0
                    ),
                    "near_miss_active": bool(getattr(peak_st, "near_miss_active", False)),
                    "near_miss_count": int(getattr(peak_st, "near_miss_count", 0) or 0),
                    "restore_count": int(getattr(peak_st, "restore_count", 0) or 0),
                    "last_restore_at_trade": int(
                        getattr(peak_st, "last_restore_at_trade", 0) or 0
                    ),
                    "last_restore_reason": str(
                        getattr(peak_st, "last_restore_reason", "") or ""
                    ),
                    "quality_rollouts_since_restore": int(
                        getattr(peak_st, "quality_rollouts_since_restore", 0) or 0
                    ),
                    "cumulative_closes_stop": int(
                        getattr(peak_st, "cumulative_closes_stop", 0) or 0
                    ),
                    "cumulative_closes_target": int(
                        getattr(peak_st, "cumulative_closes_target", 0) or 0
                    ),
                    "cumulative_closes_flatten": int(
                        getattr(peak_st, "cumulative_closes_flatten", 0) or 0
                    ),
                    "peak_grad_armed": bool(getattr(peak_st, "peak_grad_armed", False)),
                    "peak_grad_armed_at_trade": int(
                        getattr(peak_st, "peak_grad_armed_at_trade", 0) or 0
                    ),
                    "volume_rechallenge_done": bool(
                        getattr(peak_st, "volume_rechallenge_done", False)
                    ),
                    "volume_rechallenge_at_trade": int(
                        getattr(peak_st, "volume_rechallenge_at_trade", 0) or 0
                    ),
                    "finish_mode_active": bool(
                        getattr(peak_st, "finish_mode_active", False)
                    ),
                    "consecutive_rolling_pass_windows": int(
                        getattr(peak_st, "consecutive_rolling_pass_windows", 0) or 0
                    ),
                    "flash_green": bool(getattr(peak_st, "flash_green", False)),
                    "flash_green_wr": float(getattr(peak_st, "flash_green_wr", 0.0) or 0.0),
                    "flash_green_at_trade": int(
                        getattr(peak_st, "flash_green_at_trade", 0) or 0
                    ),
                    "flash_green_durable": bool(
                        getattr(peak_st, "flash_green_durable", False)
                    ),
                    "consecutive_green_chunks": int(
                        getattr(peak_st, "consecutive_green_chunks", 0) or 0
                    ),
                    "participation_force_exit_cum": int(
                        getattr(peak_st, "participation_force_exit_cum", 0) or 0
                    ),
                }
        except Exception:
            payload.setdefault("stage2_peak_winrate", 0.0)
        # Birth trade geometry + exit physics — always present (never omit).
        stop_g = getattr(self, "_birth_trade_stop_pct", None)
        target_g = getattr(self, "_birth_trade_target_pct", None)
        payload["birth_trade_stop_pct"] = (
            round(float(stop_g), 6) if stop_g is not None else 0.0
        )
        payload["birth_trade_target_pct"] = (
            round(float(target_g), 6) if target_g is not None else 0.0
        )
        payload["birth_trade_geometry_source"] = str(
            getattr(self, "_birth_trade_geometry_source", None) or "unset"
        )
        try:
            from lumina_core.birth.birth_trade_geometry import apply_geometry_forensics

            apply_geometry_forensics(
                payload, getattr(self, "_birth_trade_geometry", None)
            )
        except Exception:
            payload.setdefault("geometry_time_ordered", False)
            payload.setdefault("geometry_p40_raw", 0.0)
            payload.setdefault("geometry_hold_bars", 0)
            payload.setdefault("geometry_pool_size", 0)
            payload.setdefault("geometry_macro_rejected", False)
            payload.setdefault("geometry_floor_bound", False)
            payload.setdefault("geometry_breakeven_wr_after_cost", 0.0)
            payload.setdefault("geometry_cost_usd", 0.0)
            payload.setdefault("geometry_ref_price", 0.0)
        try:
            thr = float(getattr(self, "_first_touch_target_hit_rate", 0.0) or 0.0)
            # Resilience: recompute once if stage entry thr missing but geometry frozen.
            if thr <= 0:
                geo = getattr(self, "_birth_trade_geometry", None)
                pool = list(
                    getattr(self, "active_stage_ticks", None)
                    or getattr(self, "active_train", None)
                    or []
                )
                if geo is not None and len(pool) >= 80:
                    from lumina_core.birth.birth_trade_geometry import (
                        first_touch_target_hit_rate,
                    )

                    thr = float(
                        first_touch_target_hit_rate(
                            pool,
                            stop_pct=float(geo.stop_pct),
                            target_pct=float(geo.target_pct),
                            max_hold_bars=int(getattr(geo, "hold_bars", 90) or 90),
                            sample_stride=40,
                        )
                        or 0.0
                    )
                    self._first_touch_target_hit_rate = thr
            payload["first_touch_target_hit_rate"] = round(thr, 4)
            live_wr = float(
                payload.get("hygiene_wr_effective")
                or payload.get("rolling_winrate_500")
                or getattr(self, "last_winrate", 0.0)
                or 0.0
            )
            payload["edge_vs_random"] = round(live_wr - thr, 4) if thr > 0 else 0.0
            if thr > 0:
                self._edge_vs_random = float(payload["edge_vs_random"])
        except Exception:
            payload.setdefault("first_touch_target_hit_rate", 0.0)
            payload.setdefault("edge_vs_random", 0.0)
        # Pass vector on metrics path (parity with progress enrich SSOT).
        try:
            from lumina_core.birth.stage2_pass_vector import compute_stage2_pass_vector
            from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

            signals = int(getattr(self, "stage_range_total_signals", 0) or 0)
            flat_bars = int(getattr(self, "stage_range_flat_bars", 0) or 0)
            flat_pv = float(flat_bars) / float(max(1, signals)) if signals > 0 else 0.5
            live_wr_pv = float(
                payload.get("hygiene_wr_effective")
                or payload.get("rolling_winrate_500")
                or getattr(self, "last_winrate", 0.0)
                or 0.0
            )
            exp_proxy = live_wr_pv - 0.50
            edge_pv = float(payload.get("edge_vs_random") or 0.0)
            pv = compute_stage2_pass_vector(
                range_flat_ratio=flat_pv,
                expectancy=exp_proxy,
                exp_floor=float(stage2_expectancy_floor(self.cur_cfg)),
                edge_vs_random=edge_pv,
                band_lo=float(
                    getattr(self.cur_cfg, "stage2_participation_band_lo", 0.30) or 0.30
                ),
                band_hi=float(
                    getattr(self.cur_cfg, "stage2_participation_band_hi", 0.70) or 0.70
                ),
            )
            payload.update(pv.as_progress_fields())
        except Exception:
            payload.setdefault("pass_vector_dominant", "none")
            payload.setdefault("pass_vector_action", "hold_pass_path")
        payload["stage2_bootstrap_patterns"] = int(
            getattr(self, "stage2_bootstrap_patterns", 0) or 0
        )
        payload["stage2_bootstrap_updates"] = int(
            getattr(self, "stage2_bootstrap_updates", 0) or 0
        )
        payload["participation_force_open"] = int(
            getattr(self, "participation_force_open", 0) or 0
        )
        payload["participation_force_hold"] = int(
            getattr(self, "participation_force_hold", 0) or 0
        )
        payload["participation_force_flat"] = int(
            getattr(self, "participation_force_flat", 0) or 0
        )
        payload["participation_force_exit"] = int(
            getattr(self, "participation_force_exit", 0) or 0
        )
        payload["participation_last_mode"] = str(
            getattr(self, "participation_last_mode", "") or "PASSTHROUGH"
        )
        try:
            payload["occupancy_control_flat"] = round(
                float(getattr(self, "occupancy_control_flat", 0.0) or 0.0), 4
            )
        except (TypeError, ValueError):
            payload["occupancy_control_flat"] = 0.0
        payload["closes_stop"] = int(getattr(self, "closes_stop", 0) or 0)
        payload["closes_target"] = int(getattr(self, "closes_target", 0) or 0)
        payload["closes_flatten"] = int(getattr(self, "closes_flatten", 0) or 0)
        payload["closes_time_stop"] = int(getattr(self, "closes_time_stop", 0) or 0)
        payload["closes_unknown"] = int(getattr(self, "closes_unknown", 0) or 0)
        # Stage-wide exit forensics (all stages — not only Stage-2 peak blob).
        from lumina_core.birth.starship_edgescore_core import settlement_progress_fields

        payload.update(
            settlement_progress_fields(
                closes_stop=int(getattr(self, "stage_closes_stop_cum", 0) or 0),
                closes_target=int(getattr(self, "stage_closes_target_cum", 0) or 0),
                closes_time_stop=int(
                    getattr(self, "stage_closes_time_stop_cum", 0) or 0
                ),
                closes_flatten=int(getattr(self, "stage_closes_flatten_cum", 0) or 0),
                closes_unknown=int(
                    getattr(self, "stage_closes_unknown_cum", 0) or 0
                ),
            )
        )
        payload["stage2_rolling_pass_streak"] = int(
            getattr(self, "_stage2_rolling_pass_streak", 0) or 0
        )
        payload["over_trading_detected"] = bool(
            getattr(self, "over_trading_detected", False)
        )
        payload["mean_entry_stop_pct"] = round(
            float(getattr(self, "mean_entry_stop_pct", 0.0) or 0.0), 6
        )
        payload["mean_entry_target_pct"] = round(
            float(getattr(self, "mean_entry_target_pct", 0.0) or 0.0), 6
        )
        payload["expectancy_quality_step_source"] = str(
            getattr(self, "expectancy_quality_step_source", "") or ""
        )
        payload["_exhausted_ladder_swarm_used"] = bool(
            getattr(self, "_exhausted_ladder_swarm_used", False)
        )
        # Starship champion / swarm persistence (resume-safe + poison sanitize).
        try:
            from lumina_core.birth.starship_birth import (
                live_stage_winrate,
                publish_edgescore_champion_fields,
                sanitize_edgescore_champion,
            )

            best, at_trade, cleared = sanitize_edgescore_champion(
                best_edgescore=float(getattr(self, "best_edgescore", 0.0) or 0.0),
                best_edgescore_at_trade=int(
                    getattr(self, "best_edgescore_at_trade", 0) or 0
                ),
                best_winrate=float(getattr(self.plateau_state, "best_winrate", 0.0) or 0.0),
                required=int(self.required),
                cfg=self.cur_cfg,
                stage=str(getattr(self.stage, "value", self.stage) or ""),
                live_winrate=live_stage_winrate(
                    wins=int(getattr(self, "stage_wins", 0) or 0),
                    trades=int(getattr(self, "stage_trades", 0) or 0),
                ),
            )
            self.best_edgescore = best
            self.best_edgescore_at_trade = at_trade
            if cleared:
                self.best_edgescore_policy_path = ""
            payload.update(
                publish_edgescore_champion_fields(
                    best_edgescore=float(getattr(self, "best_edgescore", 0.0) or 0.0),
                    best_edgescore_at_trade=int(
                        getattr(self, "best_edgescore_at_trade", 0) or 0
                    ),
                    best_edgescore_policy_path=str(
                        getattr(self, "best_edgescore_policy_path", "") or ""
                    ),
                    stage_trades=int(self.stage_trades),
                    required=int(self.required),
                    cfg=self.cur_cfg,
                )
            )
        except Exception as exc:
            logger.debug("birth.starship.champion_sanitize_metrics_failed: %s", exc)
            payload["best_edgescore"] = None
            payload["best_edgescore_at_trade"] = 0
            payload["best_edgescore_policy_path"] = ""
        payload["swarm_retearnament_used"] = bool(getattr(self, "swarm_retearnament_used", False))
        payload["swarm_rejected_no_lift"] = bool(
            getattr(self, "swarm_rejected_no_lift", False)
            or getattr(self.swarm_state, "rejected_no_lift", False)
        )
        tournament_lift_ok = bool(
            getattr(
                self,
                "swarm_tournament_lift_ok",
                getattr(self, "swarm_edgescore_lift_ok", False),
            )
        )
        tournament_at_start = round(
            float(
                getattr(
                    self,
                    "swarm_tournament_at_start",
                    getattr(self, "swarm_edgescore_at_start", -1.0),
                )
            ),
            6,
        )
        from lumina_core.birth.starship_swarm_gates import dual_write_tournament_lift_keys

        dual_write_tournament_lift_keys(
            payload,
            lift_ok=tournament_lift_ok,
            at_start=tournament_at_start,
        )
        payload["swarm_champion_accepted"] = bool(
            getattr(self, "swarm_champion_accepted", False)
            or getattr(self.swarm_state, "champion_accepted", False)
        )
        return payload

    def _maybe_periodic_checkpoint(self, phase: str) -> None:
        interval = max(60, int(self.cur_cfg.checkpoint_interval_sec))
        if self.host._last_checkpoint_at <= 0.0 or time.time() - self.host._last_checkpoint_at >= interval:
            self.host._persist_checkpoint(
                training_mode=self.training_mode,
                curriculum_stage=self.stage.value,
                phase=phase,
                stage_metrics=self._stage_metrics_payload(),
            )

