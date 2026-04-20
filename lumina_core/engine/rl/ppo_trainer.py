# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

from datetime import datetime
import importlib
from typing import Any, Dict

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
        self._full_dna_payload: dict[str, Any] = {
            "hash": self._dna_version,
            "content": "",
            "fitness": 0.0,
            "mutation_rate": 0.0,
            "regime_focus": "neutral",
        }
        ppo_cls, make_vec_env = _load_sb3()

        def _build_env() -> RLTradingEnvironment:
            env = RLTradingEnvironment(context)
            env.set_full_dna_embedding(self._full_dna_payload)
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

    def set_full_dna_embedding(self, dna_payload: dict[str, Any] | Any) -> None:
        payload = dict(dna_payload) if isinstance(dna_payload, dict) else {}
        self._dna_version = str(payload.get("hash") or payload.get("lineage_hash") or self._dna_version or "GENESIS")
        self._full_dna_payload = {
            "hash": self._dna_version,
            "content": str(payload.get("content") or ""),
            "fitness": float(payload.get("fitness", payload.get("fitness_score", 0.0)) or 0.0),
            "mutation_rate": float(payload.get("mutation_rate", 0.0) or 0.0),
            "regime_focus": str(payload.get("regime_focus") or "neutral"),
        }
        try:
            self.env.env_method("set_full_dna_embedding", self._full_dna_payload)
        except Exception:
            pass

    def set_dna_version(self, dna_version: str) -> None:
        """Backward-compatible alias for callers still setting hash only."""
        self.set_full_dna_embedding({"hash": str(dna_version or "GENESIS")})

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
