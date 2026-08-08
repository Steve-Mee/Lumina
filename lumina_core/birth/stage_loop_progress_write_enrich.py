"""Scorecard enrichment helpers for progress write (M5 extract)."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.plateau_escalator import (
    build_plateau_audit,
    plateau_min_stage_trades,
    progress_fields as plateau_progress_fields,
    quarantine_progress_payload,
    remediation_is_exhausted,
)
from lumina_core.birth.stage_scorecard import enrich_adaptation_payload
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class StageLoopProgressWriteEnrichMixin(StageLoopMixinBase):
    """Adaptation / plateau / recovery / ops KPI fields on scorecard."""

    def _enrich_progress_scorecard(
        self,
        scorecard: dict[str, Any],
        *,
        phase: str,
        current_stage_trades: int,
        constitution_fields: dict[str, Any],
        rollout_steps: int,
        rolling_for_scorecard: float | None,
        rolling_for_blocker: float | None,
        rolling_source: str,
        rolling_covered: int,
        roll_window: int,
        hygiene_wr_telemetry: Any,
    ) -> None:
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
        rem_exhausted = remediation_is_exhausted(
            remediation_active=self.remediation_state.active,
            remediation_step=self.remediation_state.remediation_step,
            remediation_cycle=self.remediation_state.remediation_cycle,
            cfg=self.cur_cfg,
        )
        scorecard.update(
            build_plateau_audit(
                self.plateau_state,
                stage_trades=current_stage_trades,
                required=self.required,
                cfg=self.cur_cfg,
                progress=scorecard,
                remediation_exhausted=rem_exhausted,
                trade_budget_remaining=max(0, self.trade_budget_cap - self.host.cumulative_trades),
            )
        )
        scorecard["stall_remediation_cycle"] = int(self.remediation_state.remediation_cycle)
        scorecard["stall_remediation_step"] = int(self.remediation_state.remediation_step)
        scorecard["stall_remediation_max_steps"] = int(self.cur_cfg.stall_remediation_max_steps)
        scorecard["stall_remediation_max_cycles"] = int(self.cur_cfg.stall_remediation_max_cycles)
        try:
            from lumina_core.birth.recovery_compress import compress_recovery

            budget_rem = max(0, int(self.trade_budget_cap) - int(self.host.cumulative_trades))
            scorecard["recovery"] = compress_recovery(
                phase=phase,
                wall_behavior=str(self.cur_cfg.wall_behavior or ""),
                adaptation_tier=int(self.adaptation_tier),
                max_adaptation_tiers=int(self.cur_cfg.max_adaptation_tiers),
                retries_this_stage=int(self.retries_this_stage),
                max_stage_retries=int(self.cur_cfg.max_stage_retries),
                escalation_level=int(getattr(self, "escalation_level", 0) or 0),
                plateau_active=bool(self.plateau_state.active),
                plateau_full_recovery_cycles=int(self.plateau_state.full_recovery_cycles),
                plateau_evolution_step=int(self.plateau_state.evolution_step),
                plateau_noop_count=int(self.plateau_state.evolution_noop_count),
                remediation_active=bool(self.remediation_state.active),
                remediation_step=int(self.remediation_state.remediation_step),
                remediation_cycle=int(self.remediation_state.remediation_cycle),
                remediation_max_steps=int(self.cur_cfg.stall_remediation_max_steps),
                remediation_max_cycles=int(self.cur_cfg.stall_remediation_max_cycles),
                remediation_exhausted=rem_exhausted,
                phoenix_enabled=bool(getattr(self.cur_cfg, "phoenix_loop_enabled", False)),
                phoenix_cycles=int(
                    getattr(self.organism_autonomy_state.phoenix, "phoenix_count", 0) or 0
                ),
                autonomous_recovery_count=int(
                    getattr(self.organism_autonomy_state, "autonomous_recovery_count", 0) or 0
                ),
                swarm_active=bool(getattr(self.swarm_state, "active", False)),
                swarm_rejected_no_lift=bool(
                    getattr(self, "swarm_rejected_no_lift", False)
                    or getattr(self.swarm_state, "rejected_no_lift", False)
                ),
                needs_attention=bool(scorecard.get("needs_attention")),
                terminal_stall_reason=str(scorecard.get("terminal_stall_reason") or "") or None,
                trade_budget_remaining=budget_rem,
                strong_recovery_mode=bool(getattr(self, "strong_recovery_mode", False)),
                provisional_graduation=bool(
                    scorecard.get("provisional_graduation") or scorecard.get("provisional_pass")
                ),
            )
        except Exception:
            logger.debug("birth.recovery_compress failed", exc_info=True)

        scorecard["stage1_winrate_gate"] = float(
            getattr(self.cur_cfg, "stage1_winrate_pass_threshold", 0.45)
        )
        scorecard["stage1_winrate_recommended"] = float(
            getattr(self.cur_cfg, "stage1_winrate_recommended", 0.45)
        )
        self._progress_enrich_starship_scorecard(
            scorecard,
            current_stage_trades=current_stage_trades,
            rolling_for_blocker=rolling_for_blocker,
        )
        scorecard["stage_pass_gate_trades"] = int(self.required)
        scorecard["stage_budget_trades"] = int(self.target)
        scorecard["plateau_min_stage_trades"] = int(
            plateau_min_stage_trades(self.stage, self.cur_cfg)
        )
        try:
            r_wr, r_src, r_cov = self._rolling_winrate_meta()
            scorecard["rolling_winrate_500"] = round(float(r_wr), 6)
            scorecard["rolling_winrate_source"] = str(r_src)
            scorecard["rolling_window_trades_covered"] = int(r_cov)
        except Exception:
            r_wr = rolling_for_scorecard
            r_src = rolling_source
            r_cov = rolling_covered
            if r_wr is not None:
                scorecard["rolling_winrate_500"] = round(float(r_wr), 6)
            else:
                scorecard["rolling_winrate_500"] = round(self._rolling_winrate_500(), 6)
            scorecard["rolling_winrate_source"] = str(
                getattr(self, "_rolling_winrate_source", r_src) or "lifetime_fallback"
            )
            scorecard["rolling_window_trades_covered"] = int(
                getattr(self, "_rolling_window_trades_covered", r_cov) or 0
            )
        lifetime_wr = float(self.stage_wins) / float(max(1, current_stage_trades))
        if self.stage.value == "stage3_mixed":
            hygiene_floor = float(getattr(self.cur_cfg, "stage3_winrate_floor", 0.35))
        else:
            hygiene_floor = float(getattr(self.cur_cfg, "stage1_winrate_pass_floor", 0.35))
        scorecard.update(
            hygiene_wr_telemetry(
                lifetime_wr=lifetime_wr,
                rolling_wr=(
                    float(scorecard["rolling_winrate_500"])
                    if scorecard.get("rolling_winrate_500") is not None
                    else None
                ),
                rolling_source=str(scorecard.get("rolling_winrate_source") or ""),
                rolling_covered=int(scorecard.get("rolling_window_trades_covered") or 0),
                floor=hygiene_floor,
                window=roll_window,
            )
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
            avg_rollout_sec = self.rollout_wall_clock_total_sec / float(
                self.rollout_wall_clock_samples
            )
            scorecard["wall_clock_rollout_sec_avg"] = round(avg_rollout_sec, 2)
            trades_per_min = (
                float(self.stage_trades) / max(0.01, self.rollout_wall_clock_total_sec)
            ) * 60.0
            scorecard["wall_clock_trades_per_min"] = round(trades_per_min, 1)
        soft_blocks = int(constitution_fields.get("constitution_soft_blocks_session", 0) or 0)
        signals = max(1, int(self.stage_total_signals) + int(rollout_steps or 0))
        scorecard["soft_block_rate_per_1k_signals"] = round(
            (1000.0 * float(soft_blocks)) / float(signals), 1
        )
        if self.evolution_last_action_applied is not None:
            scorecard["evolution_last_action_applied"] = bool(self.evolution_last_action_applied)
            scorecard["evolution_last_action_detail"] = str(
                self.evolution_last_action_detail or ""
            )
        if self.cur_cfg.meta_controller_enabled:
            scorecard.update(self.bus.meta_scorecard_fields(self.stage, self.meta_last_plan))
        # Stage2 Participation Envelope telemetry (hard occupancy physics).
        scorecard["stage2_participation_envelope_enabled"] = bool(
            getattr(self.cur_cfg, "stage2_participation_envelope_enabled", True)
        )
        scorecard["participation_force_open"] = int(
            getattr(self, "participation_force_open", 0) or 0
        )
        scorecard["participation_force_hold"] = int(
            getattr(self, "participation_force_hold", 0) or 0
        )
        scorecard["participation_force_flat"] = int(
            getattr(self, "participation_force_flat", 0) or 0
        )
        scorecard["participation_overrides_total"] = int(
            getattr(self, "participation_overrides_total", 0) or 0
        )
        scorecard["participation_last_mode"] = str(
            getattr(self, "participation_last_mode", "") or "PASSTHROUGH"
        )


__all__ = ["StageLoopProgressWriteEnrichMixin"]
