# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

from datetime import datetime
import importlib
import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np

from lumina_core.engine.rl.rl_trading_environment import RLTradingEnvironment
from lumina_core.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


def _load_sb3() -> tuple:
    try:
        ppo_cls = importlib.import_module("stable_baselines3").PPO
        make_vec_env = importlib.import_module("stable_baselines3.common.env_util").make_vec_env
        return ppo_cls, make_vec_env
    except Exception as exc:  # pragma: no cover - depends on optional package install
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/rl/ppo_trainer.py:23")
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
            logger.exception("PPOTrainer failed to propagate DNA embedding to vectorized env")

    def set_dna_version(self, dna_version: str) -> None:
        """Backward-compatible alias for callers still setting hash only."""
        self.set_full_dna_embedding({"hash": str(dna_version or "GENESIS")})

    def train(self, total_timesteps: int = 100000):
        """Nightly training - run na backtest."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] PPO Training started ({total_timesteps} steps)")
        self.model.learn(total_timesteps=total_timesteps, progress_bar=True)
        self.model.save("lumina_ppo_model")
        print("PPO model saved - policy updated")

    def get_weights(self) -> dict[str, Any] | None:
        if not hasattr(self.model, "policy"):
            return None
        return dict(self.model.policy.state_dict())

    def set_weights(self, weights: dict[str, Any]) -> bool:
        try:
            self.model.policy.load_state_dict(dict(weights), strict=True)
            return True
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/rl/ppo_trainer.py:96")
            return False

    def save_weights(self, policy_path: str | Path | None = None) -> str:
        target = Path(policy_path) if policy_path is not None else Path("lumina_ppo_model.zip")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.model.save(str(target))
        return str(target)

    def load_weights(self, policy_path: str | Path) -> Any | None:
        ppo_cls, _ = _load_sb3()
        try:
            loaded = ppo_cls.load(str(policy_path))
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/rl/ppo_trainer.py:109")
            return None
        try:
            self.model.policy.load_state_dict(loaded.policy.state_dict(), strict=True)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/rl/ppo_trainer.py:113")
            return None
        return self.model

    def predict_action(self, obs: np.ndarray) -> Dict[str, float]:
        """Live policy gebruik."""
        action, _ = self.model.predict(obs, deterministic=False)
        return {
            "signal": int(action[0]),
            "qty_pct": float(action[1]),
            "stop_mult": float(action[2]),
            "target_mult": float(action[3]),
        }
