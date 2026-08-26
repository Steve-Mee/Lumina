"""Birth engine trajectory buffer, stall detection, provisional pass."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    sample_intra_stage1_pool,
    sample_intra_stage2_pool,
    should_gen0_soft_pass,
)
from lumina_core.birth.meta_controller import StallDetectionResult
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


@dataclass(frozen=True, slots=True)
class ProvisionalPassDecision:
    should_grant: bool
    reason: str
    blocked_reason: str | None
    safeguards: dict[str, bool]


@dataclass(slots=True)
class TrajectoryBuffer:
    capacity: int = 500_000
    trajectories: list[dict[str, Any]] = field(default_factory=list)
    priorities: list[float] = field(default_factory=list)

    def add(self, trajectory: dict[str, Any], priority: float = 1.0) -> None:
        if len(self.trajectories) >= self.capacity:
            self.trajectories.pop(0)
            self.priorities.pop(0)
        self.trajectories.append(trajectory)
        self.priorities.append(priority)

    def sample(self, batch_size: int) -> list[dict[str, Any]]:
        if not self.trajectories:
            return []
        import numpy as np

        idx = np.random.choice(len(self.trajectories), size=min(batch_size, len(self.trajectories)), replace=False)
        return [self.trajectories[int(i)] for i in idx]

    def __len__(self) -> int:
        return len(self.trajectories)

    def clear(self) -> None:
        self.trajectories.clear()
        self.priorities.clear()



class EngineTrajectoryMixin:
    def _stage_tick_pool(
        self,
        *,
        stage: CurriculumStage,
        stage_ticks: list[dict[str, Any]],
        train_ticks: list[dict[str, Any]],
        escalation_level: int,
        attempt: int,
        chunk_target: int = 250,
        cur_cfg: BirthCurriculumConfig | None = None,
        intra_state: Stage1IntraCurriculumState | None = None,
        easy_pool: list[dict[str, Any]] | None = None,
        hard_pool: list[dict[str, Any]] | None = None,
        intra_s2_state: Stage2IntraCurriculumState | None = None,
        s2_easy_pool: list[dict[str, Any]] | None = None,
        s2_hard_pool: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        cfg = cur_cfg or self.birth_config.curriculum
        if (
            stage == CurriculumStage.STAGE1_TREND
            and cfg.intra_stage1_enabled
            and intra_state is not None
            and easy_pool
            and hard_pool
        ):
            pool_size = max(
                chunk_target * max(1, int(cfg.intra_pool_size_multiplier)),
                len(easy_pool),
            )
            rng = random.Random(attempt + int(intra_state.hard_pct * 1000) + escalation_level * 17)
            return sample_intra_stage1_pool(
                easy_pool,
                hard_pool,
                intra_state,
                pool_size=pool_size,
                rng=rng,
                chrono_source=list(stage_ticks or train_ticks or []),
            )
        if (
            stage == CurriculumStage.STAGE2_RANGE
            and cfg.intra_stage2_enabled
            and intra_s2_state is not None
            and s2_easy_pool
            and s2_hard_pool
        ):
            pool_size = max(
                chunk_target * max(1, int(cfg.intra_pool_size_multiplier)),
                len(s2_easy_pool),
            )
            rng = random.Random(attempt + int(intra_s2_state.hard_pct * 1000) + escalation_level * 23)
            return sample_intra_stage2_pool(
                s2_easy_pool,
                s2_hard_pool,
                intra_s2_state,
                pool_size=pool_size,
                rng=rng,
                chrono_source=list(stage_ticks or train_ticks or []),
            )
        if escalation_level >= 2:
            # Contiguous windows from train — no full shuffle (geometry/path poison).
            from lumina_core.birth.curriculum_intra import _stamp_and_concat_windows

            series = list(train_ticks or stage_ticks or [])
            if len(series) < 64:
                return series
            rng = random.Random(attempt + escalation_level * 17)
            win = 256
            n_win = max(1, min(32, (len(series) + win - 1) // win))
            max_st = max(0, len(series) - win)
            windows: list[list[dict]] = []
            for _ in range(n_win):
                st = int(rng.randint(0, max_st)) if max_st > 0 else 0
                windows.append([dict(t) for t in series[st : st + win]])
            rng.shuffle(windows)
            return _stamp_and_concat_windows(windows, size=n_win * win)
        if escalation_level >= 1 and len(stage_ticks) < len(train_ticks):
            # Append contiguous train segment with explicit segment break at merge.
            from lumina_core.birth.birth_trade_geometry import (
                SEGMENT_BREAK_KEY,
                SEGMENT_ID_KEY,
            )

            extra = list(train_ticks)
            take = max(len(stage_ticks), len(train_ticks) // 4)
            merged: list[dict] = []
            for t in stage_ticks:
                row = dict(t)
                row[SEGMENT_ID_KEY] = 0
                merged.append(row)
            for j, t in enumerate(extra[:take]):
                row = dict(t)
                row[SEGMENT_ID_KEY] = 1
                if j == 0:
                    row[SEGMENT_BREAK_KEY] = True
                merged.append(row)
            return merged
        return list(stage_ticks)

    def _detect_stall(
        self,
        *,
        winrate_history: list[float],
        reward_history: list[float],
        low_velocity_attempts: int,
        cfg: BirthCurriculumConfig,
        stage: CurriculumStage = CurriculumStage.STAGE1_TREND,
    ) -> StallDetectionResult:
        """Detect learning stall via EventBus meta handler."""
        client = self._birth_bus_client
        if client is not None:
            if self._birth_handler_registry is not None:
                self._birth_handler_registry.sync_birth_cfg(cfg, self.birth_config.reward)
            client.cfg = cfg
            return client.detect_stall(
                stage,
                winrate_history=winrate_history,
                reward_history=reward_history,
                low_velocity_attempts=low_velocity_attempts,
            )
        from lumina_core.birth.meta_controller import detect_stall

        return detect_stall(
            winrate_history=winrate_history,
            reward_history=reward_history,
            low_velocity_attempts=low_velocity_attempts,
            cfg=cfg,
        )

    @staticmethod
    def _resolve_oracle_mining_params(
        cfg: BirthCurriculumConfig,
        *,
        aggressive: bool,
    ) -> tuple[int, int]:
        max_patterns = int(cfg.oracle_patterns_per_stage)
        scan_stride = int(cfg.oracle_scan_stride)
        if not aggressive:
            return max_patterns, scan_stride
        divisor = max(1, int(cfg.strong_recovery_oracle_stride_divisor))
        multiplier = max(1, int(cfg.strong_recovery_pattern_multiplier))
        scan_stride = max(1, scan_stride // divisor)
        max_patterns = min(max_patterns * multiplier, max_patterns * 2)
        return max_patterns, scan_stride

    def _maybe_trigger_provisional_pass(
        self,
        *,
        stage: CurriculumStage,
        stage_trades: int,
        required: int,
        attempt: int,
        strong_recovery_attempts: int,
        patterns_mined: int,
        buffer_size: int,
        constitution_violations: int,
        combined_velocity: float,
        allow_provisional: bool,
        cfg: BirthCurriculumConfig,
    ) -> ProvisionalPassDecision:
        """Autonomously decide provisional soft-pass (practice / allow_provisional only)."""
        _ = stage
        soft_pass_eligible = should_gen0_soft_pass(
            stage_trades=stage_trades,
            buffer_size=buffer_size,
            attempt=attempt,
            cfg=cfg,
        ) or (patterns_mined >= 100 and buffer_size >= 256)
        safeguards = {
            "allow_provisional": allow_provisional,
            "constitution_clean": constitution_violations == 0,
            "volume_gate_passed": stage_trades >= required,
            "recovery_attempts_met": strong_recovery_attempts
            >= cfg.strong_recovery_no_improvement_threshold,
            "velocity_still_low": combined_velocity <= cfg.velocity_stall_epsilon,
            "soft_pass_eligible": soft_pass_eligible,
        }
        if not allow_provisional:
            logger.info(
                "birth.provisional_pass_blocked reason=certified_mode_strict stage=%s "
                "strong_recovery_attempts=%s safeguards=%s",
                stage.value,
                strong_recovery_attempts,
                safeguards,
            )
            return ProvisionalPassDecision(
                should_grant=False,
                reason="",
                blocked_reason="certified_mode_strict",
                safeguards=safeguards,
            )
        if all(
            (
                safeguards["constitution_clean"],
                safeguards["volume_gate_passed"],
                safeguards["recovery_attempts_met"],
                safeguards["velocity_still_low"],
                safeguards["soft_pass_eligible"],
            )
        ):
            logger.info(
                "birth.provisional_pass_granted stage=%s strong_recovery_attempts=%s "
                "combined_velocity=%.6f patterns_mined=%s buffer_size=%s safeguards=%s",
                stage.value,
                strong_recovery_attempts,
                combined_velocity,
                patterns_mined,
                buffer_size,
                safeguards,
            )
            return ProvisionalPassDecision(
                should_grant=True,
                reason="strong_recovery_exhausted_soft_pass",
                blocked_reason=None,
                safeguards=safeguards,
            )
        blocked_reason = next(
            (
                key
                for key, ok in (
                    ("constitution_clean", safeguards["constitution_clean"]),
                    ("volume_gate_passed", safeguards["volume_gate_passed"]),
                    ("recovery_attempts_met", safeguards["recovery_attempts_met"]),
                    ("velocity_still_low", safeguards["velocity_still_low"]),
                    ("soft_pass_eligible", safeguards["soft_pass_eligible"]),
                )
                if not ok
            ),
            "safeguard_failed",
        )
        logger.info(
            "birth.provisional_pass_blocked reason=%s stage=%s strong_recovery_attempts=%s "
            "combined_velocity=%.6f safeguards=%s",
            blocked_reason,
            stage.value,
            strong_recovery_attempts,
            combined_velocity,
            safeguards,
        )
        return ProvisionalPassDecision(
            should_grant=False,
            reason="",
            blocked_reason=blocked_reason,
            safeguards=safeguards,
        )
