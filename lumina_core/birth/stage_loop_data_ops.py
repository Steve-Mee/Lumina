"""StageLoopDataOpsMixin — StageLoopSession mixin."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from lumina_core.birth.birth_bus_serde import reward_config_to_dict
from lumina_core.birth.curriculum import (
    CurriculumStage,
    filter_ticks_for_stage,
    split_stage1_trend_ticks,
    split_stage2_range_ticks,
)
from lumina_core.birth.data_expansion import expand_birth_data, expansion_ladder_at_max
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.policy_swarm import (
    PolicySwarmState,
    build_swarm_variants,
    record_swarm_rollout,
    select_swarm_winner,
    swarm_rollout_target,
)
from lumina_core.birth.stall_remediation import (
    curate_buffer_top_quartile,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")

class StageLoopDataOpsMixin(StageLoopMixinBase):
    """See StageLoopSession for attributes."""

    def _rebuild_intra_pools(self, ticks: list[dict[str, Any]]) -> None:
        if self.stage != CurriculumStage.STAGE1_TREND or not self.cur_cfg.intra_stage1_enabled:
            self.intra_easy_pool = []
            self.intra_hard_pool = []
            self.intra_meta = {}
        else:
            self.intra_easy_pool, self.intra_hard_pool, self.intra_meta = split_stage1_trend_ticks(
                ticks,
                easy_percentile=self.cur_cfg.intra_easy_percentile,
                hard_percentile=self.cur_cfg.intra_hard_percentile,
            )
        if self.stage != CurriculumStage.STAGE2_RANGE or not self.cur_cfg.intra_stage2_enabled:
            self.intra_s2_easy_pool = []
            self.intra_s2_hard_pool = []
            self.intra_s2_meta = {}
        else:
            self.intra_s2_easy_pool, self.intra_s2_hard_pool, self.intra_s2_meta = split_stage2_range_ticks(
                ticks,
                easy_percentile=self.cur_cfg.intra_stage2_easy_percentile,
                hard_percentile=self.cur_cfg.intra_stage2_hard_percentile,
            )

    def _apply_oracle_distill(self) -> str:
        removed = curate_buffer_top_quartile(
            self.host.buffer,
            keep_pct=float(self.cur_cfg.plateau_oracle_distill_top_pct),
        )
        if len(self.host.buffer) >= 256:
            polish = max(1000, int(getattr(self.cur_cfg, "polish_ppo_timesteps", 10_000)))
            batch = min(5000, polish)
            self.host.ppo_trainer.update_from_buffer(
                buffer=self.host.buffer,
                timesteps=batch,
                birth_phase=True,
            )
            self.host.ppo_steps += batch
        return f"oracle distill (removed {removed} low-reward trajectories)"

    def _mine_and_inject(self, *, aggressive: bool = False) -> int:
        """Mine oracle patterns into buffer. Returns number of patterns found this call."""
        if self.current_intra_sample_pool:
            pool = list(self.current_intra_sample_pool)
        elif len(self.active_train) > len(self.active_stage_ticks):
            pool = list(self.active_train)
        else:
            pool = list(self.active_stage_ticks)
        max_patterns, scan_stride = self.host._resolve_oracle_mining_params(
            self.cur_cfg,
            aggressive=aggressive,
        )
        # Prefer full train universe for harvest (intra pool can be too thin for calib).
        if len(pool) < 80 and self.active_train:
            pool = list(self.active_train)
        hold = max(int(self.cur_cfg.oracle_max_hold_bars), 180)
        mine_result = mine_winning_patterns(
            ticks=pool,
            stage=self.stage,
            runtime=self.host.runtime,
            workspace_root=self.host.workspace_root,
            max_patterns=max_patterns,
            scan_stride=scan_stride,
            max_hold_bars=hold,
            auto_calibrate=True,
        )
        found = len(mine_result.patterns)
        self.patterns_mined += found
        self.oracle_wins += mine_result.wins
        self.oracle_last_scanned = int(mine_result.scanned)
        self.oracle_last_patterns = found
        self.oracle_last_stop_pct = float(mine_result.stop_pct)
        self.oracle_last_target_pct = float(mine_result.target_pct)
        self.oracle_last_reason = str(mine_result.reason or "")
        self.bus.meta_record_inject(
            self.stage,
            patterns=found,
            oracle_wins=mine_result.wins,
        )
        for pattern in mine_result.patterns:
            self.host.buffer.add(
                pattern,
                priority=3.0 + min(10.0, abs(float(pattern.get("reward", 0.0)))),
            )
        self.active_stage_ticks = filter_ticks_for_stage(self.stage, self.active_train) or list(
            self.active_train
        )
        self._rebuild_intra_pools(self.active_stage_ticks)
        return found

    def _force_oracle_harvest(self, *, reason: str = "force") -> int:
        """Mandatory harvest independent of meta thrash (Raptor v4)."""
        if not getattr(self, "active_train", None) and not getattr(
            self, "active_stage_ticks", None
        ):
            logger.info(
                "birth.oracle.force_harvest skipped reason=%s detail=ticks_not_ready",
                reason,
            )
            return 0
        found = self._mine_and_inject(aggressive=True)
        logger.info(
            "birth.oracle.force_harvest reason=%s found=%s cumulative=%s last_reason=%s",
            reason,
            found,
            self.patterns_mined,
            getattr(self, "oracle_last_reason", ""),
        )
        return found

    def _maybe_expand_data(self) -> bool:
        if self.data_exhausted:
            return False
        if expansion_ladder_at_max(
            self.expansion_step,
            list(self.cur_cfg.data_expansion_steps),
            has_train_ticks=bool(self.active_train),
        ):
            logger.info(
                "birth.data_expansion.skip_at_max step=%s train_ticks=%s",
                self.expansion_step,
                len(self.active_train),
            )
            self.data_exhausted = True
            return False
        expanded = expand_birth_data(
            market_data_service=self.host.market_data_service,
            runtime=self.host.runtime,
            current_step=self.expansion_step,
            expansion_steps=list(self.cur_cfg.data_expansion_steps),
            holdout_pct=self.host.birth_config.holdout_pct,
            enrich_news_fn=lambda rows: enrich_ticks_with_news(
                rows,
                workspace_root=self.host.workspace_root,
                primary=self.news_cfg.primary,
                enable_cache=self.news_cfg.enable_cache,
                cache_path=self.news_cfg.cache_path,
            ),
            synthetic_fallback_fn=(
                None
                if self.prefer_real
                else lambda n, p: self.host._generate_synthetic_ticks(n, start_price=p or self.start_price)
            ),
            start_price=self.start_price,
        )
        self.expansion_step = expanded.step_index
        self.data_days_loaded = expanded.days_back
        if expanded.exhausted and not expanded.train_ticks:
            self.data_exhausted = True
            return False
        self.active_train = list(expanded.train_ticks)
        self.active_stage_ticks = filter_ticks_for_stage(self.stage, self.active_train) or list(self.active_train)
        self._rebuild_intra_pools(self.active_stage_ticks)
        self.host._real_data_pct = expanded.real_data_pct
        self._write_progress(
            phase="data_expansion",
            message=(
                f"Data expansion: {self.data_days_loaded} dagen, "
                f"{len(self.active_train):,} train ticks · {self.stage.value}"
            ),
        )
        return True

    def _apply_swarm_variant_for_rollout(self) -> tuple[Any | None, float]:
        variant = self.swarm_state.current_variant()
        if variant is None:
            return None, 1.0
        if variant.policy_path:
            self.host.current_policy = self.host._create_birth_policy(
                allow_load_existing=True,
                policy_path=variant.policy_path,
            )
        return variant.reward, float(variant.explore_multiplier)

    def _start_policy_swarm(self) -> None:
        if (
            not self.cur_cfg.policy_swarm_enabled
            or self.allow_provisional
            or self.swarm_state.active
            or self.swarm_state.committed_variant_id
        ):
            return
        baseline = (
            self.bus.meta_controller.active_reward
            if self.cur_cfg.meta_controller_enabled
            else self.host.birth_config.reward
        )
        variants = build_swarm_variants(baseline, cfg=self.cur_cfg)
        swarm_dir = self.host.workspace_root / "lumina_agents" / "ppo"
        swarm_dir.mkdir(parents=True, exist_ok=True)
        materialized = []
        save_fn = getattr(self.host.ppo_trainer, "save_final_birth_policy", None)
        for index, variant in enumerate(variants):
            self.host.current_policy = self.host._create_birth_policy(
                allow_load_existing=False,
                force_reinit=True,
            )
            path = swarm_dir / f"swarm_{self.stage.value}_{index}_{variant.variant_id}.zip"
            if callable(save_fn):
                save_fn(str(path))
            materialized.append(replace(variant, policy_path=str(path)))
        self.swarm_state = PolicySwarmState(active=True, variants=materialized)
        self._apply_swarm_variant_for_rollout()
        logger.info("birth.policy_swarm.started variants=%s stage=%s", len(materialized), self.stage.value)

    def _maybe_record_and_advance_swarm(self, *, trades: int, wins: int, total_pnl: float) -> None:
        if not self.swarm_state.active:
            return
        variant = self.swarm_state.current_variant()
        if variant is None:
            self.swarm_state.active = False
            return
        record_swarm_rollout(
            self.swarm_state,
            variant_id=variant.variant_id,
            trades=trades,
            wins=wins,
            total_pnl=total_pnl,
        )
        self.swarm_state.rollouts_this_variant += 1
        self.target = swarm_rollout_target(self.cur_cfg)
        if self.swarm_state.rollouts_this_variant < self.target:
            return
        self.swarm_state.rollouts_this_variant = 0
        self.swarm_state.variant_index += 1
        if self.swarm_state.variant_index >= len(self.swarm_state.variants):
            winner = select_swarm_winner(self.swarm_state)
            if winner is not None:
                if winner.policy_path:
                    self.host.current_policy = self.host._create_birth_policy(
                        allow_load_existing=True,
                        policy_path=winner.policy_path,
                    )
                if self.cur_cfg.meta_controller_enabled:
                    self.bus.meta_patch_state(self.stage, active_reward=reward_config_to_dict(winner.reward))
                self.swarm_state.committed_variant_id = winner.variant_id
            self.swarm_state.active = False
            logger.info(
                "birth.policy_swarm.committed winner=%s",
                self.swarm_state.committed_variant_id,
            )
            return
        self._apply_swarm_variant_for_rollout()

