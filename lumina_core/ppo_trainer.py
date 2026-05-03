from __future__ import annotations
# pyright: reportMissingImports=false

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

import numpy as np

from lumina_core.evolution.simulator_data_support import coerce_rl_training_bars
from lumina_core.rl import RLConfig, RLTradingEnvironment


def _sb3_ppo_load(path: str | Path) -> Any | None:
    try:
        from stable_baselines3 import PPO

        return PPO.load(str(path))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:19")
        return None


@dataclass(slots=True)
class PPOTrainer:
    """Stable-Baselines3 PPO trainer and live-policy adapter."""

    engine: Any
    model_dir: Path = Path("lumina_agents/ppo")

    def _resolve_active_model(self) -> Any | None:
        return getattr(self.engine, "rl_policy_model", None)

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
        return str(target)

    def load_weights(self, policy_path: str | Path) -> Any | None:
        """Load PPO model from .zip and install as active policy."""
        model = _sb3_ppo_load(policy_path)
        if model is None:
            return None
        self.engine.set_rl_policy(model)
        return model

    def evaluate_policy_zip_rollouts(
        self,
        policy_path: str | Path,
        simulator_data: list[dict[str, Any]],
        *,
        dna_hash: str | None = None,
        shadow_max_steps: int = 256,
        backtest_max_steps: int = 2048,
    ) -> dict[str, Any]:
        """Shadow + backtest rollouts on RLTradingEnvironment without swapping the engine's active policy.

        Returned Gym reward sums and equity deltas are RL-environment signals only,
        not broker ``economic_pnl``.
        """
        bad = {
            "ok": False,
            "shadow_equity_delta": 0.0,
            "backtest_fitness": float("-inf"),
            "shadow_total_training_reward": 0.0,
            "backtest_equity_delta": 0.0,
        }
        try:
            bars = coerce_rl_training_bars(self.engine, simulator_data, nightly_context=None)
        except RuntimeError:
            return dict(bad)

        model = _sb3_ppo_load(policy_path)
        if model is None:
            return dict(bad)

        cfg = self._build_rl_config()

        def _segment(max_steps: int) -> tuple[float, float]:
            env = RLTradingEnvironment(self.engine, bars, config=cfg)
            if dna_hash:
                env.set_dna_hash(str(dna_hash))
            obs, _ = env.reset()
            initial_equity = float(getattr(env, "_initial_equity", 50000.0) or 50000.0)
            total_reward = 0.0
            last_equity = initial_equity
            cap = max(1, min(int(max_steps), int(cfg.max_steps)))
            for _ in range(cap):
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += float(reward)
                if isinstance(info, dict) and "equity" in info:
                    last_equity = float(info.get("equity") or last_equity)
                if terminated or truncated:
                    break
            return total_reward, last_equity - initial_equity

        sh_r, sh_eq_delta = _segment(shadow_max_steps)
        bt_r, bt_eq_delta = _segment(backtest_max_steps)
        backtest_fitness = float(bt_r) + 1e-6 * float(bt_eq_delta)

        return {
            "ok": True,
            "shadow_equity_delta": float(sh_eq_delta),
            "shadow_total_training_reward": float(sh_r),
            "backtest_fitness": float(backtest_fitness),
            "backtest_equity_delta": float(bt_eq_delta),
        }

    def _build_rl_config(self) -> RLConfig:
        """LIVING ORGANISM v51: Build environment config from risk settings."""
        risk_cfg = getattr(getattr(self.engine, "config", None), "risk_controller", {})
        risk_cfg = risk_cfg if isinstance(risk_cfg, dict) else {}
        trade_mode = str(getattr(getattr(self.engine, "config", None), "trade_mode", "sim") or "sim").strip().lower()
        return RLConfig(
            slippage_points=float(risk_cfg.get("slippage_base_points", 0.125) or 0.125),
            slippage_sigma=float(risk_cfg.get("slippage_sigma", 0.5) or 0.5),
            slippage_volatility_factor=float(risk_cfg.get("slippage_volatility_factor", 1.0) or 1.0),
            commission_per_side_usd=float(risk_cfg.get("commission_per_side_usd", 1.29) or 1.29),
            exchange_fee_per_side_usd=float(risk_cfg.get("exchange_fee_per_side_usd", 0.35) or 0.35),
            clearing_fee_per_side_usd=float(risk_cfg.get("clearing_fee_per_side_usd", 0.10) or 0.10),
            nfa_fee_per_side_usd=float(risk_cfg.get("nfa_fee_per_side_usd", 0.02) or 0.02),
            real_safety_threshold_usd=float(risk_cfg.get("real_capital_safety_threshold_usd", 1000.0) or 1000.0),
            real_safety_threshold_ratio=float(risk_cfg.get("real_capital_safety_threshold_ratio", 0.90) or 0.90),
            sim_var_penalty_coeff=float(risk_cfg.get("sim_var_penalty_coeff", 0.04) or 0.04),
            sim_es_penalty_coeff=float(risk_cfg.get("sim_es_penalty_coeff", 0.06) or 0.06),
            trade_mode=trade_mode,
        )

    def train(
        self,
        simulator_data: list[dict[str, Any]],
        *,
        total_timesteps: int = 200_000,
        policy_path: str | None = None,
        dna_hash: str | None = None,
    ) -> str:
        from stable_baselines3 import PPO

        self.model_dir.mkdir(parents=True, exist_ok=True)
        bars = coerce_rl_training_bars(self.engine, simulator_data, nightly_context=None)
        env = RLTradingEnvironment(self.engine, bars, config=self._build_rl_config())
        if dna_hash:
            env.set_dna_hash(dna_hash)
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
        dna_hash: str | None = None,
    ) -> str:
        # Infinite Simulator orchestration hook for next step.
        return self.train(simulator_data, total_timesteps=timesteps, dna_hash=dna_hash)

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
