"""Rollout pre: hold caps + champion policy rollback (M5 extract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.foundation_occupancy_envelope import (
    foundation_envelope_controller_spec,
    foundation_occupancy_envelope_enabled,
)
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    detect_hold_trap,
    detect_over_trading_trap,
    detect_under_activity_trap,
    is_valid_best_policy_snapshot,
)
from lumina_core.birth.stage_loop_rollout_types import RolloutPreState
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


def _stage2_exp_floor(loop: Any) -> float:
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        return float(stage2_expectancy_floor(loop.cur_cfg))
    except Exception:
        return float(getattr(loop.cur_cfg, "stage2_expectancy_floor", -0.15) or -0.15)


def _stage1_foundation_gap(loop: Any) -> float:
    """Stage-1 learning pressure toward foundation target (not survival pass floor)."""
    try:
        from lumina_core.birth.curriculum import CurriculumStage
        from lumina_core.birth.stage1_foundation import stage1_foundation_learning_gap

        if getattr(loop, "stage", None) != CurriculumStage.STAGE1_TREND:
            return 0.0
        rolling = None
        try:
            rolling, _, _ = loop._rolling_winrate_meta()  # type: ignore[attr-defined]
        except Exception:
            rolling = None
        edge = getattr(loop, "_edge_vs_random", None)
        try:
            edge_f = float(edge) if edge is not None else None
        except (TypeError, ValueError):
            edge_f = None
        return float(
            stage1_foundation_learning_gap(
                stage_trades=int(getattr(loop, "stage_trades", 0) or 0),
                stage_wins=int(getattr(loop, "stage_wins", 0) or 0),
                required=int(getattr(loop, "required", 200) or 200),
                cfg=getattr(loop, "cur_cfg", None),
                rolling_winrate=float(rolling) if rolling is not None else None,
                edge_vs_random=edge_f,
            )
        )
    except Exception:
        return 0.0


def _stage2_expectancy_gap(loop: Any) -> float:
    """max(0, floor − live skill expectancy) + economic pressure when BE-WR high.

    Floor never moves. Economic pressure trains harder wins when plant BE-WR
    exceeds the proxy-relevant target — honest dual objective.
    """
    trades = int(getattr(loop, "stage_trades", 0) or 0)
    wins = int(getattr(loop, "stage_wins", 0) or 0)
    if trades <= 0:
        return 0.0
    floor = _stage2_exp_floor(loop)
    # Prefer pilot skill counts when present.
    try:
        from lumina_core.birth.stage2_skill_metric import resolve_stage2_skill_counts

        sc = resolve_stage2_skill_counts(
            total_trades=trades,
            total_wins=wins,
            policy_trades=int(getattr(loop, "stage_policy_trades", 0) or 0),
            policy_wins=int(getattr(loop, "stage_policy_wins", 0) or 0),
            plant_trades=int(getattr(loop, "stage_plant_trades", 0) or 0),
            plant_wins=int(getattr(loop, "stage_plant_wins", 0) or 0),
            skill_only=bool(
                getattr(loop.cur_cfg, "stage2_skill_metric_policy_only", True)
            ),
            required=int(getattr(loop, "required", 300) or 300),
            skill_min_trades=getattr(loop.cur_cfg, "stage2_skill_min_trades", None),
        )
        live = float(sc.skill_expectancy)
        skill_wr = float(sc.skill_winrate)
    except Exception:
        lifetime = float(wins) / float(max(1, trades))
        live = lifetime - 0.50
        skill_wr = lifetime
    try:
        from lumina_core.birth.plateau_rolling import rolling_winrate_last_n_trades
        from lumina_core.birth.starship_edgescore_core import gate_rolling_winrate

        from lumina_core.birth.plateau_rolling import stage_rolling_pass_window

        window = stage_rolling_pass_window(
            getattr(loop, "cur_cfg", None), getattr(loop, "stage", None)
        )
        chunks = getattr(loop, "rolling_trade_chunks", None)
        wins_at = getattr(loop, "wins_at_trade_milestones", None) or {}
        if not isinstance(wins_at, dict):
            wins_at = {}
        meta = rolling_winrate_last_n_trades(
            stage_trades=trades,
            stage_wins=wins,
            wins_at_trade=wins_at,
            window=window,
            chunks=chunks if isinstance(chunks, list) else None,
            return_meta=True,
        )
        if isinstance(meta, tuple) and len(meta) >= 3:
            wr = gate_rolling_winrate(
                rolling_wr=float(meta[0]),
                source=str(meta[1]),
                covered=int(meta[2]),
                window=window,
            )
            if wr is not None:
                live = max(live, float(wr) - 0.50)
                skill_wr = max(skill_wr, float(wr))
    except Exception:
        pass
    gap = max(0.0, float(floor) - float(live))
    # Economic honesty: when break-even WR after cost >> skill WR, add pressure.
    try:
        from lumina_core.birth.birth_trade_geometry import economic_skill_gap

        geo = getattr(loop, "_birth_trade_geometry", None)
        be = float(getattr(geo, "breakeven_wr_after_cost", 0.0) or 0.0)
        if be > 0:
            econ_gap = economic_skill_gap(be_wr=be, skill_wr=skill_wr)
            # Cap so economic term cannot drown skill gap signal.
            gap = max(gap, min(0.25, 0.5 * econ_gap + gap))
    except Exception:
        pass
    return float(gap)


class StageLoopRolloutPreCapsMixin:
    def _finish_rollout_pre_caps(
        self,
        *,
        explore_steps: int,
        reward_override: Any,
        progress_cb: Callable[..., None],
    ) -> RolloutPreState:
        pre_rollout_hold = (
            float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
            if self.stage_total_signals
            else 0.0
        )
        pre_rollout_flat = (
            float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals))
            if self.stage_range_total_signals
            else 0.0
        )
        if self.swarm_state.active:
            swarm_reward, swarm_explore_mult = self._apply_swarm_variant_for_rollout()
            if swarm_reward is not None:
                reward_override = swarm_reward
            explore_steps = max(200, int(explore_steps * swarm_explore_mult))
        plateau_recovery = self.plateau_state.active or self.remediation_state.active
        hold_cap: float | None = None
        position_flat_cap: float | None = None
        position_flat_floor: float | None = None
        is_s2 = self.stage == CurriculumStage.STAGE2_RANGE
        is_s3 = self.stage == CurriculumStage.STAGE3_MIXED
        # Airframe: occupancy envelope for every foundation stage that grades it (S2–S5).
        participation_envelope_enabled = foundation_occupancy_envelope_enabled(
            self.stage, self.cur_cfg
        )
        # sim_runner ANDs envelope with range_patience_active — S4/S5 must not skip.
        range_patience_active = bool(participation_envelope_enabled)
        # Occupancy envelope is airframe (FORCE_FLAT/OPEN). Quality lock may freeze
        # PPO and block explore_boost; it must never disable the envelope.
        # In-band PASSTHROUGH is already decide_stage2_participation's nominal law.
        velocity_stalled = self.low_velocity_attempts >= int(self.cur_cfg.velocity_stall_attempt_threshold)
        if plateau_recovery or detect_hold_trap(
            hold_ratio=pre_rollout_hold,
            winrate=float(self.stage_wins) / float(max(1, self.stage_trades)),
            pass_metric_target=self.pass_metric_target,
            velocity_stall=velocity_stalled,
            cfg=self.cur_cfg,
            range_flat_ratio=pre_rollout_flat,
        ):
            hold_cap = float(self.cur_cfg.hold_trap_recovery_hold_cap)
        # Stage-3 uses same position-flat SSOT when range flat bars are tracked.
        if is_s3 and int(getattr(self, "stage_range_total_signals", 0) or 0) < 50:
            # Fallback: treat low hold as not empty — estimate flat from hold complement.
            # Prefer real range flat once warm; this only covers cold start.
            pre_rollout_flat = max(
                float(pre_rollout_flat),
                max(0.0, 1.0 - float(pre_rollout_hold)),
            )
        if (is_s2 or is_s3) and detect_over_trading_trap(
            range_flat_ratio=pre_rollout_flat,
            range_round_trips=self.stage_range_round_trips,
            required=self.required,
            velocity_stall=velocity_stalled,
            cfg=self.cur_cfg,
        ):
            position_flat_cap = float(self.cur_cfg.over_trading_recovery_flat_target)
            range_patience_active = True
            try:
                self.over_trading_detected = True
            except Exception:
                pass
        else:
            try:
                if is_s2 or is_s3:
                    self.over_trading_detected = False
            except Exception:
                pass
        under_activity = (is_s2 or is_s3) and detect_under_activity_trap(
            range_flat_ratio=pre_rollout_flat,
            range_total_signals=self.stage_range_total_signals,
            stage_trades=self.stage_trades,
            required=self.required,
            velocity_stall=velocity_stalled,
            cfg=self.cur_cfg,
        )
        if under_activity:
            # Participation pressure: floor forces non-flat exploration; boost explore budget.
            position_flat_floor = float(self.cur_cfg.under_activity_recovery_flat_floor)
            explore_mult = float(getattr(self.cur_cfg, "under_activity_explore_multiplier", 2.0) or 2.0)
            explore_steps = max(200, int(explore_steps * max(1.0, explore_mult)))
            hold_cap = min(
                float(hold_cap) if hold_cap is not None else 1.0,
                float(self.cur_cfg.hold_trap_recovery_hold_cap),
            )
            range_patience_active = True
            logger.info(
                "birth.under_activity_recovery flat=%.1f%% floor=%.0f%% explore_steps=%s",
                pre_rollout_flat * 100.0,
                float(position_flat_floor) * 100.0,
                explore_steps,
            )
        # Expectancy stall + chronic HOLD: tighten hold cap so policy must take
        # decisive trades (truthful learning; does not lower WR floors).
        try:
            from lumina_core.birth.expectancy_stall import loop_expectancy_stall

            exp_stall = bool(
                loop_expectancy_stall(self)
                if callable(loop_expectancy_stall)
                else False
            )
        except Exception:
            exp_stall = bool(getattr(self, "expectancy_stall_detected", False))
        if (
            (is_s2 or is_s3)
            and exp_stall
            and pre_rollout_hold > 0.65
            and int(getattr(self, "stage_total_signals", 0) or 0) >= 50
        ):
            trap_cap = float(getattr(self.cur_cfg, "hold_trap_recovery_hold_cap", 0.55) or 0.55)
            hold_cap = min(float(hold_cap) if hold_cap is not None else 1.0, trap_cap, 0.55)
            logger.info(
                "birth.expectancy.hold_pressure hold=%.1f%% hold_cap=%.2f (stall + over-hold)",
                pre_rollout_hold * 100.0,
                float(hold_cap),
            )
        # Stage-3 hygiene gap: also pressure hold when WR≪35% and chronically holding.
        if is_s3 and int(self.stage_trades) >= max(50, int(self.required) // 4):
            life_wr = float(self.stage_wins) / float(max(1, self.stage_trades))
            s3_floor = float(getattr(self.cur_cfg, "stage3_winrate_floor", 0.35) or 0.35)
            if life_wr + 1e-12 < s3_floor and pre_rollout_hold > 0.55:
                trap_cap = float(
                    getattr(self.cur_cfg, "hold_trap_recovery_hold_cap", 0.55) or 0.55
                )
                hold_cap = min(
                    float(hold_cap) if hold_cap is not None else 1.0, trap_cap, 0.55
                )
        edge_champ_path = str(getattr(self, "best_edgescore_policy_path", "") or "").strip()
        plateau_champ_ok = bool(self.plateau_state.best_policy_path) and is_valid_best_policy_snapshot(
            self.plateau_state, cfg=self.cur_cfg
        )
        edge_champ_ok = bool(edge_champ_path) and Path(edge_champ_path).is_file()
        cooldown_ok = self.attempt - self.last_policy_rollback_attempt >= int(
            self.cur_cfg.policy_rollback_cooldown_rollouts
        )
        if (plateau_champ_ok or edge_champ_ok) and cooldown_ok:
            live_wr = float(self.stage_wins) / float(max(1, self.stage_trades))
            rollback_wr_gap = live_wr + float(self.cur_cfg.policy_rollback_winrate_gap) < (
                self.plateau_state.best_winrate
            )
            # Starship champion freeze: EdgeScore drop triggers rollback only for
            # eligible (min-trades) champions — never early noise.
            from lumina_core.birth.starship_birth import is_edgescore_champion_eligible

            champion_freeze = bool(
                getattr(self.cur_cfg, "starship_champion_freeze_enabled", True)
            ) and not bool(self.allow_provisional)
            live_edge = 0.0
            best_edge = float(getattr(self, "best_edgescore", 0.0) or 0.0)
            edge_gap = float(getattr(self.cur_cfg, "starship_champion_edgescore_gap", 0.02))
            rollback_edge_gap = False
            champ_eligible = is_edgescore_champion_eligible(
                stage_trades=int(getattr(self, "best_edgescore_at_trade", 0) or 0),
                required=int(self.required),
                cfg=self.cur_cfg,
            )
            if champion_freeze and best_edge > 0.0 and champ_eligible:
                try:
                    live_edge = float(self._current_edgescore())
                    rollback_edge_gap = live_edge + edge_gap < best_edge
                except Exception:
                    rollback_edge_gap = False
            should_rollback = (
                rollback_edge_gap
                or (
                    rollback_wr_gap
                    and plateau_champ_ok
                    and (
                        self.strong_recovery_mode
                        or champion_freeze
                        or (
                            self.stage == CurriculumStage.STAGE3_MIXED
                            and self.stage_trades < self.required
                            and pre_rollout_hold > 0.75
                        )
                    )
                )
            )
            if should_rollback:
                detail, applied = "", False
                if plateau_champ_ok:
                    detail, applied = self._apply_plateau_evolution_action(
                        EvolutionAction.POLICY_ROLLBACK
                    )
                if (
                    champion_freeze
                    and edge_champ_ok
                    and rollback_edge_gap
                ):
                    self.host.current_policy = self.host._create_birth_policy(
                        allow_load_existing=True,
                        policy_path=edge_champ_path,
                    )
                    applied = True
                    detail = f"{detail}; champion_freeze edgescore".lstrip("; ").strip()
                if applied:
                    self.last_policy_rollback_attempt = self.attempt
                logger.info(
                    "birth.policy_rollback_auto_applied detail=%s applied=%s live_wr=%.2f%% "
                    "best=%.2f%% live_edge=%.3f best_edge=%.3f stage=%s hold_ratio=%.1f%%",
                    detail,
                    applied,
                    live_wr * 100.0,
                    self.plateau_state.best_winrate * 100.0,
                    live_edge,
                    best_edge,
                    self.stage.value,
                    pre_rollout_hold * 100.0,
                )
        # S2 controller stays S2. S3/S4/S5 share the S3 controller (not exam floors).
        spec = foundation_envelope_controller_spec(self.stage, self.cur_cfg)
        return RolloutPreState(
            explore_steps=explore_steps,
            reward_override=reward_override,
            hold_cap=hold_cap,
            position_flat_cap=position_flat_cap,
            position_flat_floor=position_flat_floor,
            range_patience_active=range_patience_active,
            plateau_recovery=plateau_recovery,
            progress_cb=progress_cb,
            participation_envelope_enabled=participation_envelope_enabled,
            participation_min_signals=int(
                getattr(self.cur_cfg, spec.min_signals_attr, 50) or 50
            ),
            participation_min_dwell_bars=int(
                getattr(self.cur_cfg, spec.min_dwell_attr, 8) or 8
            ),
            participation_band_lo=spec.band_lo,
            participation_band_hi=spec.band_hi,
            participation_hysteresis=spec.hysteresis,
            participation_under_band_release_hysteresis=spec.release_hysteresis,
            occupancy_control_window_bars=int(
                getattr(self.cur_cfg, spec.window_attr, 500) or 500
            ),
            participation_stop_pct=float(
                getattr(self, "_birth_trade_stop_pct", None)
                or getattr(self.cur_cfg, "stage2_participation_force_open_stop_pct", 0.0012)
                or 0.0012
            ),
            participation_target_pct=float(
                getattr(self, "_birth_trade_target_pct", None)
                or getattr(self.cur_cfg, "stage2_participation_force_open_target_pct", 0.0020)
                or 0.0020
            ),
            participation_qty_frac=float(
                getattr(self.cur_cfg, "stage2_participation_force_open_qty_frac", 0.15)
                or 0.15
            ),
            stage_range_flat_bars=int(getattr(self, "stage_range_flat_bars", 0) or 0),
            stage_range_total_signals=int(
                getattr(self, "stage_range_total_signals", 0) or 0
            ),
            expectancy_gap=max(
                _stage2_expectancy_gap(self),
                _stage1_foundation_gap(self),
            ),
            stage2_expectancy_floor=_stage2_exp_floor(self),
        )

