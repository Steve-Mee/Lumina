"""Progress emit / checkpoint / notify (M5 engine_lifecycle extract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.progress import write_birth_progress

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


class EngineLifecycleOpsMixin:
    def _emit_birth_progress(
        self,
        *,
        stage: str,
        phase: str,
        message: str,
        progress_pct: float,
        cumulative_trades: int = 0,
        target_trades: int = 0,
        ppo_steps: int = 0,
        birth_start_time: float = 0.0,
        extra_parts: tuple[dict[str, Any], ...] | None = None,
        **extra: Any,
    ) -> None:
        self._progress_reporter().emit_birth_progress(
            stage=stage,
            phase=phase,
            message=message,
            progress_pct=progress_pct,
            cumulative_trades=cumulative_trades,
            target_trades=target_trades,
            ppo_steps=ppo_steps,
            birth_start_time=birth_start_time,
            extra_parts=extra_parts,
            **extra,
        )

    def _write_data_prep_progress(
        self,
        *,
        phase: str,
        message: str,
        progress_pct: float,
        training_mode: str,
        processed: int | None = None,
        total: int | None = None,
    ) -> None:
        self._data_pipeline().write_data_prep_progress(
            phase=phase,
            message=message,
            progress_pct=progress_pct,
            training_mode=training_mode,
            processed=processed,
            total=total,
        )

    def _notify_milestone(self, event: Any) -> None:
        self._progress_reporter().notify_milestone(event)

    def _notify_attention(self, event: Any) -> None:
        self._progress_reporter().notify_attention(event)

    def _notify_history_unavailable(self, detail: str) -> None:
        self._progress_reporter().notify_history_unavailable(detail)

    def _restore_buffer_from_checkpoint(self, state: dict[str, Any]) -> None:
        self._checkpoint_coordinator().restore_buffer_from_checkpoint(state)

    def _apply_checkpoint_stage_metrics(self, checkpoint_state: dict[str, Any]) -> dict[str, Any]:
        metrics = checkpoint_state.get("stage_metrics")
        return metrics if isinstance(metrics, dict) else {}

    def _persist_checkpoint(
        self,
        *,
        training_mode: str,
        curriculum_stage: str,
        policy_path: str | None = None,
        phase: str = "",
        stage_metrics: dict[str, Any] | None = None,
        oos_metrics: dict[str, Any] | None = None,
    ) -> None:
        self._checkpoint_coordinator().persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=curriculum_stage,
            policy_path=policy_path,
            phase=phase,
            stage_metrics=stage_metrics,
            oos_metrics=oos_metrics,
        )



