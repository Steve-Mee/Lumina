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

