"""Birth Phase v2 orchestrator (ADR-0012/0013/0014)."""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_certificate import (
    build_certificate_from_eval,
    certificate_path,
    write_certificate,
)
from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.checkpoint import (
    can_resume_checkpoint,
    clear_checkpoint,
    load_checkpoint_state,
    save_checkpoint,
)
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.config import load_birth_v2_config
from lumina_core.birth.curriculum import (
    CurriculumStage,
    evaluate_stage_pass,
    filter_ticks_for_stage,
    ordered_stages,
    stage_trade_target,
)
from lumina_core.birth.history_loader import load_historical_ticks
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim, real_data_percentage
from lumina_core.birth.dna_handoff import register_birth_gen0_dna
from lumina_core.birth.bible_meta import update_bible_after_birth
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


@dataclass(slots=True)
class TrajectoryBuffer:
    capacity: int = 500_000
    trajectories: list[dict[str, Any]] = field(default_factory=list)
    priorities: list[float] = field(default_factory=list)

    def add(self, trajectory: dict[str, Any], priority: float = 1.0) -> None:
        if len(self.trajectories) >= self.capacity:
            self.trajectories.pop(0)
            self.priorities.pop(0)
        self.trajectories.append(trajectory)
        self.priorities.append(priority)

    def sample(self, batch_size: int) -> list[dict[str, Any]]:
        if not self.trajectories:
            return []
        import numpy as np

        idx = np.random.choice(len(self.trajectories), size=min(batch_size, len(self.trajectories)), replace=False)
        return [self.trajectories[int(i)] for i in idx]

    def __len__(self) -> int:
        return len(self.trajectories)

    def clear(self) -> None:
        self.trajectories.clear()
        self.priorities.clear()


