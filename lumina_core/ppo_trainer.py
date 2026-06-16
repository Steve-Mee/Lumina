from __future__ import annotations
# pyright: reportMissingImports=false

from dataclasses import asdict, dataclass, field
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
from lumina_core.ppo_evolution_logger import PPOEvolutionLogger
from lumina_core.rl import RLConfig, RLTradingEnvironment

logger = get_logger("lumina.rl.ppo")


def _resolve_ppo_device() -> str:
    """Select CUDA when available; CPU otherwise (BRO PR-N)."""
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def _scale_timesteps_for_device(timesteps: int) -> int:
    device = _resolve_ppo_device()
    if device == "cuda":
        return max(int(timesteps), int(timesteps) * 2)
    return int(timesteps)


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
    logger: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger = logger

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
        report_first_boot_progress: bool = False,
        ppo_progress_interval: int | None = None,
    ) -> str:
        from stable_baselines3 import PPO

        train_id = f"ppo:{dna_hash or 'nightly'}"
        with correlation_id(train_id):
            logger.info(
                "ppo.train.start",
                extra={
                    "event_data": {
                        "event": "ppo.train.start",
                        "total_timesteps": int(total_timesteps),
                        "dna_hash": str(dna_hash or ""),
                    }
                },
            )
        started = __import__("time").time()
        if report_first_boot_progress:
            try:
                _notify_first_boot_ppo_progress(
                    steps=0,
                    total_timesteps=int(total_timesteps),
                    elapsed_sec=0.0,
                )
            except Exception:
                logger.warning("ppo.first_boot_progress_initial_write_failed", exc_info=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        bars = coerce_rl_training_bars(self.engine, simulator_data, nightly_context=None)
        rl_cfg = self._build_rl_config()
        logger.debug(
            "ppo.train.config",
            extra={
                "event_data": {
                    "event": "ppo.train.config",
                    "bars": len(bars),
                    "env_config": asdict(rl_cfg),
                }
            },
        )
        env = RLTradingEnvironment(self.engine, bars, config=rl_cfg)
        if dna_hash:
            env.set_dna_hash(dna_hash)
        model = PPO(
            policy="MlpPolicy",
            env=env,
            verbose=0,
            device=_resolve_ppo_device(),
            learning_rate=3e-4,
            n_steps=1024,
            batch_size=256,
            gamma=0.995,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.005,
        )
        heartbeat = _ppo_heartbeat_callbacks()
        callbacks: list[Any] = list(heartbeat)
        if report_first_boot_progress:
            interval = (
                int(ppo_progress_interval)
                if ppo_progress_interval is not None
                else resolve_ppo_progress_interval(None)
            )
            fb_cb = _ppo_first_boot_progress_callback(
                total_timesteps=int(total_timesteps),
                report_interval=interval,
            )
            if fb_cb is not None:
                callbacks.append(fb_cb)
        evolution_logger = PPOEvolutionLogger(
            log_path=str(resolve_monitoring_state_dir() / "ppo_training_log.jsonl"),
            log_interval=5000,
        )
        callbacks.append(evolution_logger)
        learn_kw: dict[str, Any] = {}
        if callbacks:
            learn_kw["callback"] = callbacks
        model.learn(total_timesteps=total_timesteps, **learn_kw)
        if report_first_boot_progress:
            elapsed = __import__("time").time() - started
            _notify_first_boot_ppo_progress(
                steps=int(total_timesteps),
                total_timesteps=int(total_timesteps),
                elapsed_sec=float(elapsed),
            )

        if not policy_path:
            policy_path = str(self.model_dir / "lumina_ppo_policy.zip")
        model.save(policy_path)
        self.engine.set_rl_policy(model)
        logger.info(
            "ppo.train.complete",
            extra={
                "event_data": {
                    "event": "ppo.train.complete",
                    "model_path": str(policy_path),
                    "training_time_sec": round(__import__("time").time() - started, 2),
                }
            },
        )
        try:
            target = Path(policy_path)
            stat = target.stat()
            policy_version = f"ppo-{int(stat.st_mtime)}-{int(stat.st_size)}"
            write_ppo_policy_metadata(
                policy_path=str(policy_path),
                policy_version=policy_version,
                total_training_steps=int(total_timesteps),
                training_time_sec=round(__import__("time").time() - started, 2),
                status="trained",
            )
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:train_metadata")
        return policy_path

    def train_nightly_on_infinite_simulator(
        self,
        simulator_data: list[dict[str, Any]],
        *,
        timesteps: int = 250_000,
        dna_hash: str | None = None,
        report_first_boot_progress: bool = False,
        ppo_progress_interval: int | None = None,
    ) -> str:
        # Infinite Simulator orchestration hook for next step.
        return self.train(
            simulator_data,
            total_timesteps=timesteps,
            dna_hash=dna_hash,
            report_first_boot_progress=report_first_boot_progress,
            ppo_progress_interval=ppo_progress_interval,
        )

    def _trajectory_buffer_to_rows(self, buffer: Any) -> list[dict[str, Any]]:
        trajectories = list(getattr(buffer, "trajectories", []) or [])
        rows: list[dict[str, Any]] = []

        def _price_from_obs(obs: Any) -> float:
            if not isinstance(obs, dict):
                return 0.0
            try:
                direct = float(obs.get("price", 0.0) or 0.0)
            except (TypeError, ValueError):
                direct = 0.0
            if direct > 0.0:
                return direct
            vector = obs.get("vector")
            if isinstance(vector, list) and vector:
                try:
                    return float(vector[0])
                except (TypeError, ValueError, IndexError):
                    return 0.0
            return 0.0

        for idx, item in enumerate(trajectories):
            if not isinstance(item, dict):
                continue
            obs = item.get("observation")
            next_obs = item.get("next_observation")
            price = _price_from_obs(obs)
            if price <= 0.0:
                price = _price_from_obs(next_obs)
            if price <= 0.0:
                continue
            ts = datetime.now(timezone.utc) - timedelta(seconds=max(0, len(trajectories) - idx))
            rows.append(
                {
                    "timestamp": ts.isoformat(),
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "last": price,
                    "volume": 1,
                }
            )
        return rows

    def _birth_bootstrap_rows(self, *, count: int = 256) -> list[dict[str, Any]]:
        # BIRTH ENGINE 2026-05-17
        out: list[dict[str, Any]] = []
        base = 5000.0
        bar_count = max(80, int(count))
        base_ts = datetime.now(timezone.utc)
        for idx in range(bar_count):
            price = float(base + (idx * 0.25))
            ts = base_ts - timedelta(minutes=bar_count - idx)
            out.append(
                {
                    "timestamp": ts.isoformat(),
                    "open": price,
                    "high": price + 0.25,
                    "low": price - 0.25,
                    "close": price,
                    "last": price,
                    "volume": 10,
                }
            )
        return out

    def create_fresh_birth_policy(self, *, allow_load_existing: bool = True) -> Any:
        """Ensure an active policy object exists for the birth phase loop."""
        # BIRTH ENGINE 2026-05-17
        active = self._resolve_active_model()
        if active is not None:
            self.logger.info("ppo.birth.policy.reuse_active")
            return active
        default_path = self.model_dir / "lumina_ppo_policy.zip"
        if allow_load_existing and default_path.exists():
            loaded = self.load_weights(default_path)
            if loaded is not None:
                self.logger.info("ppo.birth.policy.loaded_existing", extra={"event_data": {"path": str(default_path)}})
                return loaded
        # Create a minimal valid PPO model so birth loop always has concrete policy state.
        bootstrap_rows = self._birth_bootstrap_rows(count=256)
        self.train(
            bootstrap_rows,
            total_timesteps=1_024,
            report_first_boot_progress=False,
        )
        created = self._resolve_active_model()
        if created is None:
            raise RuntimeError("create_fresh_birth_policy failed to initialize PPO model")
        self.logger.info("ppo.birth.policy.initialized_bootstrap")
        return created

    def update_from_buffer(
        self,
        *,
        buffer: Any,
        timesteps: int = 25_000,
        birth_phase: bool = True,
    ) -> Any:
        """Train PPO from trajectory snapshots and return latest active model."""
        # BIRTH ENGINE 2026-05-17
        rows = self._trajectory_buffer_to_rows(buffer)
        active = self._resolve_active_model()
        if active is None:
            active = self.create_fresh_birth_policy()
        if len(rows) < 80:
            self.logger.info(
                "ppo.birth.update.skipped_insufficient_rows",
                extra={"event_data": {"rows": len(rows), "timesteps": int(timesteps)}},
            )
            return active
        self.logger.info(
            "ppo.birth.update.start",
            extra={
                "event_data": {
                    "rows": len(rows),
                    "timesteps": int(timesteps),
                    "birth_phase": bool(birth_phase),
                }
            },
        )
        self.train(
            rows,
            total_timesteps=max(1_000, _scale_timesteps_for_device(int(timesteps))),
            report_first_boot_progress=bool(birth_phase),
        )
        updated = self._resolve_active_model()
        if updated is None:
            raise RuntimeError("update_from_buffer completed without an active PPO policy")
        return updated

    def final_birth_polish(self, buffer: Any) -> None:
        # BIRTH ENGINE 2026-05-17
        self.logger.info("ppo.birth.polish.start")
        self.update_from_buffer(buffer=buffer, timesteps=50_000, birth_phase=False)

    def save_intermediate_policy(self, trade_count: int) -> None:
        # BIRTH ENGINE 2026-05-17
        path = self.model_dir / f"lumina_ppo_policy_birth_{max(0, int(trade_count))}.zip"
        try:
            self.save_weights(path)
            self.logger.info("ppo.birth.policy.intermediate_saved", extra={"event_data": {"path": str(path)}})
        except Exception:
            self.logger.warning("ppo.birth.policy.intermediate_save_failed", exc_info=True)

    def save_final_birth_policy(self, path: str | None = None) -> None:
        # BIRTH ENGINE 2026-05-17
        target = Path(path) if path else (self.model_dir / "lumina_ppo_policy.zip")
        if self._resolve_active_model() is None and target.exists():
            self.load_weights(target)
        if self._resolve_active_model() is None:
            self.create_fresh_birth_policy()
        self.save_weights(target)
        self.logger.info("ppo.birth.policy.final_saved", extra={"event_data": {"path": str(target)}})

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
