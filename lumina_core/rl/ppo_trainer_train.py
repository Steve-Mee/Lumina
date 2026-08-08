"""PPO trainer training loops."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from typing import Any


from lumina_core.first_boot_progress import resolve_ppo_progress_interval
from lumina_core.evolution.simulator_data_support import coerce_rl_training_bars
from lumina_core.logging_utils import (
    correlation_id,
    get_logger,
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
from lumina_core.rl import RLTradingEnvironment

logger = get_logger("lumina.rl.ppo")


def _sb3_ppo_load(path: str | Path) -> Any | None:
    try:
        from stable_baselines3 import PPO

        return PPO.load(str(path))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/ppo_trainer.py:19")
        return None


class PPOTrainerTrainMixin:
    """train / update_from_buffer / nightly."""

    def train(
        self,
        simulator_data: list[dict[str, Any]],
        *,
        total_timesteps: int = 200_000,
        policy_path: str | None = None,
        dna_hash: str | None = None,
        report_first_boot_progress: bool = False,
        ppo_progress_interval: int | None = None,
        birth_phase: bool = False,
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
            **self._get_training_hyperparams(birth_phase=birth_phase),
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
        # Birth curriculum bursts are often < 5000 steps; cap interval so JSONL + entropy emit.
        log_interval = min(5000, max(1, int(total_timesteps)))
        evolution_logger = PPOEvolutionLogger(
            log_path=str(resolve_monitoring_state_dir() / "ppo_training_log.jsonl"),
            log_interval=log_interval,
        )
        callbacks.append(evolution_logger)
        learn_kw: dict[str, Any] = {}
        if callbacks:
            learn_kw["callback"] = callbacks
        model.learn(total_timesteps=total_timesteps, **learn_kw)
        self.last_policy_entropy = _extract_policy_entropy(model, evolution_logger)
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


    def update_from_buffer(
        self,
        *,
        buffer: Any,
        timesteps: int = 25_000,
        birth_phase: bool = False,
    ) -> Any:
        """Train PPO from trajectory snapshots and return latest active model."""
        rows = self._trajectory_buffer_to_rows(buffer)
        active = self._resolve_active_model()
        if len(rows) < 80:
            self.logger.info(
                "ppo.update.skipped_insufficient_rows",
                extra={"event_data": {"rows": len(rows), "timesteps": int(timesteps)}},
            )
            return active
        self.logger.info(
            "ppo.update.start",
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
            birth_phase=birth_phase,
        )
        updated = self._resolve_active_model()
        if updated is None:
            raise RuntimeError("update_from_buffer completed without an active PPO policy")
        return updated


