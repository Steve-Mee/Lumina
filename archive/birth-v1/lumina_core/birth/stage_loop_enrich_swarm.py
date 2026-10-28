"""stage_loop_enrich_swarm — extracted from stage_loop_data_enrich.py."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_bus_serde import reward_config_to_dict
from lumina_core.birth.birth_control_plane import (
    swarm_tournament_lift,
    tournament_score,
)
from lumina_core.birth.policy_swarm import (
    PolicySwarmState,
    build_swarm_variants,
    record_swarm_rollout,
    select_swarm_winner,
    swarm_rollout_target,
)
from lumina_core.birth.starship_birth import (
    edgescore_from_swarm_result,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_data_enrich")


class StageLoopEnrichSwarmMixin:
    """Methods: _maybe_record_and_advance_swarm, _start_policy_swarm."""

    def _start_policy_swarm(self, *, force: bool = False) -> None:
        if (
            not self.cur_cfg.policy_swarm_enabled
            or self.allow_provisional
            or self.swarm_state.active
            or (
                (
                    self.swarm_state.committed_variant_id
                    or self.swarm_state.rejected_no_lift
                    or self.swarm_state.champion_accepted
                )
                and not force
            )
        ):
            return
        # Snapshot champion BEFORE force_reinit destroys weights.
        swarm_dir = self.host.workspace_root / "lumina_agents" / "ppo"
        swarm_dir.mkdir(parents=True, exist_ok=True)
        pre_path = swarm_dir / f"preswarm_{self.stage.value}.zip"
        save_fn = getattr(self.host.ppo_trainer, "save_final_birth_policy", None)
        if callable(save_fn):
            try:
                save_fn(str(pre_path))
            except Exception as exc:
                logger.debug("birth.policy_swarm.preswarm_save_failed: %s", exc)
        best = str(
            getattr(self, "best_edgescore_policy_path", "")
            or getattr(self.plateau_state, "best_policy_path", "")
            or ""
        ).strip()
        pre_swarm_path = str(pre_path) if pre_path.is_file() else best

        if force:
            self.swarm_state = PolicySwarmState()
        # Baseline set after equal-window champion probe (not lifetime stage stats).
        self.swarm_tournament_at_start = -1.0
        self.swarm_edgescore_at_start = -1.0  # legacy alias
        self.swarm_rejected_no_lift = False
        self.swarm_tournament_lift_ok = False
        self.swarm_edgescore_lift_ok = False  # legacy alias
        self.swarm_champion_accepted = False
        baseline = (
            self.bus.meta_controller.active_reward
            if self.cur_cfg.meta_controller_enabled
            else self.host.birth_config.reward
        )
        variants = build_swarm_variants(baseline, cfg=self.cur_cfg)
        materialized = []
        for index, variant in enumerate(variants):
            self.host.current_policy = self.host._create_birth_policy(
                allow_load_existing=False,
                force_reinit=True,
            )
            path = swarm_dir / f"swarm_{self.stage.value}_{index}_{variant.variant_id}.zip"
            if callable(save_fn):
                save_fn(str(path))
            materialized.append(replace(variant, policy_path=str(path)))
        # Restore champion for equal-window probe before any variant rollouts.
        if pre_swarm_path and Path(pre_swarm_path).is_file():
            self.host.current_policy = self.host._create_birth_policy(
                allow_load_existing=True,
                policy_path=pre_swarm_path,
            )
        # Freeze identical tick windows once — probe + all variants replay the same slices.
        window_count = swarm_rollout_target(self.cur_cfg)
        chunk_target = max(1, int(self.cur_cfg.rollout_chunk_trades))
        swarm_seed = 17_000 + int(self.attempt) * 31 + len(materialized) * 7
        frozen_windows: list[list[dict[str, Any]]] = []
        for win_i in range(window_count):
            frozen_windows.append(
                list(
                    self.host._stage_tick_pool(
                        stage=self.stage,
                        stage_ticks=self.active_stage_ticks,
                        train_ticks=self.active_train,
                        escalation_level=self.escalation_level,
                        attempt=swarm_seed + win_i,
                        chunk_target=chunk_target,
                        cur_cfg=self.cur_cfg,
                        intra_state=self.intra_state,
                        easy_pool=self.intra_easy_pool,
                        hard_pool=self.intra_hard_pool,
                        intra_s2_state=self.intra_s2_state,
                        s2_easy_pool=self.intra_s2_easy_pool,
                        s2_hard_pool=self.intra_s2_hard_pool,
                    )
                )
            )
        self.swarm_state = PolicySwarmState(
            active=True,
            variants=materialized,
            pre_swarm_policy_path=pre_swarm_path,
            champion_probe_active=True,
            frozen_tick_windows=frozen_windows,
            frozen_window_count=len(frozen_windows),
            frozen_window_cursor=0,
        )
        logger.info(
            "birth.policy_swarm.started variants=%s stage=%s champion_probe=1 windows=%s",
            len(materialized),
            self.stage.value,
            len(frozen_windows),
        )
    def _maybe_record_and_advance_swarm(self, *, trades: int, wins: int, total_pnl: float) -> None:
        if not self.swarm_state.active:
            return
        probe_target = swarm_rollout_target(self.cur_cfg)
        # Equal-window champion probe before variants.
        if self.swarm_state.champion_probe_active:
            self.swarm_state.champion_probe_rollouts += 1
            self.swarm_state.champion_probe_trades += max(0, int(trades))
            self.swarm_state.champion_probe_wins += max(0, int(wins))
            self.swarm_state.champion_probe_pnl += float(total_pnl)
            self.target = probe_target
            if self.swarm_state.champion_probe_rollouts < probe_target:
                return
            self.swarm_tournament_at_start = tournament_score(
                trades=self.swarm_state.champion_probe_trades,
                wins=self.swarm_state.champion_probe_wins,
                total_pnl=self.swarm_state.champion_probe_pnl,
            )
            self.swarm_edgescore_at_start = self.swarm_tournament_at_start  # legacy alias
            self.swarm_state.champion_probe_active = False
            self.swarm_state.variant_index = 0
            self.swarm_state.rollouts_this_variant = 0
            self.swarm_state.reset_frozen_window_cursor()
            logger.info(
                "birth.policy_swarm.champion_probe_done score=%.3f trades=%s",
                self.swarm_tournament_at_start,
                self.swarm_state.champion_probe_trades,
            )
            self._apply_swarm_variant_for_rollout()
            return
        variant = self.swarm_state.current_variant()
        if variant is None:
            # Incomplete resume / empty variants — fail-closed, do not silent-abort.
            self.swarm_state.active = False
            self.swarm_rejected_no_lift = True
            self.swarm_state.rejected_no_lift = True
            self._write_progress(
                phase="policy_swarm",
                message="Swarm aborted: incomplete tournament state (no variants)",
            )
            return
        record_swarm_rollout(
            self.swarm_state,
            variant_id=variant.variant_id,
            trades=trades,
            wins=wins,
            total_pnl=total_pnl,
        )
        self.swarm_state.rollouts_this_variant += 1
        self.target = probe_target
        if self.swarm_state.rollouts_this_variant < self.target:
            return
        self.swarm_state.rollouts_this_variant = 0
        self.swarm_state.variant_index += 1
        self.swarm_state.reset_frozen_window_cursor()
        if self.swarm_state.variant_index >= len(self.swarm_state.variants):
            starship_on = bool(getattr(self.cur_cfg, "starship_swarm_first_enabled", True))
            winner = select_swarm_winner(
                self.swarm_state,
                prefer_tournament_score=starship_on,
                prefer_expectancy=(
                    not starship_on
                    and bool(getattr(self.cur_cfg, "stage1_edgescore_enabled", False))
                ),
            )
            before = float(
                getattr(
                    self,
                    "swarm_tournament_at_start",
                    getattr(self, "swarm_edgescore_at_start", -1.0),
                )
            )
            delta = float(getattr(self.cur_cfg, "plateau_evolution_meaningful_delta", 0.01))
            after = before
            winner_trades = 0
            if winner is not None:
                row = self.swarm_state.results.get(winner.variant_id)
                if row is not None:
                    winner_trades = int(row.trades)
                    after = edgescore_from_swarm_result(
                        trades=row.trades,
                        wins=row.wins,
                        total_pnl=row.total_pnl,
                        cfg=self.cur_cfg,
                    )
            min_trades = max(20, int(getattr(self.cur_cfg, "policy_swarm_min_trades", 20)))
            probe_trades = int(getattr(self.swarm_state, "champion_probe_trades", 0) or 0)
            sample_ok = winner_trades >= min_trades and probe_trades >= min_trades
            lift_trades = min(winner_trades, probe_trades) if sample_ok else 0
            lift_ok = sample_ok and swarm_tournament_lift(
                before_score=before,
                after_score=after,
                meaningful_delta=delta,
                trades=lift_trades,
            )
            # When Starship swarm-first disabled, keep legacy always-commit behavior.
            require_lift = bool(getattr(self.cur_cfg, "starship_swarm_first_enabled", True))
            self.swarm_state.active = False
            if winner is not None and (lift_ok or not require_lift):
                if winner.policy_path:
                    self.host.current_policy = self.host._create_birth_policy(
                        allow_load_existing=True,
                        policy_path=winner.policy_path,
                    )
                if self.cur_cfg.meta_controller_enabled:
                    self.bus.meta_patch_state(
                        self.stage, active_reward=reward_config_to_dict(winner.reward)
                    )
                self.swarm_state.committed_variant_id = winner.variant_id
                self.swarm_state.rejected_no_lift = False
                self.swarm_tournament_lift_ok = True
                self.swarm_edgescore_lift_ok = True  # legacy alias
                self.swarm_rejected_no_lift = False
                logger.info(
                    "birth.policy_swarm.committed winner=%s tournament_before=%.3f after=%.3f",
                    winner.variant_id,
                    before,
                    after,
                )
                return
            # No lift / inconclusive sample — reject winner, restore champion, raise attention.
            self._restore_pre_swarm_policy()
            rejected_id = winner.variant_id if winner is not None else "none"
            self.swarm_state.committed_variant_id = ""
            self.swarm_state.rejected_no_lift = True
            self.swarm_tournament_lift_ok = False
            self.swarm_edgescore_lift_ok = False  # legacy alias
            self.swarm_rejected_no_lift = True
            reason = "inconclusive_sample" if not sample_ok else "no_tournament_lift"
            self.swarm_fail_reason_code = (
                "swarm_inconclusive_sample"
                if reason == "inconclusive_sample"
                else "swarm_no_tournament_lift"
            )
            self._swarm_reject_hard_stop_armed = False
            logger.warning(
                "birth.policy_swarm.rejected_%s winner=%s before=%.3f after=%.3f delta=%.3f",
                reason,
                rejected_id,
                before,
                after,
                delta,
            )
            self._write_progress(
                phase="policy_swarm",
                message=(
                    f"Swarm rejected {rejected_id}: {reason} "
                    f"({before:.3f}→{after:.3f}); champion restored"
                ),
            )
            return
        self._apply_swarm_variant_for_rollout()
