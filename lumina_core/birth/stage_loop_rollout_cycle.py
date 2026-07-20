"""Single-rollout cycle: pre-meta, sim rollout, post-update (thin orchestrator)."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    is_runway_stage,
    update_stage1_intra_state,
    update_stage2_intra_state,
)
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.birth.stage_loop_rollout_post import StageLoopRolloutPostMixin
from lumina_core.birth.stage_loop_rollout_pre import StageLoopRolloutPreMixin, RolloutPreState
from lumina_core.birth.stage_loop_rollout_tail import StageLoopRolloutTailMixin
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_rollout_cycle")


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
        rollout_started_at = time.time()
        rollout = run_policy_rollout(
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
            range_patience_active=pre.range_patience_active,
            plateau_active=pre.plateau_recovery,
            on_progress=pre.progress_cb,
            reward_override=pre.reward_override,
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
        self.host.cumulative_trades += rollout.trades
        self._maybe_run_oos_proxy()
        self._maybe_record_and_advance_swarm(
            trades=rollout.trades,
            wins=rollout.wins,
            total_pnl=float(rollout.total_pnl),
        )
        if is_runway_stage(self.stage):
            self.stage_val_pnl.extend(rollout.pnl_series)

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
                )

        current_hold_ratio = float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
        range_flat_ratio = float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals))
        if self.stage == CurriculumStage.STAGE2_RANGE and rollout.range_total_signals > 0:
            rollout_flat = float(rollout.range_flat_bars) / float(max(1, rollout.range_total_signals))
            flat_delta = range_flat_ratio - self.last_range_flat_ratio
            logger.info(
                "birth.stage2.rollout_metrics rollout_flat=%.4f stage_flat=%.4f delta=%+.4f "
                "round_trips=%s trades=%s",
                rollout_flat,
                range_flat_ratio,
                flat_delta,
                rollout.range_round_trips,
                rollout.trades,
            )
            self.last_range_flat_ratio = range_flat_ratio
        if rollout.trades > 0:
            self.wins_at_trade_milestones[self.stage_trades] = self.stage_wins
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
