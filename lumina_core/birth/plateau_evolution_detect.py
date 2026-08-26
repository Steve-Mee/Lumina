"""Plateau enter detection + terminal pending (M5 extract from loop)."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    PlateauEnterContext,
    is_plateau_quarantine_blocking,
    sanitize_plateau_best_snapshot,
    should_terminal_plateau_stall,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.birth.stage_scorecard import calculate_simple_slope, compute_stage_blocker
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class PlateauEvolutionDetectMixin(StageLoopMixinBase):
    """Detect plateau entry and build terminal stall pending payloads."""

    def _stage_failure_key(self) -> str:
        return {
            CurriculumStage.STAGE1_TREND: "stage1_winrate",
            CurriculumStage.STAGE2_RANGE: "stage2_metric",
            CurriculumStage.STAGE3_MIXED: "stage3_foundation",
        }.get(self.stage, "stage_metrics")

    def _maybe_detect_plateau(self, *, stage_trades: int, stage_wins: int) -> None:
        del stage_trades, stage_wins  # use live self.* counters
        if self.plateau_state.active or self.allow_provisional:
            return
        ctx = PlateauEnterContext(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            required=self.required,
            winrate_trend_slope=calculate_simple_slope(self.winrate_history),
            velocity_stall_attempts=self.low_velocity_attempts,
            meta_self_eval_phase=self._meta_self_eval_phase_str(),
            pass_metric_target=self.pass_metric_target,
            plateau_quarantine_active=is_plateau_quarantine_blocking(
                quarantine_rollouts_remaining=int(
                    self.plateau_quarantine.get("plateau_quarantine_rollouts_remaining", 0) or 0
                ),
                quarantine_trades_at_resume=int(
                    self.plateau_quarantine.get("plateau_quarantine_trades_at_resume", 0) or 0
                ),
                stage_trades=self.stage_trades,
                quarantine_min_trades=int(
                    self.plateau_quarantine.get("plateau_quarantine_trades_remaining", 0)
                    or self.cur_cfg.plateau_quarantine_min_trades
                ),
            ),
            stage=self.stage,
        )
        meta_health = str(getattr(self, "meta_learning_health", "") or "")
        if not meta_health and self.cur_cfg.meta_controller_enabled:
            try:
                snap = getattr(self, "meta_last_plan", None)
                if snap is not None and getattr(snap, "snapshot", None) is not None:
                    meta_health = str(
                        getattr(snap.snapshot.learning_health, "value", "")
                        or snap.snapshot.learning_health
                        or ""
                    )
            except Exception:
                meta_health = ""
        winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        hygiene = float(getattr(self.cur_cfg, "stage1_winrate_pass_floor", 0.35) or 0.35)
        if self.stage == CurriculumStage.STAGE3_MIXED:
            hygiene = float(getattr(self.cur_cfg, "stage3_winrate_floor", 0.35) or 0.35)
        flat_ratio = float(self.stage_range_flat_bars) / float(
            max(1, self.stage_range_total_signals)
        )
        skill_failing = winrate + 1e-9 < hygiene
        # Stage2 EdgeScore: flat-band outside 30–70% is a first-class skill fail.
        if self.stage == CurriculumStage.STAGE2_RANGE and self.stage_range_total_signals >= 50:
            if flat_ratio < 0.30 - 1e-12 or flat_ratio > 0.70 + 1e-12:
                skill_failing = True
        if self.bus.plateau_check_enter(
            self.stage,
            stage_trades=ctx.stage_trades,
            stage_wins=ctx.stage_wins,
            required=ctx.required,
            winrate_trend_slope=ctx.winrate_trend_slope,
            velocity_stall_attempts=ctx.velocity_stall_attempts,
            meta_self_eval_phase=ctx.meta_self_eval_phase,
            pass_metric_target=ctx.pass_metric_target,
            plateau_quarantine_active=ctx.plateau_quarantine_active,
            wall_budget_exhausted=bool(getattr(self, "wall_budget_exhausted", False)),
            meta_learning_health=meta_health,
            skill_failing=skill_failing,
            range_flat_ratio=flat_ratio,
            range_round_trips=self.stage_range_round_trips,
            velocity_stall=self.low_velocity_attempts > 0,
        ):
            self.bus.plateau_enter(
                self.stage, stage_trades=self.stage_trades, stage_wins=self.stage_wins
            )
            self.ppo_steps_at_plateau_evolution_step = int(self.host.ppo_steps)
            sanitize_plateau_best_snapshot(
                self.plateau_state,
                cfg=self.cur_cfg,
                stage_trades=self.stage_trades,
                stage_wins=self.stage_wins,
            )
            wr = float(self.stage_wins) / float(max(1, self.stage_trades))
            try:
                from lumina_core.birth.foundation_stages import is_foundation_stage
                from lumina_core.notifications.milestone_events import plateau_entered_event

                if is_foundation_stage(self.stage):
                    self.host._notify_milestone(
                        plateau_entered_event(
                            stage_trades=self.stage_trades,
                            winrate=wr,
                            pass_target=None,
                            pass_label=(
                                "process-R ≤ 1.5R · net RR ≥ 0.80 · settlement ≥70% "
                                "(WR is not a pass gate)"
                            ),
                        )
                    )
                else:
                    self.host._notify_milestone(
                        plateau_entered_event(
                            stage_trades=self.stage_trades,
                            winrate=wr,
                            pass_target=self.pass_metric_target,
                        )
                    )
            except Exception as exc:
                logger.debug("birth.milestone_plateau_enter_failed: %s", exc)
            # Stage2 flat-band survival before swarm theater (post-mortem 2026-08-07).
            flat_ratio = float(self.stage_range_flat_bars) / float(
                max(1, self.stage_range_total_signals)
            )
            defer_swarm = False
            defer_reason = ""
            if self.stage == CurriculumStage.STAGE2_RANGE:
                from lumina_core.birth.plateau_escalator import (
                    stage2_should_defer_swarm_for_flat_band,
                )
                from lumina_core.birth.expectancy_stall import (
                    detect_expectancy_stall,
                    stage2_should_defer_swarm_for_expectancy,
                )

                defer_swarm = stage2_should_defer_swarm_for_flat_band(
                    range_flat_ratio=flat_ratio,
                    range_total_signals=self.stage_range_total_signals,
                    stage_trades=self.stage_trades,
                    required=self.required,
                    evolution_step=int(getattr(self.plateau_state, "evolution_step", 0) or 0),
                    cfg=self.cur_cfg,
                )
                if defer_swarm:
                    defer_reason = "flat_band"
                else:
                    exp_stall = detect_expectancy_stall(
                        stage_is_range=True,
                        range_flat_ratio=flat_ratio,
                        range_total_signals=self.stage_range_total_signals,
                        stage_trades=self.stage_trades,
                        stage_wins=self.stage_wins,
                        required=self.required,
                        velocity_stall=self.low_velocity_attempts
                        >= int(self.cur_cfg.velocity_stall_attempt_threshold),
                        plateau_active=bool(self.plateau_state.active),
                        trades_beyond_gate=max(0, int(self.stage_trades) - int(self.required)),
                        cfg=self.cur_cfg,
                    )
                    quality_step = int(getattr(self, "expectancy_quality_step", 0) or 0)
                    edge_vr = getattr(self, "_edge_vs_random", None)
                    try:
                        edge_vr_f = float(edge_vr) if edge_vr is not None else None
                    except (TypeError, ValueError):
                        edge_vr_f = None
                    if stage2_should_defer_swarm_for_expectancy(
                        expectancy_stall=exp_stall,
                        remediation_step=quality_step,
                        evolution_step=int(
                            getattr(self.plateau_state, "evolution_step", 0) or 0
                        ),
                        cfg=self.cur_cfg,
                        edge_vs_random=edge_vr_f,
                    ):
                        defer_swarm = True
                        defer_reason = (
                            "beat_random"
                            if edge_vr_f is not None and edge_vr_f < -1e-12
                            else "expectancy_quality"
                        )
                        # Do not advance quality ladder step here — only meta_apply
                        # owns step progression (avoids step/history desync).
                    # P0–P1: near-miss / peak protect — never burn a 34% peak with swarm.
                    if not defer_swarm:
                        try:
                            from lumina_core.birth.stage2_peak_capture import (
                                should_defer_swarm_for_peak,
                            )

                            peak_st = getattr(self, "stage2_peak_state", None)
                            if peak_st is not None:
                                max_q = int(
                                    getattr(
                                        self.cur_cfg,
                                        "stage2_expectancy_quality_max_steps",
                                        4,
                                    )
                                    or 4
                                )
                                d2, r2 = should_defer_swarm_for_peak(
                                    peak_st,
                                    edge_vs_random=edge_vr_f,
                                    quality_step=quality_step,
                                    max_quality_steps=max_q,
                                    best_winrate=float(
                                        getattr(self.plateau_state, "best_winrate", 0.0)
                                        or peak_st.peak_winrate
                                        or 0.0
                                    ),
                                    cfg=self.cur_cfg,
                                )
                                if d2:
                                    defer_swarm = True
                                    defer_reason = r2 or "peak_protect"
                                    peak_st.swarm_blocked_reason = defer_reason
                        except Exception:
                            pass
            if defer_swarm:
                logger.info(
                    "birth.stage2.defer_swarm reason=%s flat=%.1f%% trades=%s step=%s",
                    defer_reason or "unknown",
                    flat_ratio * 100.0,
                    self.stage_trades,
                    int(getattr(self.plateau_state, "evolution_step", 0) or 0),
                )
                self._try_plateau_evolution(failure_key=self._stage_failure_key())
            else:
                # Starship A3: swarm tournament first; ladder waits until swarm idle.
                self._start_policy_swarm(force=False)
                if not bool(self.swarm_state.active):
                    self._try_plateau_evolution(failure_key=self._stage_failure_key())

    def _plateau_terminal_pending(self, *, failure_key: str) -> dict[str, Any] | None:
        if not should_terminal_plateau_stall(
            self.plateau_state,
            stage_trades=self.stage_trades,
            required=self.required,
            cfg=self.cur_cfg,
            meta_self_eval_phase=self._meta_self_eval_phase_str(),
            remediation_exhausted=self._remediation_exhausted_now(),
            trade_budget_remaining=self._trade_budget_remaining(),
            max_steps=self._evolution_max_steps(),
            stage=self.stage,
        ):
            return None
        hold_ratio = float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
        range_flat_ratio = float(self.stage_range_flat_bars) / float(
            max(1, self.stage_range_total_signals)
        )
        blocker_metric, blocker_value, blocker_reason = compute_stage_blocker(
            self.stage,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            hold_ratio=hold_ratio,
            required=self.required,
            constitution_violations=self.host._constitution_guard.violations,
            range_flat_ratio=range_flat_ratio,
            range_round_trips=self.stage_range_round_trips,
            range_total_signals=self.stage_range_total_signals,
            cfg=self.cur_cfg,
            policy_entropy=self._resolve_policy_entropy(),
            ppo_steps=int(getattr(self.host, "ppo_steps", 0) or 0),
            policy_trades=int(getattr(self, "stage_policy_trades", 0) or 0),
            policy_wins=int(getattr(self, "stage_policy_wins", 0) or 0),
            plant_trades=int(getattr(self, "stage_plant_trades", 0) or 0),
            plant_wins=int(getattr(self, "stage_plant_wins", 0) or 0),
        )
        if not blocker_metric:
            blocker_metric = "plateau_evolution_exhausted"
            blocker_value = float(self.plateau_state.evolution_step)
            blocker_reason = TERMINAL_STALL_REASON
        return {
            "failure_key": failure_key,
            "blocker_metric": blocker_metric,
            "blocker_value": blocker_value if blocker_value is not None else 0.0,
            "blocker_reason": blocker_reason or TERMINAL_STALL_REASON,
            "terminal_stall_reason": TERMINAL_STALL_REASON,
        }


__all__ = ["PlateauEvolutionDetectMixin"]
