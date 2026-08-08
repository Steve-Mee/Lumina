from __future__ import annotations
# pyright: reportMissingImports=false

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.rl.ppo_callbacks import (
    _notify_first_boot_ppo_progress,
)
from lumina_core.rl.ppo_device import _resolve_ppo_device, _scale_timesteps_for_device
from lumina_core.rl.ppo_trainer_ops import PPOTrainerOpsMixin

logger = get_logger("lumina.rl.ppo")

# Public / test re-exports (behavior-preserving import surface).
__all__ = [
    "PPOTrainer",
    "_notify_first_boot_ppo_progress",
    "_resolve_ppo_device",
    "_scale_timesteps_for_device",
]


@dataclass(slots=True)
class PPOTrainer(PPOTrainerOpsMixin):
    """Stable-Baselines3 PPO trainer and live-policy adapter."""

    engine: Any
    model_dir: Path = Path("lumina_agents/ppo")
    logger: Any = field(init=False, repr=False)
    last_policy_entropy: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logger
        self.last_policy_entropy = None

    def _resolve_active_model(self) -> Any | None:
        return getattr(self.engine, "rl_policy_model", None)
