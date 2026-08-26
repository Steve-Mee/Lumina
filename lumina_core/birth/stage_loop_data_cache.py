"""StageLoopDataCacheMixin — intra pools, oracle harvest, data expansion."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    split_stage1_trend_ticks,
    split_stage2_range_ticks,
)
from lumina_core.birth.foundation_history import apply_expansion_history_manifest
from lumina_core.birth.foundation_stages import refresh_fail_closed_ticks_after_data_change
from lumina_core.birth.data_expansion import (
    clamp_expansion_steps,
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


def _expand_birth_data(**kwargs: Any) -> Any:
    """Late-bound so tests can monkeypatch stage_training_loop.expand_birth_data."""
    from lumina_core.birth import stage_training_loop as _compat

    return _compat.expand_birth_data(**kwargs)


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
        # Expectancy quality mode: selective inject (geometry-matched auto_calib),
        # not buffer flood that dilutes PPO toward non-transferable winners.
        quality_mode = False
        beat_random_mode = False
        try:
            last = getattr(self, "meta_last_plan", None)
            rationale = str(getattr(last, "rationale", "") or "").lower()
            quality_mode = (
                "stage2_expectancy" in rationale
                or "expectancy_quality" in rationale
                or "beat_random" in rationale
                or "pass_vector" in rationale
            )
            beat_random_mode = "beat_random" in rationale or "anti_edge" in rationale
        except Exception:
            quality_mode = False
            beat_random_mode = False
        # Also treat active anti-edge / exit magnet as quality inject discipline.
        try:
            edge = getattr(self, "_edge_vs_random", None)
            if edge is not None and float(edge) < -1e-12:
                quality_mode = True
                beat_random_mode = True
            peak_st0 = getattr(self, "stage2_peak_state", None)
            if peak_st0 is not None:
                stop_n = int(getattr(peak_st0, "cumulative_closes_stop", 0) or 0)
                tgt_n = int(getattr(peak_st0, "cumulative_closes_target", 0) or 0)
                if stop_n + tgt_n >= 40 and float(stop_n) / float(max(1, tgt_n)) > 2.5:
                    quality_mode = True
        except Exception:
            pass
        # PR-H: finish / near-miss / peak_grad → no inject flood (skip or tiny cap).
        finish_block = False
        try:
            from lumina_core.birth.stage2_peak_capture import finish_mode_blocks_pattern_inject

            peak_st_f = getattr(self, "stage2_peak_state", None)
            if peak_st_f is not None and finish_mode_blocks_pattern_inject(peak_st_f):
                finish_block = True
                if not aggressive:
                    # Hard zero inject under finish (plan: no pattern_inject flood).
                    max_patterns = 0
                    scan_stride = max(int(scan_stride), 8)
        except Exception:
            finish_block = False
        if quality_mode and not aggressive and not finish_block:
            qcap = int(getattr(self.cur_cfg, "stage2_quality_inject_max_patterns", 200) or 200)
            if beat_random_mode:
                qcap = min(
                    qcap,
                    int(
                        getattr(self.cur_cfg, "stage2_beat_random_inject_max_patterns", 80) or 80
                    ),
                )
            # Peak protect / near-miss: even tighter inject (P2 buffer discipline).
            try:
                peak_st = getattr(self, "stage2_peak_state", None)
                peak_thr = float(
                    getattr(self.cur_cfg, "stage2_swarm_block_if_peak_wr_above", 0.28) or 0.28
                )
                if peak_st is not None and (
                    bool(getattr(peak_st, "near_miss_active", False))
                    or float(getattr(peak_st, "peak_winrate", 0.0) or 0.0) >= peak_thr
                ):
                    qcap = min(
                        qcap,
                        int(getattr(self.cur_cfg, "stage2_peak_inject_max_patterns", 120) or 120),
                    )
            except Exception:
                pass
            max_patterns = max(20, min(int(max_patterns), max(20, qcap)))
            scan_stride = max(int(scan_stride), 3)
        # Prefer full train universe for harvest (intra pool can be too thin for calib).
        if len(pool) < 80 and self.active_train:
            pool = list(self.active_train)
        # Align oracle hold with geometry horizon (do not force 180 when cfg is 90/120).
        hold = max(30, int(getattr(self.cur_cfg, "oracle_max_hold_bars", 90) or 90))
        # Prefer stage geometry SSOT so oracle stop/target match live SIM.
        geo_stop = getattr(self, "_birth_trade_stop_pct", None)
        geo_target = getattr(self, "_birth_trade_target_pct", None)
        use_auto = True
        fixed_stop = None
        fixed_target = None
        if geo_stop is not None and geo_target is not None and float(geo_stop) > 0:
            # Pass stage geometry as fixed; still allow auto_calibrate path to
            # re-derive if caller forces, but prefer explicit aligned physics.
            fixed_stop = float(geo_stop)
            fixed_target = float(geo_target)
            use_auto = False
        # Finish mode: max_patterns=0 → skip mine entirely (no empty harvest thrash).
        if int(max_patterns) <= 0:
            self.oracle_last_reason = "finish_mode_skip_inject"
            self.oracle_last_patterns = 0
            return
        # Net-of-cost oracle floor (same fee model as geometry) — no gross-only flood.
        # Stage-2 uses higher min-net (quality); Stage-1/3 keep a soft positive floor so
        # survival harvest is not starved by Stage-2 economics.
        from lumina_core.birth.curriculum import CurriculumStage as _CS

        if self.stage == _CS.STAGE2_RANGE:
            min_net = float(getattr(self.cur_cfg, "stage2_min_net_oracle_pnl", 0.50) or 0.0)
            if min_net <= 0:
                min_net = 0.01
        else:
            min_net = 0.01
        mine_result = _mine_winning_patterns(
            ticks=pool,
            stage=self.stage,
            runtime=self.host.runtime,
            workspace_root=self.host.workspace_root,
            max_patterns=max_patterns,
            scan_stride=scan_stride,
            max_hold_bars=hold,
            auto_calibrate=use_auto,
            stop_pct=fixed_stop,
            target_pct=fixed_target,
            net_of_cost=True,
            min_net_pnl_usd=min_net,
            min_pnl_usd=min_net,
        )
        found = len(mine_result.patterns)
        self.patterns_mined += found
        self.oracle_wins += mine_result.wins
        self.oracle_last_scanned = int(mine_result.scanned)
        self.oracle_last_patterns = found
        self.oracle_last_stop_pct = float(mine_result.stop_pct)
        self.oracle_last_target_pct = float(mine_result.target_pct)
        self.oracle_last_reason = str(mine_result.reason or "")
        # If mine returned capped/macro vs stage geometry, realign log for operator.
        try:
            from lumina_core.birth.runtime_diagnostics import log_geometry_trace

            log_geometry_trace(
                where="oracle_mine",
                stop_pct=float(mine_result.stop_pct),
                target_pct=float(mine_result.target_pct),
                source=str(getattr(self, "_birth_trade_geometry_source", "") or ""),
                pool_size=len(pool),
                oracle_stop=float(mine_result.stop_pct),
                oracle_target=float(mine_result.target_pct),
            )
        except Exception:
            pass
        if (
            fixed_stop is not None
            and abs(float(mine_result.stop_pct) - float(fixed_stop)) > 1e-6
        ):
            logger.warning(
                "birth.oracle.geometry_mismatch stage_stop=%.6f mine_stop=%.6f source=%s",
                float(fixed_stop),
                float(mine_result.stop_pct),
                getattr(self, "_birth_trade_geometry_source", ""),
            )
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
        self._refresh_fail_closed_stage_ticks()
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

    def _refresh_fail_closed_stage_ticks(self) -> None:
        pct = float(getattr(self.cur_cfg, "certificate_runway_validation_pct", 0.20) or 0.20)
        self.stage_ticks, self.active_stage_ticks = refresh_fail_closed_ticks_after_data_change(
            self.stage,
            train_ticks=self.active_train,
            previous_stage_ticks=getattr(self, "stage_ticks", None),
            holdout_ticks=getattr(self, "holdout_ticks", None),
            validation_pct=pct,
        )

    def _maybe_expand_data(self) -> bool:
        if self.data_exhausted:
            return False
        max_days = int(self.host.birth_config.max_real_days)
        steps = clamp_expansion_steps(
            list(self.cur_cfg.data_expansion_steps),
            max_real_days=max_days,
        )
        prior_train = list(self.active_train) if self.active_train else []
        prior_count = len(prior_train)
        if expansion_ladder_at_max(
            self.expansion_step,
            steps,
            has_train_ticks=bool(prior_train),
        ):
            logger.info(
                "birth.data_expansion.skip_at_max step=%s train_ticks=%s",
                self.expansion_step,
                prior_count,
            )
            self.data_exhausted = True
            return False
        expanded = _expand_birth_data(
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
        load_failed = bool(getattr(expanded, "load_failed", False)) or not expanded.train_ticks

        if load_failed or not expanded.train_ticks:
            if expanded.exhausted or load_failed:
                self.data_exhausted = True
            logger.warning(
                "birth.data_expansion.preserved_prior reason=%s prior_ticks=%s "
                "requested_days=%s exhausted=%s load_failed=%s",
                "empty_load" if load_failed else "no_train_ticks",
                prior_count,
                int(expanded.requested_days or expanded.days_back or 0),
                bool(expanded.exhausted),
                load_failed,
            )
            if prior_count > 0:
                self._write_progress(
                    phase="data_expansion",
                    message=(
                        f"Data expansion failed (0 bars for "
                        f"{int(expanded.requested_days or expanded.days_back or 0)}d) — "
                        f"preserved {prior_count:,} prior train ticks · {self.stage.value}. "
                        "Check Fabric/NT HDS or market-data connection; training continues on cache."
                    ),
                )
            return False

        self.data_days_loaded = int(
            expanded.actual_calendar_days or expanded.days_back
        )
        self.active_train = list(expanded.train_ticks)
        if expanded.holdout_ticks:
            self.holdout_ticks = list(expanded.holdout_ticks)
            self.holdout_ticks_ref = list(expanded.holdout_ticks)
        self._refresh_fail_closed_stage_ticks()
        self._rebuild_intra_pools(self.active_stage_ticks)
        self.host._real_data_pct = expanded.real_data_pct
        apply_expansion_history_manifest(
            self.host._data_manifest,
            expanded,
            days_loaded=self.data_days_loaded,
        )
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
