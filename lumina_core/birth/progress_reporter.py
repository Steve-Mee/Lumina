"""Birth progress writes and operator/milestone notifications."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.progress import merge_birth_progress_extra, write_birth_progress
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.progress_reporter")


class BirthProgressReporter:
    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root)

    def emit_birth_progress(
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
        """Write birth progress; observability failures must not stop training."""
        parts: list[dict[str, Any]] = list(extra_parts or ())
        if extra:
            parts.append(extra)
        merged_extra = merge_birth_progress_extra(*parts)
        call_kwargs: dict[str, Any] = {
            "stage": stage,
            "phase": phase,
            "message": message,
            "progress_pct": progress_pct,
            "cumulative_trades": cumulative_trades,
            "target_trades": target_trades,
            "ppo_steps": ppo_steps,
            "birth_start_time": birth_start_time,
        }
        try:
            write_birth_progress(self.workspace_root, **call_kwargs, **merged_extra)
        except TypeError as exc:
            if "multiple values for keyword argument" not in str(exc):
                logger.warning("birth.progress_write_failed type=%s", exc)
                return
            logger.warning("birth.progress_write_duplicate_kwargs retry: %s", exc)
            try:
                write_birth_progress(
                    self.workspace_root,
                    **call_kwargs,
                    **merge_birth_progress_extra(*parts),
                )
            except Exception as retry_exc:
                logger.warning("birth.progress_write_failed retry: %s", retry_exc)
        except OSError as exc:
            logger.warning("birth.progress_write_failed: %s", exc)
        except Exception as exc:
            logger.warning("birth.progress_write_failed: %s", exc)

    def notify_milestone(self, event: Any) -> None:
        try:
            from lumina_core.notifications.milestone_notifier import notify_milestone

            notify_milestone(event, workspace_root=self.workspace_root)
        except Exception as exc:
            logger.warning("birth.milestone_notify_failed: %s", exc)

    def notify_attention(self, event: Any) -> None:
        try:
            from lumina_core.notifications.operator_notifier import notify_problem

            notify_problem(event, workspace_root=self.workspace_root)
        except Exception as exc:
            logger.warning("birth.attention_notify_failed: %s", exc)

    def notify_history_unavailable(self, detail: str) -> None:
        from lumina_core.notifications.attention_events import birth_history_unavailable_event

        self.notify_attention(birth_history_unavailable_event(detail=detail))