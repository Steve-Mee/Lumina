"""PPO trainer ops mixin (Wave E split: weights / eval / train)."""
from __future__ import annotations

from lumina_core.rl.ppo_trainer_eval import PPOTrainerEvalMixin
from lumina_core.rl.ppo_trainer_train import PPOTrainerTrainMixin
from lumina_core.rl.ppo_trainer_weights import PPOTrainerWeightsMixin

__all__ = ["PPOTrainerOpsMixin"]


class PPOTrainerOpsMixin(
    PPOTrainerWeightsMixin,
    PPOTrainerEvalMixin,
    PPOTrainerTrainMixin,
):
    """Combined ops surface for PPOTrainer."""
