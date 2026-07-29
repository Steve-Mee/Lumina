"""PPO training callbacks and first-boot progress helpers (Wave B PR-B4)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.ppo_evolution_logger import PPOEvolutionLogger

logger = get_logger("lumina.rl.ppo")

def _extract_policy_entropy(model: Any, evolution_logger: PPOEvolutionLogger) -> float | None:
    """Best-effort entropy after learn() — logger flush first, else SB3 train logs."""
    cached = getattr(evolution_logger, "last_entropy", None)
    if cached is not None:
        try:
            return float(cached)
        except (TypeError, ValueError):
            pass
    logger_obj = getattr(model, "logger", None)
    raw = getattr(logger_obj, "name_to_value", {}) if logger_obj is not None else {}
    logs: dict[str, float] = {}
    for key, value in (raw or {}).items():
        if value is None:
            continue
        try:
            logs[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    if not logs:
        return None
    try:
        return float(PPOEvolutionLogger._resolve_entropy(logs))
    except (TypeError, ValueError):
        return None


def _notify_first_boot_ppo_progress(
    *,
    steps: int,
    total_timesteps: int,
    elapsed_sec: float,
) -> None:
    """Write incremental PPO progress into first_boot_progress.json."""
    from lumina_core.engine.runtime_entrypoint import _write_first_boot_progress

    total = max(1, int(total_timesteps))
    current = max(0, min(int(steps), total))
    ratio = float(current) / float(total)
    ppo_pct = max(0.0, min(100.0, ratio * 100.0))
    overall_pct = max(68.0, min(95.0, 68.0 + (27.0 * ratio)))
    eta_minutes: float | None = None
    if current > 0 and elapsed_sec > 0:
        steps_per_sec = float(current) / max(1e-6, float(elapsed_sec))
        remaining_steps = max(0, total - current)
        if steps_per_sec > 0:
            eta_minutes = round((float(remaining_steps) / steps_per_sec) / 60.0, 1)
    _write_first_boot_progress(
        "training_running",
        f"PPO training: {current:,}/{total:,} timesteps in huidige batch ({ppo_pct:.1f}%)",
        phase="ppo_training",
        ppo_batch_steps=current,
        ppo_batch_total=total,
        ppo_batch_progress_pct=round(ppo_pct, 2),
        ppo_progress_pct=round(ppo_pct, 2),
        ppo_elapsed_sec=round(float(elapsed_sec), 1),
        ppo_eta_minutes=eta_minutes,
        progress_pct=round(overall_pct, 2),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _ppo_heartbeat_callbacks(*, log_every_timesteps: int = 5_000) -> list[Any]:
    """Periodic INFO logs during ``model.learn`` (SB3 uses ``verbose=0`` otherwise — looks hung)."""
    try:
        from stable_baselines3.common.callbacks import BaseCallback
    except ImportError:
        return []

    interval = max(5000, int(log_every_timesteps))

    class _PPOTrainHeartbeat(BaseCallback):
        def __init__(self) -> None:
            super().__init__(verbose=0)
            self._next_log_at = interval
            self._t0 = __import__("time").time()

        def _on_step(self) -> bool:
            ts = int(getattr(self, "num_timesteps", 0) or 0)
            if ts >= self._next_log_at:
                elapsed = __import__("time").time() - self._t0
                logger.info(
                    "ppo.train.progress",
                    extra={
                        "event_data": {
                            "event": "ppo.train.progress",
                            "timesteps": ts,
                            "elapsed_sec": round(elapsed, 1),
                            "next_milestone": self._next_log_at,
                        }
                    },
                )
                while self._next_log_at <= ts:
                    self._next_log_at += interval
            return True

    return [_PPOTrainHeartbeat()]


def _ppo_first_boot_progress_callback(
    *,
    total_timesteps: int,
    report_interval: int,
) -> Any | None:
    try:
        from stable_baselines3.common.callbacks import BaseCallback
    except ImportError:
        return None

    interval = max(1000, int(report_interval))
    total = max(1, int(total_timesteps))

    class _FirstBootPPOProgressCallback(BaseCallback):
        def __init__(self) -> None:
            super().__init__(verbose=0)
            self._next_report_at = interval
            self._started_at = __import__("time").time()

        def _on_step(self) -> bool:
            ts = int(getattr(self, "num_timesteps", 0) or 0)
            if ts >= self._next_report_at:
                elapsed = __import__("time").time() - self._started_at
                try:
                    _notify_first_boot_ppo_progress(
                        steps=ts,
                        total_timesteps=total,
                        elapsed_sec=elapsed,
                    )
                except Exception:
                    logger.warning("ppo.first_boot_progress_callback_failed", exc_info=True)
                while self._next_report_at <= ts:
                    self._next_report_at += interval
            return True

    return _FirstBootPPOProgressCallback()


__all__ = [
    "_extract_policy_entropy",
    "_notify_first_boot_ppo_progress",
    "_ppo_first_boot_progress_callback",
    "_ppo_heartbeat_callbacks",
]
