"""StageLoopDataCacheMixin — intra pools, oracle harvest, data expansion.

Part of StageLoopDataOpsMixin (Wave B PR-B4).
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    filter_ticks_for_stage,
    split_stage1_trend_ticks,
    split_stage2_range_ticks,
)
from lumina_core.birth.data_expansion import (
    clamp_expansion_steps,
    expand_birth_data,
    expansion_ladder_at_max,
)
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.stall_remediation import curate_buffer_top_quartile
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_data_cache")


def _mine_winning_patterns(**kwargs: Any) -> Any:
    """Late-bound so tests can monkeypatch stage_training_loop.mine_winning_patterns."""
    from lumina_core.birth import stage_training_loop as _compat

    return _compat.mine_winning_patterns(**kwargs)


class StageLoopDataCacheMixin(StageLoopMixinBase):
    """Tick-pool / buffer / expansion ops for StageLoopSession."""

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
            self._capture_trainer_policy_entropy()
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
        mine_result = _mine_winning_patterns(
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
        max_days = int(self.host.birth_config.max_real_days)
        steps = clamp_expansion_steps(
            list(self.cur_cfg.data_expansion_steps),
            max_real_days=max_days,
        )
        if expansion_ladder_at_max(
            self.expansion_step,
            steps,
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
            expansion_steps=steps,
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
            max_real_days=max_days,
        )
        self.expansion_step = expanded.step_index
        # Honest loaded depth = calendar span, not requested ladder rung.
        self.data_days_loaded = int(
            expanded.actual_calendar_days or expanded.days_back
        )
        if expanded.exhausted and not expanded.train_ticks:
            self.data_exhausted = True
            return False
        self.active_train = list(expanded.train_ticks)
        self.active_stage_ticks = filter_ticks_for_stage(self.stage, self.active_train) or list(self.active_train)
        self._rebuild_intra_pools(self.active_stage_ticks)
        self.host._real_data_pct = expanded.real_data_pct
        self.host._data_manifest["requested_days"] = int(expanded.requested_days)
        self.host._data_manifest["actual_calendar_days"] = int(
            expanded.actual_calendar_days
        )
        self.host._data_manifest["days_loaded"] = int(self.data_days_loaded)
        depth_warn = ""
        if (
            expanded.requested_days > 0
            and expanded.actual_calendar_days > 0
            and expanded.actual_calendar_days < max(7, int(expanded.requested_days * 0.5))
        ):
            depth_warn = (
                f" (thin: {expanded.actual_calendar_days}d actual / "
                f"{expanded.requested_days}d requested)"
            )
            logger.warning(
                "birth.data_expansion.depth_thin requested=%s actual=%s",
                expanded.requested_days,
                expanded.actual_calendar_days,
            )
        self._write_progress(
            phase="data_expansion",
            message=(
                f"Data expansion: {self.data_days_loaded}d actual"
                f" (requested {expanded.requested_days}d){depth_warn}, "
                f"{len(self.active_train):,} train ticks · {self.stage.value}"
            ),
        )
        return True