class BirthPhaseEngineV2:
    def __init__(
        self,
        runtime: Any = None,
        ppo_trainer: Any = None,
        market_data_service: Any = None,
        config: dict[str, Any] | None = None,
        workspace_root: str | Path = Path.cwd(),
        stop_event: threading.Event | None = None,
    ) -> None:
        self.runtime = runtime
        self.ppo_trainer = ppo_trainer
        self.market_data_service = market_data_service
        self.config = config or {}
        self.workspace_root = Path(workspace_root)
        self.stop_event = stop_event
        self.birth_config = load_birth_v2_config(self.workspace_root)
        self.cumulative_trades = 0
        self.ppo_steps = 0
        self.birth_start_time = 0.0
        self.buffer = TrajectoryBuffer()
        self.current_policy: Any = None
        self._stages_passed: list[str] = []
        self._real_data_pct = 0.0
        event_bus = getattr(runtime, "event_bus", None)
        self._constitution_guard = BirthConstitutionGuard(event_bus=event_bus, mode="birth")

        self.completion_flag_path = self.workspace_root / "state" / "lumina_birth_completed.flag"
        self.legacy_completion_flag_path = self.workspace_root / "state" / "first_boot_completed.flag"
        self.final_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
        self.practice_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy_practice.zip"
        self.pause_flag_path = self.workspace_root / "state" / "first_boot_pause_requested"
        self.practice_completed_flag_path = self.workspace_root / "state" / "lumina_birth_practice_completed.flag"

    def _stop_requested(self) -> bool:
        if self.stop_event is not None and self.stop_event.is_set():
            return True
        return self.pause_flag_path.exists()

    def _create_birth_policy(self, *, allow_load_existing: bool, policy_path: str | None = None) -> Any:
        create = getattr(self.ppo_trainer, "create_fresh_birth_policy", None)
        if not callable(create):
            raise RuntimeError("PPO trainer missing create_fresh_birth_policy")
        resolved_path = str(policy_path or "").strip()
        if resolved_path:
            candidate = Path(resolved_path)
            if candidate.is_file():
                load_policy = getattr(self.ppo_trainer, "load_policy", None)
                if callable(load_policy):
                    load_policy(resolved_path)
                active = getattr(self.ppo_trainer, "_resolve_active_model", None)
                if callable(active):
                    loaded = active()
                    if loaded is not None:
                        return loaded
                load_weights = getattr(self.ppo_trainer, "load_weights", None)
                if callable(load_weights):
                    loaded = load_weights(resolved_path)
                    if loaded is not None:
                        return loaded
        try:
            return create(allow_load_existing=bool(allow_load_existing))
        except TypeError:
            return create()

    def _generate_synthetic_ticks(self, n_ticks: int, *, start_price: float) -> list[dict[str, Any]]:
        rng = random.Random(51)
        price = max(100.0, float(start_price))
        out: list[dict[str, Any]] = []
        for i in range(max(1, n_ticks)):
            shock = rng.gauss(0.0, 0.0016)
            price = max(10.0, price * (1.0 + shock))
            out.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "last": float(price),
                    "close": float(price),
                    "bid": float(price - 0.125),
                    "ask": float(price + 0.125),
                    "volume": 1000,
                    "regime": "SYNTHETIC",
                    "imbalance": 1.0,
                    "source": "synthetic",
                    "bar_index": i,
                }
            )
        return out

    def run_birth_phase(
        self,
        target_trades: int | None = None,
        max_real_days: int = 365,
        prefer_real_data_only: bool = True,
        chunk_size: int = 50_000,
        ppo_update_timesteps: int = 25_000,
        force: bool = False,
        practice_mode: bool = False,
        reuse_existing_policy: bool | None = None,
    ) -> dict[str, Any]:
        _ = (target_trades, chunk_size, force)
        cfg = self.birth_config
        training_mode = "practice" if practice_mode else "certified"
        max_days = max(30, min(3650, int(max_real_days or cfg.max_real_days)))
        prefer_real = bool(prefer_real_data_only if prefer_real_data_only is not None else cfg.prefer_real_data_only)
        ppo_steps_per_update = max(1000, int(ppo_update_timesteps or cfg.ppo_update_timesteps))
        self.birth_start_time = time.time()
        self._stages_passed = []
        self.cumulative_trades = 0
        self.ppo_steps = 0
        self.buffer.clear()
        self._constitution_guard.reset()

        completion_flags = (self.completion_flag_path, self.legacy_completion_flag_path)
        resume = can_resume_checkpoint(
            self.workspace_root,
            training_mode=training_mode,
            completion_flag_paths=completion_flags,
        ) and not force
        resume_policy_path = ""
        if resume:
            state = load_checkpoint_state(self.workspace_root)
            self.cumulative_trades = int(state.get("cumulative_trades", 0) or 0)
            self.ppo_steps = int(state.get("ppo_steps", 0) or 0)
            self._stages_passed = list(state.get("stages_passed") or [])
            resume_policy_path = str(state.get("policy_path", "") or "")

        allow_load = resume if reuse_existing_policy is None else bool(reuse_existing_policy)
        if resume_policy_path and Path(resume_policy_path).is_file():
            allow_load = True

        write_birth_progress(
            self.workspace_root,
            stage="detected",
            phase="detected",
            message="Birth Phase v2 gestart.",
            progress_pct=5.0,
            cumulative_trades=0,
            target_trades=cfg.trade_budget_cap,
            ppo_steps=0,
            birth_start_time=self.birth_start_time,
            training_mode=training_mode,
            resumed=resume,
        )

        ticks = load_historical_ticks(
            market_data_service=self.market_data_service,
            runtime=self.runtime,
            days_back=max_days,
            limit=None,
        )
        if not ticks and not prefer_real:
            ticks = self._generate_synthetic_ticks(max(20_000, max_days * 1000), start_price=5000.0)
        elif not ticks and prefer_real and practice_mode:
            ticks = self._generate_synthetic_ticks(20_000, start_price=5000.0)
        elif not ticks:
            write_birth_progress(
                self.workspace_root,
                stage="history_unavailable",
                phase="loading_history_failed",
                message="Geen historische data beschikbaar.",
                progress_pct=100.0,
                cumulative_trades=0,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=self.birth_start_time,
                retryable=True,
            )
            return {"status": "history_unavailable", "total_trades": 0, "ppo_steps": 0, "training_mode": "certified"}

        ticks = enrich_ticks_for_sim(ticks)
        self._real_data_pct = real_data_percentage(ticks)
        split = purged_train_holdout_split(ticks, holdout_pct=cfg.holdout_pct)

        write_birth_progress(
            self.workspace_root,
            stage="historical_loaded",
            phase="ticks_ready",
            message=f"Data geladen: {len(ticks):,} ticks, holdout {split.holdout_days} dagen.",
            progress_pct=20.0,
            cumulative_trades=0,
            target_trades=cfg.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            actual_real_days_loaded=max(1, len(ticks) // 450),
            real_data_pct=self._real_data_pct,
        )

        self.current_policy = self._create_birth_policy(
            allow_load_existing=allow_load and resume,
            policy_path=resume_policy_path or None,
        )
        total_stages = len(ordered_stages())
        stage_index = 0

        for stage in ordered_stages():
            if self._stop_requested():
                policy_hint = str(self.final_policy_path)
                if self.final_policy_path.is_file():
                    policy_hint = str(self.final_policy_path)
                save_checkpoint(
                    self.workspace_root,
                    cumulative_trades=self.cumulative_trades,
                    ppo_steps=self.ppo_steps,
                    training_mode=training_mode,
                    stages_passed=self._stages_passed,
                    curriculum_stage=stage.value,
                    policy_path=policy_hint,
                )
                return self._paused_result()

            if stage == CurriculumStage.STAGE4_POLISH:
                break

            if stage.value in self._stages_passed:
                stage_index += 1
                continue

            stage_ticks = filter_ticks_for_stage(stage, split.train)
            if not stage_ticks:
                stage_ticks = list(split.train)
            target = stage_trade_target(stage, cfg.curriculum)
            self._constitution_guard.reset()

            write_birth_progress(
                self.workspace_root,
                stage="training_running",
                phase="curriculum_stage",
                message=f"Curriculum {stage.value}: doel {target:,} trades.",
                progress_pct=20.0 + (stage_index / total_stages) * 60.0,
                cumulative_trades=self.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                ppo_steps=self.ppo_steps,
                birth_start_time=self.birth_start_time,
                curriculum_stage=stage.value,
            )

            rollout = run_policy_rollout(
                runtime=self.runtime,
                data=stage_ticks,
                policy=self.current_policy,
                target_trades=target,
                workspace_root=self.workspace_root,
                constitution_guard=self._constitution_guard,
            )
            self.cumulative_trades += rollout.trades
            for traj in rollout.trajectories:
                self.buffer.add(traj, priority=1.0 + min(10.0, abs(float(traj.get("reward", 0.0)))))

            if len(self.buffer) >= 256:
                self.current_policy = self.ppo_trainer.update_from_buffer(
                    buffer=self.buffer,
                    timesteps=ppo_steps_per_update,
                    birth_phase=True,
                )
                self.ppo_steps += ppo_steps_per_update

            stage_result = evaluate_stage_pass(
                stage,
                trades=rollout.trades,
                wins=rollout.wins,
                hold_signals=rollout.hold_signals,
                total_signals=rollout.total_signals,
                constitution_violations=self._constitution_guard.violations,
                target_trades=target,
            )
            if not stage_result.passed and not practice_mode:
                write_birth_progress(
                    self.workspace_root,
                    stage="failed",
                    phase="curriculum_failed",
                    message=f"Curriculum stage failed: {stage_result.message}",
                    progress_pct=95.0,
                    cumulative_trades=self.cumulative_trades,
                    target_trades=cfg.trade_budget_cap,
                    birth_start_time=self.birth_start_time,
                    curriculum_stage=stage.value,
                )
                return {
                    "status": "certificate_failed",
                    "total_trades": self.cumulative_trades,
                    "ppo_steps": self.ppo_steps,
                    "training_mode": "certified",
                }

            self._stages_passed.append(stage.value)
            stage_index += 1
            self.ppo_trainer.save_final_birth_policy(str(self.final_policy_path))
            save_checkpoint(
                self.workspace_root,
                cumulative_trades=self.cumulative_trades,
                ppo_steps=self.ppo_steps,
                training_mode=training_mode,
                stages_passed=self._stages_passed,
                curriculum_stage=stage.value,
                policy_path=str(self.final_policy_path),
            )

        write_birth_progress(
            self.workspace_root,
            stage="ppo_training",
            phase="ppo_polish",
            message="Final PPO polish (stage4).",
            progress_pct=85.0,
            cumulative_trades=self.cumulative_trades,
            target_trades=cfg.trade_budget_cap,
            ppo_steps=self.ppo_steps,
            birth_start_time=self.birth_start_time,
            curriculum_stage=CurriculumStage.STAGE4_POLISH.value,
        )

        polish_steps = cfg.curriculum.stage4_polish_ppo_steps
        if len(self.buffer) >= 256:
            self.ppo_trainer.final_birth_polish(self.buffer)
            self.ppo_steps += polish_steps
        else:
            self.ppo_trainer.update_from_buffer(buffer=self.buffer, timesteps=min(polish_steps, 10_000), birth_phase=True)
            self.ppo_steps += min(polish_steps, 10_000)

        target_policy = self.practice_policy_path if practice_mode else self.final_policy_path
        self.ppo_trainer.save_final_birth_policy(str(target_policy))

        if practice_mode:
            self.practice_completed_flag_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
            clear_checkpoint(self.workspace_root)
            write_birth_progress(
                self.workspace_root,
                stage="practice_completed",
                phase="practice_completed",
                message="Practice Birth voltooid (geen certificate).",
                progress_pct=100.0,
                cumulative_trades=self.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=self.birth_start_time,
            )
            return {
                "status": "practice_completed",
                "total_trades": self.cumulative_trades,
                "ppo_steps": self.ppo_steps,
                "real_data_pct": self._real_data_pct,
                "policy_path": str(target_policy),
                "training_mode": "practice",
            }

        write_birth_progress(
            self.workspace_root,
            stage="training_running",
            phase="oos_evaluation",
            message="OOS certificate evaluatie…",
            progress_pct=92.0,
            cumulative_trades=self.cumulative_trades,
            target_trades=cfg.trade_budget_cap,
            birth_start_time=self.birth_start_time,
        )

        eval_result = evaluate_holdout_certificate(
            runtime=self.runtime,
            holdout_data=split.holdout,
            policy=self.current_policy,
            real_data_pct=self._real_data_pct,
            holdout_days=split.holdout_days,
            constitution_violations=self._constitution_guard.violations,
            workspace_root=self.workspace_root,
            thresholds=cfg.certificate_thresholds,
        )

        if not eval_result.get("certificate_passed"):
            write_birth_progress(
                self.workspace_root,
                stage="failed",
                phase="certificate_failed",
                message="Birth Certificate v2 thresholds not met.",
                progress_pct=100.0,
                cumulative_trades=self.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=self.birth_start_time,
                oos_metrics=eval_result,
            )
            return {
                "status": "certificate_failed",
                "total_trades": self.cumulative_trades,
                "ppo_steps": self.ppo_steps,
                "real_data_pct": self._real_data_pct,
                "eval": eval_result,
                "training_mode": "certified",
            }

        self._stages_passed.append(CurriculumStage.STAGE4_POLISH.value)
        certificate = build_certificate_from_eval(
            workspace_root=self.workspace_root,
            eval_result=eval_result,
            curriculum_stages_passed=self._stages_passed,
            training_trades=self.cumulative_trades,
            ppo_steps=self.ppo_steps,
        )
        write_certificate(self.workspace_root, certificate)
        clear_checkpoint(self.workspace_root)
        stamp = datetime.now(timezone.utc).isoformat()
        for path in (self.completion_flag_path, self.legacy_completion_flag_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(stamp, encoding="utf-8")

        register_birth_gen0_dna(self.workspace_root, certificate)
        update_bible_after_birth(self.workspace_root, certificate, eval_result)

        write_birth_progress(
            self.workspace_root,
            stage="completed",
            phase="certificate_issued",
            message="Birth Certificate v2 issued.",
            progress_pct=100.0,
            cumulative_trades=self.cumulative_trades,
            target_trades=cfg.trade_budget_cap,
            ppo_steps=self.ppo_steps,
            birth_start_time=self.birth_start_time,
            certificate_ok=True,
            oos_metrics=eval_result,
            curriculum_stages_passed=self._stages_passed,
        )

        return {
            "status": "completed",
            "total_trades": self.cumulative_trades,
            "ppo_steps": self.ppo_steps,
            "real_data_pct": self._real_data_pct,
            "policy_path": str(target_policy),
            "certificate_path": str(certificate_path(self.workspace_root)),
            "eval": eval_result,
            "training_mode": "certified",
        }

    def _paused_result(self) -> dict[str, Any]:
        write_birth_progress(
            self.workspace_root,
            stage="paused",
            phase="paused",
            message="Birth Phase gepauzeerd.",
            progress_pct=min(
                99.0,
                float(self.cumulative_trades) / max(1.0, float(self.birth_config.trade_budget_cap)) * 100.0,
            ),
            cumulative_trades=self.cumulative_trades,
            target_trades=self.birth_config.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            ppo_steps=self.ppo_steps,
        )
        return {"status": "paused", "total_trades": self.cumulative_trades, "ppo_steps": self.ppo_steps}
