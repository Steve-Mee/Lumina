"""PPO trainer weight save/load helpers."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any


from lumina_core.logging_utils import (
    get_logger,
    record_model_load_time_monitoring,
    write_ppo_policy_metadata,
)

logger = get_logger("lumina.rl.ppo")


def _sb3_ppo_load(path: str | Path) -> Any | None:
    try:
        from stable_baselines3 import PPO

        return PPO.load(str(path))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:19")
        return None


class PPOTrainerWeightsMixin:
    """Weight get/set/save/load surface."""

    def get_weights(self) -> dict[str, Any] | None:
        model = self._resolve_active_model()
        if model is None or not hasattr(model, "policy"):
            return None
        return dict(model.policy.state_dict())


    def set_weights(self, weights: dict[str, Any]) -> bool:
        """Apply a raw policy state_dict to the active PPO model."""
        model = self._resolve_active_model()
        if model is None or not hasattr(model, "policy"):
            return False
        try:
            model.policy.load_state_dict(dict(weights), strict=True)
            self.engine.set_rl_policy(model)
            return True
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:48")
            return False


    def save_weights(self, policy_path: str | Path | None = None) -> str:
        """Persist active PPO model (.zip) and return output path."""
        model = self._resolve_active_model()
        if model is None:
            raise RuntimeError("Cannot save PPO weights: engine has no active rl_policy_model")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        target = Path(policy_path) if policy_path is not None else (self.model_dir / "lumina_ppo_policy.zip")
        target.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(target))
        try:
            stat = target.stat()
            policy_version = f"ppo-{int(stat.st_mtime)}-{int(stat.st_size)}"
            write_ppo_policy_metadata(
                policy_path=str(target),
                policy_version=policy_version,
                total_training_steps=int(getattr(model, "num_timesteps", 0) or 0),
                status="saved",
            )
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:save_weights_metadata")
        return str(target)


    def load_weights(self, policy_path: str | Path) -> Any | None:
        """Load PPO model from .zip and install as active policy."""
        start = __import__("time").perf_counter()
        model = _sb3_ppo_load(policy_path)
        if model is None:
            record_model_load_time_monitoring(
                model_type="ppo",
                model_path=str(policy_path),
                load_time_sec=__import__("time").perf_counter() - start,
                status="failed",
            )
            return None
        self.engine.set_rl_policy(model)
        elapsed = __import__("time").perf_counter() - start
        record_model_load_time_monitoring(
            model_type="ppo",
            model_path=str(policy_path),
            load_time_sec=elapsed,
            status="loaded",
        )
        try:
            path = Path(policy_path)
            stat = path.stat()
            policy_version = f"ppo-{int(stat.st_mtime)}-{int(stat.st_size)}"
            write_ppo_policy_metadata(
                policy_path=str(path),
                policy_version=policy_version,
                total_training_steps=int(getattr(model, "num_timesteps", 0) or 0),
                last_load_time_sec=float(elapsed),
                status="loaded",
            )
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:load_weights_metadata")
        return model


    def load_policy(self, policy_path: str) -> None:
        try:
            model = self.load_weights(policy_path)
            if model is not None:
                return
            raise RuntimeError("load_weights returned None")
        except Exception as exc:  # obs-space mismatch after Meta-RL expansion or missing file
            logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:200")
            logging.getLogger(__name__).warning(
                "PPO.load failed (obs-space mismatch after Meta-RL expansion or file missing); "
                "engine will fall back to HOLD until retrained. Reason: %s",
                exc,
            )


