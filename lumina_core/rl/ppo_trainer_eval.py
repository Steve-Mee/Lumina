"""PPO trainer evaluation and birth policy helpers."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import Any

import numpy as np

from lumina_core.first_boot_progress import resolve_ppo_progress_interval
from lumina_core.evolution.simulator_data_support import coerce_rl_training_bars
from lumina_core.logging_utils import (
    correlation_id,
    get_logger,
    record_model_load_time_monitoring,
    resolve_monitoring_state_dir,
    write_ppo_policy_metadata,
)
from lumina_core.rl.ppo_callbacks import (
    _extract_policy_entropy,
    _notify_first_boot_ppo_progress,
    _ppo_first_boot_progress_callback,
    _ppo_heartbeat_callbacks,
)
from lumina_core.rl.ppo_device import _resolve_ppo_device, _scale_timesteps_for_device
from lumina_core.rl.ppo_evolution_logger import PPOEvolutionLogger
from lumina_core.rl import RLConfig, RLTradingEnvironment

logger = get_logger("lumina.rl.ppo")


def _sb3_ppo_load(path: str | Path) -> Any | None:
    try:
        from stable_baselines3 import PPO

        return PPO.load(str(path))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:19")
        return None


class PPOTrainerEvalMixin:
    """Eval rollouts, birth policy create/polish, live infer."""

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


    def _resolve_intelligence_tier(self) -> str:
        try:
            from lumina_core.adaptive_intelligence import AdaptiveIntelligenceManager

            tier = str(AdaptiveIntelligenceManager().get_status().tier or "standard").strip().lower()
            if tier in {"high", "standard", "light"}:
                return tier
        except Exception:
            self.logger.debug("ppo.intelligence_tier_fallback", exc_info=True)
        return "standard"


    def _get_training_hyperparams(self, *, birth_phase: bool = False) -> dict[str, Any]:
        """Tier-aware PPO hyperparameters (birth phase uses extra exploration)."""
        tier = self._resolve_intelligence_tier()
        hyperparams: dict[str, Any] = {
            "learning_rate": 3e-4,
            "n_steps": 1024,
            "batch_size": 256,
            "gamma": 0.995,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
            "ent_coef": 0.01,
            "vf_coef": 0.5,
        }
        if tier == "high":
            hyperparams["ent_coef"] = 0.005
            hyperparams["learning_rate"] = 2e-4
        elif tier == "light":
            hyperparams["ent_coef"] = 0.03
            hyperparams["n_steps"] = 512
        if birth_phase:
            hyperparams["ent_coef"] = float(hyperparams["ent_coef"]) * 1.5
        return hyperparams


    def _bootstrap_birth_env(self) -> RLTradingEnvironment:
        """Minimal RL env so SB3 PPO gets valid observation/action spaces during birth init."""
        price = 5000.0
        stub_rows = [
            {
                "timestamp": "",
                "last": price,
                "close": price,
                "bid": price - 0.125,
                "ask": price + 0.125,
                "volume": 100,
            }
            for _ in range(200)
        ]
        return RLTradingEnvironment(self.engine, stub_rows, config=self._build_rl_config())


    def create_fresh_birth_policy(
        self,
        *,
        allow_load_existing: bool = True,
        force_reinit: bool = False,
    ) -> Any:
        """Initialize or reload the PPO policy used by Birth Phase rollouts."""
        if not force_reinit and allow_load_existing:
            default_path = self.model_dir / "lumina_ppo_policy.zip"
            if default_path.is_file():
                loaded = self.load_weights(str(default_path))
                if loaded is not None:
                    self.logger.info(
                        "ppo.birth.load_existing",
                        extra={
                            "event_data": {
                                "event": "ppo.birth.load_existing",
                                "path": str(default_path),
                                "tier": self._resolve_intelligence_tier(),
                            }
                        },
                    )
                    return loaded
            active = self._resolve_active_model()
            if active is not None:
                return active

        from stable_baselines3 import PPO

        hyperparams = self._get_training_hyperparams(birth_phase=True)
        env = self._bootstrap_birth_env()
        model = PPO(
            policy="MlpPolicy",
            env=env,
            verbose=0,
            device=_resolve_ppo_device(),
            **hyperparams,
        )
        self.engine.set_rl_policy(model)
        self.logger.info(
            "ppo.birth.fresh_policy",
            extra={
                "event_data": {
                    "event": "ppo.birth.fresh_policy",
                    "tier": self._resolve_intelligence_tier(),
                    "force_reinit": bool(force_reinit),
                }
            },
        )
        return model


    def save_final_birth_policy(self, path: str) -> None:
        """Persist the active birth policy to the certificate/practice target path."""
        self.save_weights(path)


    def final_birth_polish(self, buffer: Any, *, timesteps: int = 50_000) -> Any:
        """Final birth polish pass over the trajectory buffer."""
        return self.update_from_buffer(
            buffer=buffer,
            timesteps=int(timesteps),
            birth_phase=True,
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
