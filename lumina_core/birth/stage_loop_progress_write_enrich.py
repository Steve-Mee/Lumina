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
        evo_max = self._evolution_max_steps()
        scorecard.update(
            plateau_progress_fields(
                self.plateau_state,
                stage_trades=current_stage_trades,
                required=self.required,
                cfg=self.cur_cfg,
                max_steps=evo_max,
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
                max_steps=evo_max,
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
            # C2: promote recovery SSOT attention to top-level progress (page unattended Birth)
            rec = scorecard.get("recovery") if isinstance(scorecard.get("recovery"), dict) else {}
            rec_flags = rec.get("flags") if isinstance(rec.get("flags"), dict) else {}
            if bool(rec_flags.get("needs_attention")) or rec.get("active") == "terminal_stall":
                scorecard["needs_attention"] = True
                if not str(scorecard.get("attention_reason_code") or "").strip():
                    reason = str(
                        scorecard.get("terminal_stall_reason")
                        or rec_flags.get("terminal_stall_reason")
                        or "terminal_stall"
                    ).strip()
                    scorecard["attention_reason_code"] = reason
                if not str(scorecard.get("attention_summary") or "").strip():
                    scorecard["attention_summary"] = (
                        f"Terminal recovery: {scorecard.get('attention_reason_code')} — "
                        f"next_action={rec.get('next_action', 'expand_data_or_wipe_genesis')}"
                    )
                if not scorecard.get("attention_recommended_actions"):
                    scorecard["attention_recommended_actions"] = [
                        "expand_data",
                        "wipe_and_retry",
                        "human_review",
                    ]
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
        elif self.stage.value == "stage1_trend" and bool(
            getattr(self.cur_cfg, "birth_survival_pass_enabled", True)
        ):
            hygiene_floor = float(
                getattr(self.cur_cfg, "birth_survival_wr_floor", 0.20) or 0.20
            )
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
        scorecard["participation_force_exit"] = int(
            getattr(self, "participation_force_exit", 0) or 0
        )
        scorecard["participation_passthrough"] = int(
            getattr(self, "participation_passthrough", 0) or 0
        )
        scorecard["participation_overrides_total"] = int(
            getattr(self, "participation_overrides_total", 0) or 0
        )
        scorecard["participation_last_mode"] = str(
            getattr(self, "participation_last_mode", "") or "PASSTHROUGH"
        )
        from lumina_core.birth.stage3_inband_idle import s3_inband_progress_fields
        scorecard.update(s3_inband_progress_fields(self))
        try:
            scorecard["occupancy_control_flat"] = round(
                float(getattr(self, "occupancy_control_flat", 0.0) or 0.0), 4
            )
        except (TypeError, ValueError):
            scorecard["occupancy_control_flat"] = 0.0
        scorecard["expectancy_quality_step"] = int(
            getattr(self, "expectancy_quality_step", 0) or 0
        )
        scorecard["stage2_bootstrap_patterns"] = int(
            getattr(self, "stage2_bootstrap_patterns", 0) or 0
        )
        scorecard["stage2_bootstrap_updates"] = int(
            getattr(self, "stage2_bootstrap_updates", 0) or 0
        )
        scorecard["stage2_action_head_reinit"] = bool(
            getattr(self, "stage2_action_head_reinit", False)
        )
        # Stage-1 foundation telemetry (learning target ≠ survival pass floor).
        try:
            from lumina_core.birth.curriculum import CurriculumStage
            from lumina_core.birth.stage1_foundation import compute_stage1_foundation

            if self.stage == CurriculumStage.STAGE1_TREND:
                rolling = None
                try:
                    rolling, _, _ = self._rolling_winrate_meta()
                except Exception:
                    rolling = None
                edge = getattr(self, "_edge_vs_random", None)
                try:
                    edge_f = float(edge) if edge is not None else None
                except (TypeError, ValueError):
                    edge_f = None
                s1 = compute_stage1_foundation(
                    stage_trades=int(getattr(self, "stage_trades", 0) or 0),
                    stage_wins=int(getattr(self, "stage_wins", 0) or 0),
                    required=int(getattr(self, "required", 200) or 200),
                    survival_wr_floor=float(
                        getattr(self.cur_cfg, "birth_survival_wr_floor", 0.20) or 0.20
                    ),
                    foundation_target_wr=float(
                        getattr(self.cur_cfg, "stage1_foundation_target_wr", 0.30) or 0.30
                    ),
                    anti_thrash_wr=float(
                        getattr(self.cur_cfg, "stage1_anti_thrash_wr", 0.25) or 0.25
                    ),
                    edge_vs_random=edge_f,
                    rolling_winrate=float(rolling) if rolling is not None else None,
                )
                scorecard.update(s1.as_progress_fields())
            # Persist last Stage-1 handoff flags on host for Stage-2 HUD.
            handoff = getattr(self.host, "_stage1_transfer_handoff", None)
            if isinstance(handoff, dict):
                scorecard["stage1_transfer_handoff_ok"] = bool(handoff.get("ok"))
                scorecard["stage1_transfer_purge_mode"] = str(
                    (handoff.get("buffer_purge") or {}).get("mode") or ""
                )
                scorecard["stage1_transfer_reinit_ok"] = bool(
                    (handoff.get("action_head_reinit") or {}).get("ok")
                )
        except Exception:
            pass
        # Pilot vs plant skill metric + economic honesty (floors unchanged).
        try:
            from lumina_core.birth.stage2_skill_metric import resolve_stage2_skill_counts
            from lumina_core.birth.birth_trade_geometry import economic_skill_gap

            sc = resolve_stage2_skill_counts(
                total_trades=int(getattr(self, "stage_trades", 0) or 0),
                total_wins=int(getattr(self, "stage_wins", 0) or 0),
                policy_trades=int(getattr(self, "stage_policy_trades", 0) or 0),
                policy_wins=int(getattr(self, "stage_policy_wins", 0) or 0),
                plant_trades=int(getattr(self, "stage_plant_trades", 0) or 0),
                plant_wins=int(getattr(self, "stage_plant_wins", 0) or 0),
                skill_only=bool(
                    getattr(self.cur_cfg, "stage2_skill_metric_policy_only", True)
                ),
                required=int(getattr(self, "required", 300) or 300),
                skill_min_trades=getattr(self.cur_cfg, "stage2_skill_min_trades", None),
            )
            scorecard.update(sc.as_progress_fields())
            be_wr = float(
                scorecard.get("geometry_breakeven_wr_after_cost")
                or getattr(getattr(self, "_birth_trade_geometry", None), "breakeven_wr_after_cost", 0.0)
                or 0.0
            )
            skill_wr = float(sc.skill_winrate)
            scorecard["skill_pass_wr_floor"] = 0.35  # ≡ exp −0.15; never moved
            scorecard["economic_be_wr"] = round(be_wr, 4)
            scorecard["skill_wr_vs_economic_be"] = round(skill_wr - be_wr, 4)
            scorecard["economic_training_pressure"] = round(
                economic_skill_gap(be_wr=be_wr, skill_wr=skill_wr), 4
            )
            # Dual truth: when skill metric grades pass, HUD expectancy follows pilot.
            if bool(sc.skill_eligible) and bool(sc.skill_only):
                scorecard["expectancy_proxy"] = round(float(sc.skill_expectancy), 4)
                scorecard["expectancy_proxy_source"] = "skill_policy_only"
            else:
                scorecard.setdefault(
                    "expectancy_proxy_source",
                    str(scorecard.get("expectancy_proxy_source") or "total_or_rolling"),
                )
            # Stash skill_wr for first-touch pressure after thr is computed below.
            scorecard["_skill_wr_for_ft"] = float(skill_wr)
        except Exception:
            scorecard.setdefault("skill_metric_policy_only", True)
            scorecard.setdefault("stage_policy_trades", 0)
            scorecard.setdefault("stage_plant_trades", 0)
        # Geometry + exit physics always on progress SSOT (never omit keys).
        stop_g = getattr(self, "_birth_trade_stop_pct", None)
        target_g = getattr(self, "_birth_trade_target_pct", None)
        scorecard["birth_trade_stop_pct"] = (
            round(float(stop_g), 6) if stop_g is not None else 0.0
        )
        scorecard["birth_trade_target_pct"] = (
            round(float(target_g), 6) if target_g is not None else 0.0
        )
        scorecard["birth_trade_geometry_source"] = str(
            getattr(self, "_birth_trade_geometry_source", None) or "unset"
        )
        scorecard["closes_stop"] = int(getattr(self, "closes_stop", 0) or 0)
        scorecard["closes_target"] = int(getattr(self, "closes_target", 0) or 0)
        scorecard["closes_flatten"] = int(getattr(self, "closes_flatten", 0) or 0)
        scorecard["closes_time_stop"] = int(getattr(self, "closes_time_stop", 0) or 0)
        scorecard["closes_unknown"] = int(getattr(self, "closes_unknown", 0) or 0)
        scorecard["mean_entry_stop_pct"] = round(
            float(getattr(self, "mean_entry_stop_pct", 0.0) or 0.0), 6
        )
        scorecard["mean_entry_target_pct"] = round(
            float(getattr(self, "mean_entry_target_pct", 0.0) or 0.0), 6
        )
        # Geometry forensics (v4) — always emit; proves time-ordered micro SSOT.
        try:
            from lumina_core.birth.birth_trade_geometry import apply_geometry_forensics

            apply_geometry_forensics(
                scorecard, getattr(self, "_birth_trade_geometry", None)
            )
        except Exception:
            scorecard.setdefault("geometry_time_ordered", False)
            scorecard.setdefault("geometry_p40_raw", 0.0)
            scorecard.setdefault("geometry_hold_bars", 0)
            scorecard.setdefault("geometry_pool_size", 0)
            scorecard.setdefault("geometry_macro_rejected", False)
            scorecard.setdefault("geometry_floor_bound", False)
            scorecard.setdefault("geometry_breakeven_wr_after_cost", 0.0)
            scorecard.setdefault("geometry_cost_usd", 0.0)
            scorecard.setdefault("geometry_ref_price", 0.0)
        # Edge vs random first-touch (diagnostic; does not change floors).
        try:
            thr = float(getattr(self, "_first_touch_target_hit_rate", 0.0) or 0.0)
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
            scorecard["first_touch_target_hit_rate"] = round(thr, 4)
            live_wr = float(
                scorecard.get("hygiene_wr_effective")
                or scorecard.get("rolling_winrate_500")
                or scorecard.get("stage_winrate")
                or getattr(self, "last_winrate", 0.0)
                or 0.0
            )
            if thr > 0:
                edge = live_wr - thr
                scorecard["edge_vs_random"] = round(edge, 4)
                self._edge_vs_random = edge
                if edge < 0 and bool(scorecard.get("expectancy_stall_detected")):
                    try:
                        from lumina_core.logging_utils import get_logger

                        get_logger("lumina.birth.expectancy").warning(
                            "birth.expectancy.anti_edge wr=%.4f first_touch_thr=%.4f "
                            "edge=%.4f (policy worse than random first-touch)",
                            live_wr,
                            thr,
                            edge,
                        )
                    except Exception:
                        pass
            else:
                scorecard.setdefault("edge_vs_random", 0.0)
        except Exception:
            scorecard.setdefault("first_touch_target_hit_rate", 0.0)
            scorecard.setdefault("edge_vs_random", 0.0)
        # First-touch pressure after thr is known (skill dual-truth, floors unchanged).
        try:
            thr = float(scorecard.get("first_touch_target_hit_rate") or 0.0)
            skill_wr = float(
                scorecard.get("_skill_wr_for_ft")
                or scorecard.get("skill_metric_winrate")
                or scorecard.get("stage_winrate")
                or 0.0
            )
            if thr > 0:
                scorecard["skill_wr_vs_first_touch"] = round(skill_wr - thr, 4)
                scorecard["first_touch_training_pressure"] = round(
                    max(0.0, thr - skill_wr), 4
                )
            scorecard.pop("_skill_wr_for_ft", None)
        except Exception:
            scorecard.pop("_skill_wr_for_ft", None)
        # Stage-2 Pass Vector SSOT (multi-blocker gaps — never lowers floors).
        try:
            from lumina_core.birth.stage2_pass_vector import compute_stage2_pass_vector
            from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

            signals = int(getattr(self, "stage_range_total_signals", 0) or 0)
            flat_bars = int(getattr(self, "stage_range_flat_bars", 0) or 0)
            flat_pv = (
                float(flat_bars) / float(max(1, signals)) if signals > 0 else 0.5
            )
            # Prefer skill expectancy when policy-only grades the pilot.
            exp_proxy = float(
                scorecard.get("skill_metric_expectancy")
                if scorecard.get("expectancy_proxy_source") == "skill_policy_only"
                else (
                    scorecard.get("expectancy_proxy")
                    or (
                        float(scorecard.get("hygiene_wr_effective") or 0.0) - 0.50
                        if scorecard.get("hygiene_wr_effective") is not None
                        else (float(scorecard.get("stage_winrate") or 0.0) - 0.50)
                    )
                )
            )
            exp_floor = float(stage2_expectancy_floor(self.cur_cfg))
            edge_pv = float(scorecard.get("edge_vs_random") or getattr(self, "_edge_vs_random", 0.0) or 0.0)
            pv = compute_stage2_pass_vector(
                range_flat_ratio=flat_pv,
                expectancy=exp_proxy,
                exp_floor=exp_floor,
                edge_vs_random=edge_pv,
                band_lo=float(
                    getattr(self.cur_cfg, "stage2_participation_band_lo", 0.30) or 0.30
                ),
                band_hi=float(
                    getattr(self.cur_cfg, "stage2_participation_band_hi", 0.70) or 0.70
                ),
            )
            scorecard.update(pv.as_progress_fields())
            # PR-I: pass HUD SSOT = same leg as EdgeScore (max skill, rolling).
            pass_exp = float(exp_proxy)
            pass_src = str(
                scorecard.get("expectancy_proxy_source")
                or ("skill_policy_only" if scorecard.get("skill_metric_eligible") else "total")
            )
            try:
                from lumina_core.birth.stage2_skill_metric import (
                    resolve_stage2_skill_counts,
                    skill_expectancy_for_pass,
                )

                sc2 = resolve_stage2_skill_counts(
                    total_trades=int(getattr(self, "stage_trades", 0) or 0),
                    total_wins=int(getattr(self, "stage_wins", 0) or 0),
                    policy_trades=int(getattr(self, "stage_policy_trades", 0) or 0),
                    policy_wins=int(getattr(self, "stage_policy_wins", 0) or 0),
                    plant_trades=int(getattr(self, "stage_plant_trades", 0) or 0),
                    plant_wins=int(getattr(self, "stage_plant_wins", 0) or 0),
                    skill_only=bool(
                        getattr(self.cur_cfg, "stage2_skill_metric_policy_only", True)
                    ),
                    required=int(getattr(self, "required", 300) or 300),
                    skill_min_trades=getattr(
                        self.cur_cfg, "stage2_skill_min_trades", None
                    ),
                )
                roll_h = scorecard.get("hygiene_wr_rolling") or scorecard.get(
                    "rolling_winrate_500"
                )
                roll_f = float(roll_h) if roll_h is not None else None
                pack = skill_expectancy_for_pass(sc2, rolling_winrate=roll_f)
                if len(pack) >= 3 and pack[1]:
                    pass_exp, pass_src = float(pack[0]), str(pack[2])
                elif pack[1]:
                    pass_exp = float(pack[0])
            except Exception:
                pass
            scorecard["pass_expectancy"] = round(float(pass_exp), 4)
            scorecard["pass_wr_equiv"] = round(float(pass_exp) + 0.50, 4)
            scorecard["pass_expectancy_source"] = str(pass_src)
            # Keep expectancy_proxy aligned with pass leg for operator truth.
            scorecard["expectancy_proxy"] = round(float(pass_exp), 4)
            scorecard["expectancy_proxy_source"] = str(pass_src)
        except Exception:
            scorecard.setdefault("pass_vector_dominant", "none")
            scorecard.setdefault("pass_vector_action", "hold_pass_path")
            scorecard.setdefault("pass_vector_edge_gap", 0.0)
            scorecard.setdefault("pass_vector_exp_gap", 0.0)
        # P0–P1 peak capture / near-miss / restore telemetry (truthful, floors unchanged).
        try:
            peak_st = getattr(self, "stage2_peak_state", None)
            if peak_st is not None and hasattr(peak_st, "as_progress_fields"):
                scorecard.update(peak_st.as_progress_fields())
            else:
                scorecard.setdefault("stage2_peak_winrate", 0.0)
                scorecard.setdefault("stage2_near_miss_active", False)
                scorecard.setdefault("stage2_peak_restore_count", 0)
        except Exception:
            scorecard.setdefault("stage2_peak_winrate", 0.0)
            scorecard.setdefault("stage2_near_miss_active", False)
        # Engine cum is HUD SSOT (peak blob may omit time_stop / unknown / share).
        try:
            from lumina_core.birth.starship_edgescore_core import settlement_progress_fields

            scorecard.update(
                settlement_progress_fields(
                    closes_stop=int(getattr(self, "stage_closes_stop_cum", 0) or 0),
                    closes_target=int(getattr(self, "stage_closes_target_cum", 0) or 0),
                    closes_time_stop=int(
                        getattr(self, "stage_closes_time_stop_cum", 0) or 0
                    ),
                    closes_flatten=int(
                        getattr(self, "stage_closes_flatten_cum", 0) or 0
                    ),
                    closes_unknown=int(
                        getattr(self, "stage_closes_unknown_cum", 0) or 0
                    ),
                )
            )
        except Exception:
            logger.debug("birth.settlement_progress_fields_failed", exc_info=True)
        scorecard["expectancy_quality_step_source"] = str(
            getattr(self, "expectancy_quality_step_source", "") or ""
        )
        # Runtime identity — proves which binary wrote this progress row.
        try:
            from lumina_core.birth.runtime_diagnostics import (
                log_progress_write_trace,
                progress_diagnostic_fields,
            )

            scorecard.update(progress_diagnostic_fields())
            # Explicit last meta rationale from applied plan (not only bus history).
            plan = getattr(self, "meta_last_plan", None)
            if plan is not None and not scorecard.get("meta_last_rationale"):
                scorecard["meta_last_rationale"] = str(
                    getattr(plan, "rationale", "") or ""
                )
            log_progress_write_trace(
                phase=str(phase),
                curriculum_stage=str(getattr(self.stage, "value", self.stage)),
                stage_trades=int(current_stage_trades),
                scorecard=scorecard,
            )
        except Exception as exc:
            scorecard["birth_diag_contract"] = "diag_error"
            scorecard["birth_code_fingerprint"] = f"error:{type(exc).__name__}"
            scorecard["birth_runtime_pid"] = 0
        # Phase D: maturity / certificate readiness (honest absence, never hollow declare).
        try:
            from lumina_core.birth.foundation_metrics import FOUNDATION_STAGE_COUNT
            from lumina_core.birth.maturity_readiness import (
                certificate_path_ready,
                certificate_readiness_blockers,
                maturity_artifact_presence,
            )

            root = self.host.workspace_root
            arts = maturity_artifact_presence(root)
            scorecard.update(arts)
            stages_passed = list(getattr(self.host, "_stages_passed", None) or [])
            scorecard["curriculum_stages_passed_count"] = len(stages_passed)
            scorecard["certificate_path_ready"] = certificate_path_ready(
                stages_passed_count=len(stages_passed),
                plateau_active=bool(self.plateau_state.active),
                needs_attention=bool(scorecard.get("needs_attention")),
                curriculum_stages_required=FOUNDATION_STAGE_COUNT,
            )
            scorecard["certificate_readiness_blockers"] = certificate_readiness_blockers(
                stages_passed_count=len(stages_passed),
                plateau_active=bool(self.plateau_state.active),
                expectancy_stall=bool(scorecard.get("expectancy_stall_detected")),
                needs_attention=bool(scorecard.get("needs_attention")),
                certificate_present=bool(arts.get("certificate_present")),
                curriculum_stages_required=FOUNDATION_STAGE_COUNT,
            )
            try:
                from lumina_core.birth.perfect_birth_gate import perfect_birth_status

                pb = perfect_birth_status(root)
                scorecard["perfect_birth_would_pass"] = bool(pb.get("would_pass"))
                scorecard["perfect_birth_unlock_valid"] = bool(pb.get("unlock_valid"))
                scorecard["perfect_birth_failures"] = list(pb.get("failures") or [])[:12]
            except Exception:
                scorecard["perfect_birth_would_pass"] = False
                scorecard["perfect_birth_unlock_valid"] = False
                scorecard["perfect_birth_failures"] = ["status_unavailable"]
        except Exception:
            logger.debug("birth.maturity_readiness_fields_failed", exc_info=True)


__all__ = ["StageLoopProgressWriteEnrichMixin"]
