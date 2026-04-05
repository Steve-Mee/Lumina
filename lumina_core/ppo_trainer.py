from __future__ import annotations
# pyright: reportMissingImports=false

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from lumina_core.rl_environment import RLTradingEnvironment


@dataclass(slots=True)
class PPOTrainer:
    """Stable-Baselines3 PPO trainer and live-policy adapter."""

    engine: Any
    model_dir: Path = Path("lumina_agents/ppo")

    def train(
        self,
        simulator_data: list[dict[str, Any]],
        *,
        total_timesteps: int = 200_000,
        policy_path: str | None = None,
    ) -> str:
        from stable_baselines3 import PPO

        self.model_dir.mkdir(parents=True, exist_ok=True)
        env = RLTradingEnvironment(self.engine, simulator_data)
        model = PPO(
            policy="MlpPolicy",
            env=env,
            verbose=0,
            learning_rate=3e-4,
            n_steps=1024,
            batch_size=256,
            gamma=0.995,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.005,
        )
        model.learn(total_timesteps=total_timesteps)

        if not policy_path:
            policy_path = str(self.model_dir / "lumina_ppo_policy.zip")
        model.save(policy_path)
        self.engine.set_rl_policy(model)
        return policy_path

    def train_nightly_on_infinite_simulator(
        self,
        simulator_data: list[dict[str, Any]],
        *,
        timesteps: int = 250_000,
    ) -> str:
        # Infinite Simulator orchestration hook for next step.
        return self.train(simulator_data, total_timesteps=timesteps)

    def load_policy(self, policy_path: str) -> None:
        from stable_baselines3 import PPO

        model = PPO.load(policy_path)
        self.engine.set_rl_policy(model)

    def infer_live_action(self, observation: np.ndarray) -> dict[str, Any]:
        model = getattr(self.engine, "rl_policy_model", None)
        if model is None:
            return {"signal": "HOLD", "confidence": 0.0, "qty": 1, "stop": 0.0, "target": 0.0, "reason": "no-policy"}

        action, _ = model.predict(observation, deterministic=True)
        action_arr = np.asarray(action, dtype=np.float32)
        side_bucket = int(np.clip(np.round(action_arr[0]), 0, 2))
        signal = "HOLD" if side_bucket == 0 else ("BUY" if side_bucket == 1 else "SELL")
        confidence = float(np.clip(np.abs(action_arr[0] - 1.0), 0.0, 1.0))

        qty = max(1, int(1 + np.clip(action_arr[1], 0.0, 1.0) * 9))
        stop_pct = float(np.clip(action_arr[2], 0.001, 0.02))
        target_pct = float(np.clip(action_arr[3], 0.001, 0.05))

        price = float(observation[0]) if observation.size > 0 else 0.0
        if signal == "BUY":
            stop = price * (1.0 - stop_pct)
            target = price * (1.0 + target_pct)
        elif signal == "SELL":
            stop = price * (1.0 + stop_pct)
            target = price * (1.0 - target_pct)
        else:
            stop = 0.0
            target = 0.0

        return {
            "signal": signal,
            "confidence": confidence,
            "qty": qty,
            "stop": stop,
            "target": target,
            "reason": "ppo_policy_live",
        }
