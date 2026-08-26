"""Session prepare: pools, oracle mine, research start (M5)."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    stage1_intra_state_from_metrics,
    stage2_intra_state_from_metrics,
)
from lumina_core.birth.meta_controller import MetaActionPlan
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session_runner")


class SessionPhasePrepareInitMixin:
    def _prepare_init_pools_and_research(self) -> None:
        """Init tick pools, intra curriculum, oracle, PPO seed."""
        self.last_stage_trades = -1
        self.stagnation_count = 0
        self.chunk_budget = max(5_000, self.cur_cfg.rollout_chunk_trades * self.cur_cfg.rollout_step_budget_multiplier)
        self.active_train = list(self.train_ticks)
        self.active_stage_ticks = list(self.stage_ticks)
        # Raptor v9: harvest only after tick pools exist.
        if getattr(self, "_pending_deep_resume_harvest", False):
            self._pending_deep_resume_harvest = False
            try:
                self._force_oracle_harvest(reason="deep_resume")
            except Exception as exc:
                logger.warning("birth.oracle.force_harvest_failed: %s", exc)
        self.data_exhausted = False
        self.scorecard_snapshot_trades = self.stage_trades
        self.scorecard_snapshot_patterns = self.patterns_mined
        self.scorecard_snapshot_at = time.time()
        self.last_progress_write_at = 0.0
        self.last_hold_ratio = 0.0



        self.intra_state: Stage1IntraCurriculumState | None = None
        self.intra_easy_pool: list[dict[str, Any]] = []
        self.intra_hard_pool: list[dict[str, Any]] = []
        self.intra_meta: dict[str, Any] = {}
        self.intra_s2_state: Stage2IntraCurriculumState | None = None
        self.intra_s2_easy_pool: list[dict[str, Any]] = []
        self.intra_s2_hard_pool: list[dict[str, Any]] = []
        self.intra_s2_meta: dict[str, Any] = {}
        self.current_intra_sample_pool: list[dict[str, Any]] = []


        if self.stage == CurriculumStage.STAGE1_TREND and self.cur_cfg.intra_stage1_enabled:
            if isinstance(self.stage_metrics, dict) and self.stage_metrics.get("intra_stage1_hard_pct") is not None:
                self.intra_state = stage1_intra_state_from_metrics(
                    self.stage_metrics,
                    default_hard_pct=self.cur_cfg.intra_initial_hard_pct,
                )
            else:
                self.intra_state = Stage1IntraCurriculumState(hard_pct=self.cur_cfg.intra_initial_hard_pct)
            self._rebuild_intra_pools(self.active_stage_ticks)
        if self.stage == CurriculumStage.STAGE2_RANGE and self.cur_cfg.intra_stage2_enabled:
            if isinstance(self.stage_metrics, dict) and self.stage_metrics.get("intra_stage2_hard_pct") is not None:
                self.intra_s2_state = stage2_intra_state_from_metrics(
                    self.stage_metrics,
                    default_hard_pct=self.cur_cfg.intra_stage2_initial_hard_pct,
                )
            else:
                self.intra_s2_state = Stage2IntraCurriculumState(
                    hard_pct=self.cur_cfg.intra_stage2_initial_hard_pct
                )
            self._rebuild_intra_pools(self.active_stage_ticks)
        self.last_winrate = 0.0
        self.meta_last_plan: MetaActionPlan | None = None
        self.meta_message_suffix = ""
        # Pin loaded code identity before training decisions (forensics).
        try:
            from lumina_core.birth.runtime_diagnostics import log_birth_code_fingerprint

            log_birth_code_fingerprint(
                reason=f"stage_prepare:{getattr(self.stage, 'value', self.stage)}"
            )
        except Exception as exc:
            logger.warning("birth.runtime.fingerprint_failed: %s", exc)
        # Birth trade geometry SSOT — calibrate at stage entry on CHRONOLOGICAL
        # stage/train ticks only (never on shuffled intra active_ticks).
        try:
            from lumina_core.birth.birth_trade_geometry import (
                BirthTradeGeometry,
                calibrate_birth_stops,
            )
            from lumina_core.birth.runtime_diagnostics import log_geometry_trace

            pool = list(self.active_stage_ticks or self.active_train or [])
            hold = max(20, int(getattr(self.cur_cfg, "oracle_max_hold_bars", 90) or 90))
            geo = calibrate_birth_stops(pool, max_hold_bars=hold)
            self._birth_trade_stop_pct = float(geo.stop_pct)
            self._birth_trade_target_pct = float(geo.target_pct)
            self._birth_trade_geometry_source = str(geo.source)
            self._birth_trade_geometry = geo
            self._birth_geometry_hold_bars = int(
                getattr(geo, "hold_bars", 0) or hold or 120
            )
            # Random first-touch baseline at frozen geometry (edge-vs-random diagnostic).
            try:
                from lumina_core.birth.birth_trade_geometry import first_touch_target_hit_rate

                thr = first_touch_target_hit_rate(
                    pool,
                    stop_pct=geo.stop_pct,
                    target_pct=geo.target_pct,
                    max_hold_bars=hold,
                    sample_stride=30,
                )
                self._first_touch_target_hit_rate = float(thr)
            except Exception:
                self._first_touch_target_hit_rate = 0.0
            logger.info(
                "birth.stage.geometry stage=%s stop=%.5f%% target=%.5f%% source=%s pool=%s "
                "ordered=%s p40=%.6f macro_rej=%s hold=%s floor_bound=%s net_rr=%.3f be_wr=%.3f "
                "first_touch_thr=%.3f",
                getattr(self.stage, "value", self.stage),
                geo.stop_pct * 100.0,
                geo.target_pct * 100.0,
                geo.source,
                len(pool),
                geo.time_ordered,
                geo.p40_raw,
                geo.macro_rejected,
                geo.hold_bars,
                geo.floor_bound,
                geo.net_rr_after_cost,
                geo.breakeven_wr_after_cost,
                float(getattr(self, "_first_touch_target_hit_rate", 0.0) or 0.0),
            )
            log_geometry_trace(
                where="stage_prepare",
                stop_pct=geo.stop_pct,
                target_pct=geo.target_pct,
                source=geo.source,
                pool_size=len(pool),
                time_ordered=bool(geo.time_ordered),
                macro_rejected=bool(geo.macro_rejected),
                p40_raw=float(geo.p40_raw),
            )
            # Stage2 hygiene: mandatory oracle harvest on same frozen geometry.
            # NOTE: do NOT re-import CurriculumStage here — that makes it a local
            # name for the whole function and breaks earlier uses (UnboundLocalError).
            try:
                if self.stage == CurriculumStage.STAGE2_RANGE:
                    if hasattr(self, "_force_oracle_harvest"):
                        found = int(self._force_oracle_harvest(reason="stage2_entry_geometry") or 0)
                        logger.info(
                            "birth.stage.stage2_entry_oracle patterns=%s stop=%.6f tgt=%.6f",
                            found,
                            geo.stop_pct,
                            geo.target_pct,
                        )
                        self.stage2_bootstrap_patterns = int(found)
                        # Cold bootstrap: reinit action head + curate buffer + PPO warm.
                        # Detox Stage1 survival prior (~26% WR) without floor theater.
                        self.stage2_bootstrap_updates = 0
                        self.stage2_action_head_reinit = False
                        try:
                            from lumina_core.birth.stage2_policy_bootstrap import (
                                run_stage2_cold_bootstrap,
                            )

                            boot = run_stage2_cold_bootstrap(
                                host=self.host,
                                cur_cfg=self.cur_cfg,
                                oracle_patterns=int(found),
                                buffer=self.host.buffer,
                            )
                            self.stage2_bootstrap_updates = int(boot.get("ppo_steps", 0) or 0)
                            self.stage2_action_head_reinit = bool(
                                (boot.get("action_head_reinit") or {}).get("ok")
                            )
                            self.stage2_bootstrap_detail = str(boot.get("reason") or "")
                            if hasattr(self, "_capture_trainer_policy_entropy"):
                                self._capture_trainer_policy_entropy()
                            logger.info(
                                "birth.stage.stage2_cold_bootstrap patterns=%s ppo=%s "
                                "reinit=%s ok=%s reason=%s",
                                found,
                                self.stage2_bootstrap_updates,
                                self.stage2_action_head_reinit,
                                boot.get("ok"),
                                boot.get("reason"),
                            )
                        except Exception as boot_exc:
                            logger.warning(
                                "birth.stage.stage2_cold_bootstrap_failed: %s",
                                boot_exc,
                            )
            except Exception as harvest_exc:
                logger.warning("birth.stage.stage2_entry_oracle_failed: %s", harvest_exc)
        except Exception as exc:
            logger.warning("birth.stage.geometry_init_failed: %s", exc)
            from lumina_core.birth.birth_trade_geometry import BirthTradeGeometry

            self._birth_trade_stop_pct = 0.0012
            self._birth_trade_target_pct = 0.0020
            self._birth_trade_geometry_source = "fallback_init"
            self._birth_trade_geometry = BirthTradeGeometry(
                stop_pct=0.0012,
                target_pct=0.0020,
                source="fallback_init",
                time_ordered=True,
            )
            self._birth_geometry_hold_bars = 120
            self._first_touch_target_hit_rate = 0.0
        self.closes_stop = 0
        self.closes_target = 0
        self.closes_flatten = 0
        self.closes_time_stop = 0
        self.closes_unknown = 0
        self.stage_closes_stop_cum = 0
        self.stage_closes_target_cum = 0
        self.stage_closes_flatten_cum = 0
        self.stage_closes_time_stop_cum = 0
        self.stage_closes_unknown_cum = 0
        self._stage2_rolling_pass_streak = 0
        self.mean_entry_stop_pct = 0.0
        self.mean_entry_target_pct = 0.0
        self.expectancy_quality_step_source = ""
        # Pilot/plant skill counters reset each stage (FORCE_OPEN does not grade pilot).
        self.stage_policy_trades = 0
        self.stage_policy_wins = 0
        self.stage_plant_trades = 0
        self.stage_plant_wins = 0

















        self._write_progress(
            phase="curriculum_research",
            message=f"Curriculum {self.stage.value}: oracle scan start (doel {self.required:,} trades).",
        )
        if isinstance(self.stage_metrics, dict) and self.stage_metrics.get("pending_data_expand"):
            self._maybe_expand_data()
            pending_cleared = dict(self._stage_metrics_payload())
            pending_cleared.pop("pending_data_expand", None)
            self.host._persist_checkpoint(
                training_mode=self.training_mode,
                curriculum_stage=self.stage.value,
                policy_path=str(self.host.final_policy_path),
                phase="curriculum_learning",
                stage_metrics=pending_cleared,
            )
        self._mine_and_inject()
        if len(self.host.buffer) >= 80:
            self.host.current_policy = self.host.ppo_trainer.update_from_buffer(
                buffer=self.host.buffer,
                timesteps=self.ppo_steps_per_update,
                birth_phase=True,
            )
            self.host.ppo_steps += self.ppo_steps_per_update
            self._capture_trainer_policy_entropy()

