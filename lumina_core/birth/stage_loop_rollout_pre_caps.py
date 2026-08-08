"""Rollout pre: hold caps + champion policy rollback (M5 extract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from lumina_core.birth.curriculum import CurriculumStage
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


def _stage2_expectancy_gap(loop: Any) -> float:
    """max(0, floor − live expectancy) for quality reward seed."""
    trades = int(getattr(loop, "stage_trades", 0) or 0)
    wins = int(getattr(loop, "stage_wins", 0) or 0)
    if trades <= 0:
        return 0.0
    floor = _stage2_exp_floor(loop)
    lifetime = float(wins) / float(max(1, trades))
    live = lifetime - 0.50
    try:
        from lumina_core.birth.plateau_rolling import rolling_winrate_last_n_trades
        from lumina_core.birth.starship_edgescore_core import gate_rolling_winrate

        window = int(getattr(loop.cur_cfg, "stage1_rolling_pass_window", 500) or 500)
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
    except Exception:
        pass
    return max(0.0, float(floor) - float(live))


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
        range_patience_active = self.stage == CurriculumStage.STAGE2_RANGE
        # Stage2 Participation Envelope: always on for range curriculum (hard occupancy).
        participation_envelope_enabled = bool(
            self.stage == CurriculumStage.STAGE2_RANGE
            and getattr(self.cur_cfg, "stage2_participation_envelope_enabled", True)
        )
        velocity_stalled = self.low_velocity_attempts >= int(self.cur_cfg.velocity_stall_attempt_threshold)
        if plateau_recovery or detect_hold_trap(
            hold_ratio=pre_rollout_hold,
            winrate=float(self.stage_wins) / float(max(1, self.stage_trades)),
            pass_metric_target=self.pass_metric_target,
            velocity_stall=velocity_stalled,
            cfg=self.cur_cfg,
        ):
            hold_cap = float(self.cur_cfg.hold_trap_recovery_hold_cap)
        if self.stage == CurriculumStage.STAGE2_RANGE and detect_over_trading_trap(
            range_flat_ratio=pre_rollout_flat,
            range_round_trips=self.stage_range_round_trips,
            required=self.required,
            velocity_stall=velocity_stalled,
            cfg=self.cur_cfg,
        ):
            position_flat_cap = float(self.cur_cfg.over_trading_recovery_flat_target)
            range_patience_active = True
        under_activity = self.stage == CurriculumStage.STAGE2_RANGE and detect_under_activity_trap(
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
                getattr(self.cur_cfg, "stage2_participation_min_signals", 50) or 50
            ),
            participation_min_dwell_bars=int(
                getattr(self.cur_cfg, "stage2_participation_min_dwell_bars", 8) or 8
            ),
            participation_band_lo=float(
                getattr(self.cur_cfg, "stage2_participation_band_lo", 0.30) or 0.30
            ),
            participation_band_hi=float(
                getattr(self.cur_cfg, "stage2_participation_band_hi", 0.70) or 0.70
            ),
            participation_hysteresis=float(
                getattr(self.cur_cfg, "stage2_participation_hysteresis", 0.02) or 0.02
            ),
            participation_stop_pct=float(
                getattr(self.cur_cfg, "stage2_participation_force_open_stop_pct", 0.0075)
                or 0.0075
            ),
            participation_target_pct=float(
                getattr(self.cur_cfg, "stage2_participation_force_open_target_pct", 0.015)
                or 0.015
            ),
            participation_qty_frac=float(
                getattr(self.cur_cfg, "stage2_participation_force_open_qty_frac", 0.15)
                or 0.15
            ),
            stage_range_flat_bars=int(getattr(self, "stage_range_flat_bars", 0) or 0),
            stage_range_total_signals=int(
                getattr(self, "stage_range_total_signals", 0) or 0
            ),
            expectancy_gap=_stage2_expectancy_gap(self),
            stage2_expectancy_floor=_stage2_exp_floor(self),
        )

