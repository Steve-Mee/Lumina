# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

from datetime import datetime
import importlib
from typing import Dict

import numpy as np

from lumina_core.engine.rl.rl_trading_environment import RLTradingEnvironment
from lumina_core.runtime_context import RuntimeContext


def _load_sb3() -> tuple:
    try:
        ppo_cls = importlib.import_module("stable_baselines3").PPO
        make_vec_env = importlib.import_module("stable_baselines3.common.env_util").make_vec_env
        return ppo_cls, make_vec_env
    except Exception as exc:  # pragma: no cover - depends on optional package install
        raise RuntimeError(
            "stable-baselines3 is required for PPOTrainer. Install with: pip install stable-baselines3"
        ) from exc


class PPOTrainer:
    def __init__(self, context: RuntimeContext):
        self.context = context
        self._dna_version = str(getattr(getattr(context, "engine", None), "active_dna_version", "GENESIS") or "GENESIS")
        ppo_cls, make_vec_env = _load_sb3()

        def _build_env() -> RLTradingEnvironment:
            env = RLTradingEnvironment(context)
            env.set_dna_version(self._dna_version)
            return env

        self.env = make_vec_env(_build_env, n_envs=4)
        self.model = ppo_cls(
            "MlpPolicy",
            self.env,
            verbose=1,
            learning_rate=3e-4,
            n_steps=2048,
            batch_size=64,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            tensorboard_log="./lumina_rl_logs/",
        )

    def set_dna_version(self, dna_version: str) -> None:
        self._dna_version = str(dna_version or "GENESIS")

    def train(self, total_timesteps: int = 100000):
        """Nightly training - run na backtest."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] PPO Training started ({total_timesteps} steps)")
        self.model.learn(total_timesteps=total_timesteps, progress_bar=True)
        self.model.save("lumina_ppo_model")
        print("PPO model saved - policy updated")

    def predict_action(self, obs: np.ndarray) -> Dict[str, float]:
        """Live policy gebruik."""
        action, _ = self.model.predict(obs, deterministic=False)
        return {
            "signal": int(action[0]),
            "qty_pct": float(action[1]),
            "stop_mult": float(action[2]),
            "target_mult": float(action[3]),
        }
