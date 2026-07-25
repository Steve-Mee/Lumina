"""StageLoopProgressMixin — StageLoopSession mixin."""

from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.plateau_escalator import (
    build_plateau_audit,
    plateau_min_stage_trades,
    progress_fields as plateau_progress_fields,
    quarantine_progress_payload,
    remediation_is_exhausted,
)
from lumina_core.birth.progress import merge_birth_progress_extra
from lumina_core.birth.stage_scorecard import (
    build_scorecard_payload,
    enrich_adaptation_payload,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class StageLoopProgressMixin(StageLoopMixinBase):
    """See StageLoopSession for attributes."""

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

    def _write_progress(self, 
        *,
        phase: str,
        message: str,
        chunk_trades: int = 0,
        rollout_steps: int = 0,
        exploration_active: bool = False,
        hold_ratio: float = 0.0,
    ) -> None:
        current_stage_trades = self.stage_trades + chunk_trades
        elapsed_snapshot = max(0.0, time.time() - self.scorecard_snapshot_at)
        constitution_fields = self.host._constitution_progress_fields()
        rolling_for_scorecard: float | None = None
        rolling_source = "lifetime_fallback"
        rolling_covered = 0
        try:
            rolling_for_scorecard, rolling_source, rolling_covered = self._rolling_winrate_meta()
        except Exception:
            try:
                rolling_for_scorecard = float(self._rolling_winrate_500())
            except Exception:
                rolling_for_scorecard = None
        # Blocker/pass skill: only treat rolling as independent when not lifetime-fallback.
        rolling_for_blocker = (
            rolling_for_scorecard
            if rolling_source in ("true_window", "partial_window")
            else None
        )
        scorecard = build_scorecard_payload(
            stage=self.stage,
            curriculum_index=self.stage_index + 1,
            stages_passed=list(self.host._stages_passed),
            stage_trades=current_stage_trades,
            stage_wins=self.stage_wins,
            stage_hold_signals=self.stage_hold_signals,
            stage_total_signals=self.stage_total_signals,
            constitution_violations=int(constitution_fields["constitution_violations_session"]),
            target_trades=self.target,
            phase=phase,
            patterns_mined=self.patterns_mined,
            learning_attempt=self.attempt + 1,
            prev_stage_trades=self.scorecard_snapshot_trades,
            prev_patterns_mined=self.scorecard_snapshot_patterns,
            snapshot_elapsed_sec=elapsed_snapshot,
            stage_range_flat_bars=self.stage_range_flat_bars,
            stage_range_total_signals=self.stage_range_total_signals,
            stage_range_round_trips=self.stage_range_round_trips,
            provisional_pass=self.gen0_provisional,
            cfg=self.cur_cfg,
            rolling_winrate=rolling_for_blocker,
        )
        wa_metrics = self.bus.adaptation_recovery_metrics(self.stage)
        adaptation_fields = enrich_adaptation_payload(
            stage_trades=current_stage_trades,
            required=self.required,
            winrate_history=self.winrate_history,
            retries_this_stage=self.retries_this_stage,
            adaptation_tier=self.adaptation_tier,
            max_adaptation_tiers=self.cur_cfg.max_adaptation_tiers,
            max_stage_retries=self.cur_cfg.max_stage_retries,
            adaptation_history=self.adaptation_history,
            adaptation_enabled=self.cur_cfg.adaptation_enabled,
            wall_behavior=self.cur_cfg.wall_behavior,
            reward_history=self.reward_history,
            strong_recovery_mode=self.strong_recovery_mode,
            velocity_stall_attempts=self.low_velocity_attempts,
            strong_recovery_attempts=self.strong_recovery_attempts,
            provisional_pass_considered=self.provisional_pass_considered,
            wall_triggers_total=int(wa_metrics.get("wall_triggers_total", 0) or 0),
            autonomous_recovery_attempts=int(
                wa_metrics.get("autonomous_recovery_attempts", 0) or 0
            ),
            autonomous_recovery_successes=int(
                wa_metrics.get("autonomous_recovery_successes", 0) or 0
            ),
            autonomous_recovery_rate_pct=float(
                wa_metrics.get("autonomous_recovery_rate_pct", 0.0) or 0.0
            ),
        )
        scorecard.update(adaptation_fields)
        scorecard.update(
            plateau_progress_fields(
                self.plateau_state,
                stage_trades=current_stage_trades,
                required=self.required,
                cfg=self.cur_cfg,
            )
        )
        scorecard.update(
            build_plateau_audit(
                self.plateau_state,
                stage_trades=current_stage_trades,
                required=self.required,
                cfg=self.cur_cfg,
                progress=scorecard,
                remediation_exhausted=remediation_is_exhausted(
                    remediation_active=self.remediation_state.active,
                    remediation_step=self.remediation_state.remediation_step,
                    remediation_cycle=self.remediation_state.remediation_cycle,
                    cfg=self.cur_cfg,
                ),
                trade_budget_remaining=max(0, self.trade_budget_cap - self.host.cumulative_trades),
            )
        )
        scorecard["stall_remediation_cycle"] = int(self.remediation_state.remediation_cycle)
        scorecard["stall_remediation_step"] = int(self.remediation_state.remediation_step)
        scorecard["stall_remediation_max_steps"] = int(self.cur_cfg.stall_remediation_max_steps)
        scorecard["stall_remediation_max_cycles"] = int(self.cur_cfg.stall_remediation_max_cycles)
        scorecard["stage1_winrate_gate"] = float(
            getattr(self.cur_cfg, "stage1_winrate_pass_threshold", 0.45)
        )
        scorecard["stage1_winrate_recommended"] = float(
            getattr(self.cur_cfg, "stage1_winrate_recommended", 0.45)
        )
        scorecard["stage_pass_gate_trades"] = int(self.required)
        scorecard["stage_budget_trades"] = int(self.target)
        scorecard["plateau_min_stage_trades"] = int(plateau_min_stage_trades(self.stage, self.cur_cfg))
        try:
            r_wr, r_src, r_cov = self._rolling_winrate_meta()
            scorecard["rolling_winrate_500"] = round(float(r_wr), 6)
            scorecard["rolling_winrate_source"] = str(r_src)
            scorecard["rolling_window_trades_covered"] = int(r_cov)
        except Exception:
            scorecard["rolling_winrate_500"] = round(self._rolling_winrate_500(), 6)
            scorecard["rolling_winrate_source"] = str(
                getattr(self, "_rolling_winrate_source", rolling_source) or "lifetime_fallback"
            )
            scorecard["rolling_window_trades_covered"] = int(
                getattr(self, "_rolling_window_trades_covered", rolling_covered) or 0
            )
        scorecard["rollouts_since_last_adaptation"] = int(
            getattr(self, "rollouts_since_last_adaptation", 0) or 0
        )
        scorecard["last_adaptation_stage_trades"] = int(
            getattr(self, "last_adaptation_stage_trades", -1) or -1
        )
        scorecard.update(
            quarantine_progress_payload(
                self.plateau_quarantine,
                stage_trades=current_stage_trades,
                cfg=self.cur_cfg,
            )
        )
        scorecard["sim_ticks_processed_cumulative"] = int(self.sim_ticks_processed_cumulative)
        if self.rollout_wall_clock_samples > 0 and self.stage_trades > 0:
            avg_rollout_sec = self.rollout_wall_clock_total_sec / float(self.rollout_wall_clock_samples)
            scorecard["wall_clock_rollout_sec_avg"] = round(avg_rollout_sec, 2)
            trades_per_min = (float(self.stage_trades) / max(0.01, self.rollout_wall_clock_total_sec)) * 60.0
            scorecard["wall_clock_trades_per_min"] = round(trades_per_min, 1)
        if self.evolution_last_action_applied is not None:
            scorecard["evolution_last_action_applied"] = bool(self.evolution_last_action_applied)
            scorecard["evolution_last_action_detail"] = str(self.evolution_last_action_detail or "")
        if self.cur_cfg.meta_controller_enabled:
            scorecard.update(self.bus.meta_scorecard_fields(self.stage, self.meta_last_plan))
        elapsed_stage_sec = max(0.0, time.time() - self.stage_started_at)
        progress_extra = merge_birth_progress_extra(constitution_fields, scorecard)
        self.host._emit_birth_progress(
            stage="training_running",
            phase=phase,
            message=message,
            progress_pct=self.stage_progress_pct,
            cumulative_trades=self.host.cumulative_trades + chunk_trades,
            target_trades=self.trade_budget_cap,
            ppo_steps=self.host.ppo_steps,
            birth_start_time=self.host.birth_start_time,
            curriculum_stage=self.stage.value,
            stage_trades=current_stage_trades,
            stage_hold_signals=self.stage_hold_signals,
            stage_total_signals=self.stage_total_signals,
            stage_range_hold_signals=self.stage_range_hold_signals,
            stage_range_total_signals=self.stage_range_total_signals,
            stage_range_flat_bars=self.stage_range_flat_bars,
            stage_range_round_trips=self.stage_range_round_trips,
            stage_range_flat_ratio=round(
                float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals)),
                4,
            ),
            rollout_trades=chunk_trades,
            rollout_steps=rollout_steps,
            hold_ratio=round(hold_ratio, 4),
            exploration_active=exploration_active,
            learning_attempt=self.attempt + 1,
            escalation_level=self.escalation_level,
            gen0_provisional=self.gen0_provisional,
            patterns_mined=self.patterns_mined,
            oracle_wins=self.oracle_wins,
            oracle_last_scanned=int(getattr(self, "oracle_last_scanned", 0) or 0),
            oracle_last_patterns=int(getattr(self, "oracle_last_patterns", 0) or 0),
            oracle_last_stop_pct=round(float(getattr(self, "oracle_last_stop_pct", 0.0) or 0.0), 6),
            oracle_last_target_pct=round(
                float(getattr(self, "oracle_last_target_pct", 0.0) or 0.0), 6
            ),
            oracle_last_reason=str(getattr(self, "oracle_last_reason", "") or ""),
            display_winrate_scope="stage_current",
            training_mode=str(self.training_mode),
            allow_provisional=bool(self.allow_provisional),
            data_days_loaded=self.data_days_loaded,
            expansion_step=self.expansion_step,
            stage_wall_remaining_sec=max(
                0, int(self.cur_cfg.max_stage_wall_sec) - int(elapsed_stage_sec)
            ),
            quality_score=float(self.host._data_manifest.get("quality_score", 0.0) or 0.0),
            intra_hard_pct=round(float(self.intra_state.hard_pct), 4) if self.intra_state else None,
            intra_easy_winrate=round(
                float(self.intra_state.easy_wins) / float(max(1, self.intra_state.easy_trades)),
                4,
            )
            if self.intra_state and self.intra_state.easy_trades > 0
            else None,
            needs_attention=False,
            attention_summary="",
            attention_reason_code="",
            attention_recommended_actions=[],
            user_initiated_stop=False,
            extra_parts=(progress_extra,),
        )
        if (
            current_stage_trades > self.scorecard_snapshot_trades
            or self.patterns_mined > self.scorecard_snapshot_patterns
        ):
            self.scorecard_snapshot_trades = current_stage_trades
            self.scorecard_snapshot_patterns = self.patterns_mined
            self.scorecard_snapshot_at = time.time()
        self.last_progress_write_at = time.time()

