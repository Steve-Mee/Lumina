from __future__ import annotations

import json
import math
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lumina_core.birth_policy_observation import BIRTH_RL_OBS_DIM, build_birth_rl_observation_vector
from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_TRADES,
    FIRST_BOOT_TRAINING_TRADES_MAX,
    FIRST_BOOT_TRAINING_TRADES_MIN,
    normalize_first_boot_training_trades,
)
from lumina_core.logging_utils import get_logger
from lumina_core.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth_engine")
_BIRTH_TICKS_PER_REAL_DAY = 450
_STALL_CONSECUTIVE_MAX = 3
_STALL_CHUNK_RETRIES = 3
_NEAR_COMPLETE_RATIO = 0.98
_SIM_ZERO_TRADE_ABORT_TICKS = 100_000
_SIM_EXPLORATION_AFTER_TICKS = 50_000
_BOOTSTRAP_WARMUP_TRADES = 25


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
        idx = np.random.choice(len(self.trajectories), size=min(batch_size, len(self.trajectories)), replace=False)
        return [self.trajectories[int(i)] for i in idx]

    def __len__(self) -> int:
        return len(self.trajectories)

    def clear(self) -> None:
        self.trajectories.clear()
        self.priorities.clear()


class LuminaBirthEngine:
    # BIRTH ENGINE 2026-05-17
    def __init__(
        self,
        runtime: Any = None,
        ppo_trainer: PPOTrainer | None = None,
        market_data_service: Any = None,
        config: dict[str, Any] | None = None,
        workspace_root: str | Path = Path.cwd(),
        stop_event: threading.Event | None = None,
    ) -> None:
        self.runtime = runtime
        self.ppo_trainer = ppo_trainer or PPOTrainer(engine=runtime)
        self.market_data_service = market_data_service
        self.config = config or {}
        self.workspace_root = Path(workspace_root)
        self.stop_event = stop_event
        self.logger = logger
        self.cumulative_trades = 0
        self.ppo_steps = 0
        self.birth_start_time = 0.0
        self.buffer = TrajectoryBuffer(capacity=500_000)
        self.current_policy: Any = None
        self._entry_counter = 0
        self._recent_pnl: list[float] = []
        self._loaded_real_days = 0
        self._real_data_pct = 0.0
        self._active_training_mode = "certified"
        self._ppo_timesteps_planned_total = 0
        self._ppo_batch_count = 0
        self._consecutive_stall_chunks = 0

        self.checkpoint_path = self.workspace_root / "state" / "lumina_birth_checkpoint.json"
        self.legacy_checkpoint_path = self.workspace_root / "state" / "first_boot_checkpoint.json"
        self.progress_path = self.workspace_root / "state" / "lumina_birth_progress.json"
        self.legacy_progress_path = self.workspace_root / "state" / "first_boot_progress.json"
        self.pause_flag_path = self.workspace_root / "state" / "first_boot_pause_requested"
        self.final_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
        self.practice_policy_path = self.workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy_practice.zip"
        self.completion_flag_path = self.workspace_root / "state" / "lumina_birth_completed.flag"
        self.legacy_completion_flag_path = self.workspace_root / "state" / "first_boot_completed.flag"
        self.practice_completed_flag_path = self.workspace_root / "state" / "lumina_birth_practice_completed.flag"

        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.final_policy_path.parent.mkdir(parents=True, exist_ok=True)
        self.practice_policy_path.parent.mkdir(parents=True, exist_ok=True)

    def _user_stop_requested(self) -> bool:
        return self.stop_event is not None and self.stop_event.is_set()

    def _stop_requested(self) -> bool:
        if self._user_stop_requested():
            return True
        return self.pause_flag_path.exists()

    def _handle_user_stop(
        self,
        *,
        target: int,
        ticks: list[dict[str, Any]],
        training_mode: str,
    ) -> dict[str, Any]:
        self._save_checkpoint(target=target, training_mode=training_mode)
        if self._user_stop_requested():
            stage = "stopped_by_user"
            phase = "stopped_by_user"
            status = "stopped"
            message = "Birth Phase gestopt op gebruikersverzoek."
        else:
            stage = "paused"
            phase = "paused"
            status = "paused"
            message = "Birth Phase gepauzeerd op gebruikersverzoek."
        self._write_progress(
            stage=stage,
            message=message,
            target_trades=target,
            phase=phase,
            progress_pct=self._overall_progress_pct(target),
            remaining_trades=max(0, target - self.cumulative_trades),
            **self._data_progress_extra(training_mode),
        )
        return self._result_payload(status=status, ticks=ticks)

    def _data_progress_extra(self, training_mode: str) -> dict[str, Any]:
        mode = str(training_mode or self._active_training_mode or "certified").strip().lower()
        return {
            "training_mode": mode,
            "actual_real_days_loaded": int(self._loaded_real_days),
            "real_data_pct": round(float(self._real_data_pct), 3),
            "certification_eligible": mode == "certified",
        }

    def _estimate_ppo_timesteps_planned(
        self,
        *,
        target_trades: int,
        chunk_size: int,
        ppo_update_timesteps: int,
    ) -> int:
        chunks = max(1, int(math.ceil(float(max(1, target_trades)) / float(max(1, chunk_size)))))
        per_chunk_updates = max(1, int(ppo_update_timesteps))
        final_polish = 50_000
        return int(chunks * per_chunk_updates + final_polish)

    def _ppo_progress_extra(self, *, target_trades: int) -> dict[str, Any]:
        target = max(1, int(target_trades))
        planned = max(0, int(self._ppo_timesteps_planned_total))
        cumulative = max(0, int(self.ppo_steps))
        return {
            "ppo_steps_cumulative": cumulative,
            "ppo_timesteps_planned_total": planned,
            "sim_trades_complete": bool(self.cumulative_trades >= target),
            "ppo_batch_count": int(self._ppo_batch_count),
        }

    def _read_checkpoint_payload(self) -> dict[str, Any] | None:
        candidates = [p for p in (self.checkpoint_path, self.legacy_checkpoint_path) if p.exists()]
        if not candidates:
            return None
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _can_resume_checkpoint(self, *, target: int, training_mode: str) -> bool:
        if self._birth_completed_flag_exists():
            return False
        payload = self._read_checkpoint_payload()
        if not payload:
            return False
        if int(payload.get("target_trades", 0) or 0) != int(target):
            return False
        ckpt_mode = str(payload.get("training_mode", "") or "").strip().lower()
        desired = str(training_mode).strip().lower()
        if ckpt_mode and ckpt_mode != desired:
            return False
        if not ckpt_mode and desired == "certified":
            return False
        return True

    def _checkpoint_resume_block_reason(self, *, target: int, training_mode: str) -> str | None:
        payload = self._read_checkpoint_payload()
        if not payload:
            return None
        if self._can_resume_checkpoint(target=target, training_mode=training_mode):
            return None
        ckpt_target = int(payload.get("target_trades", 0) or 0)
        if ckpt_target != int(target):
            return "target_mismatch"
        ckpt_mode = str(payload.get("training_mode", "") or "").strip().lower()
        desired = str(training_mode).strip().lower()
        if ckpt_mode and ckpt_mode != desired:
            return "mode_mismatch"
        if not ckpt_mode and desired == "certified":
            return "mode_mismatch"
        return "checkpoint_incompatible"

    def _create_birth_policy(self, *, allow_load_existing: bool) -> Any:
        create = getattr(self.ppo_trainer, "create_fresh_birth_policy", None)
        if not callable(create):
            raise RuntimeError("PPO trainer heeft geen create_fresh_birth_policy.")
        try:
            return create(allow_load_existing=bool(allow_load_existing))
        except TypeError:
            return create()

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
        # BIRTH ENGINE 2026-05-17
        training_mode = "practice" if practice_mode else "certified"
        self._active_training_mode = training_mode
        target = self._resolve_target_trades(target_trades)
        max_days = max(30, min(3650, int(max_real_days)))
        chunk_size = max(2_500, min(250_000, int(chunk_size)))
        ppo_update_timesteps = max(1_000, min(500_000, int(ppo_update_timesteps)))
        self.birth_start_time = time.time()
        self._write_progress(
            stage="detected",
            message="Birth Phase gestart.",
            target_trades=target,
            max_real_days=max_days,
            phase="detected",
            progress_pct=5.0,
            **self._data_progress_extra(training_mode),
        )
        block_reason = self._checkpoint_resume_block_reason(target=target, training_mode=training_mode)
        if block_reason and not force:
            ckpt = self._read_checkpoint_payload() or {}
            ckpt_trades = int(ckpt.get("cumulative_trades", 0) or 0)
            ckpt_mode = str(ckpt.get("training_mode", "") or "").strip().lower()
            self._write_progress(
                stage="checkpoint_available",
                message=(
                    f"Checkpoint beschikbaar ({ckpt_trades:,} trades, mode `{ckpt_mode or 'onbekend'}`) — "
                    f"hervatten niet mogelijk ({block_reason.replace('_', ' ')})."
                ),
                target_trades=target,
                phase="checkpoint_available",
                progress_pct=self._overall_progress_pct(target),
                retryable=True,
                failure_reason=block_reason,
                checkpoint_trades=ckpt_trades,
                checkpoint_mode=ckpt_mode,
                requested_training_mode=training_mode,
                **self._data_progress_extra(training_mode),
            )
            self.logger.info(
                "birth.checkpoint.skipped_resume reason=%s target=%s training_mode=%s checkpoint_trades=%s",
                block_reason,
                target,
                training_mode,
                ckpt_trades,
            )
            return {
                "status": "checkpoint_available",
                "total_trades": ckpt_trades,
                "ppo_steps": int(ckpt.get("ppo_steps", 0) or 0),
                "duration_seconds": round(time.time() - self.birth_start_time, 2),
                "real_data_pct": 0.0,
                "policy_path": str(self.final_policy_path),
                "training_mode": training_mode,
                "failure_reason": block_reason,
            }
        ticks = self._load_training_ticks(
            max_real_days=max_days,
            prefer_real_data_only=prefer_real_data_only,
            target_trades=target,
            training_mode=training_mode,
        )
        ticks = self._enrich_ticks_for_sim(ticks)
        self._real_data_pct = self._calculate_real_data_percentage(ticks)
        if not ticks:
            self._write_progress(
                stage="history_unavailable",
                message="Birth Phase kon niet starten: geen historische data beschikbaar.",
                target_trades=target,
                phase="loading_history_failed",
                progress_pct=100.0,
                retryable=True,
                failure_reason="historical_data_unavailable",
                **self._data_progress_extra(training_mode),
            )
            return {
                "status": "history_unavailable",
                "total_trades": 0,
                "ppo_steps": 0,
                "duration_seconds": round(time.time() - self.birth_start_time, 2),
                "real_data_pct": 0.0,
                "policy_path": str(self.final_policy_path),
                "training_mode": training_mode,
            }
        can_resume = self._can_resume_checkpoint(target=target, training_mode=training_mode) and not force
        if reuse_existing_policy is None:
            reuse_existing_policy = bool(can_resume)
        if can_resume:
            self._load_checkpoint()
            self.logger.info("birth.resume checkpoint trades=%s ppo_steps=%s", self.cumulative_trades, self.ppo_steps)
        else:
            if self._read_checkpoint_payload() is not None:
                self.logger.info(
                    "birth.checkpoint.fresh_start target=%s training_mode=%s force=%s",
                    target,
                    training_mode,
                    bool(force),
                )
            self.cumulative_trades = 0
            self.ppo_steps = 0
            self.buffer.clear()
            self.current_policy = self._create_birth_policy(allow_load_existing=bool(reuse_existing_policy))
            if force:
                self._clear_checkpoint()
        if self.current_policy is None:
            self.current_policy = self._create_birth_policy(allow_load_existing=bool(reuse_existing_policy))

        self._ppo_timesteps_planned_total = self._estimate_ppo_timesteps_planned(
            target_trades=target,
            chunk_size=chunk_size,
            ppo_update_timesteps=ppo_update_timesteps,
        )
        self._write_progress(
            stage="pipeline_boot",
            message=(
                f"Simulatie starten — doel {target:,} trades "
                f"(chunk {chunk_size:,}, PPO plan {self._ppo_timesteps_planned_total:,} steps)."
            ),
            target_trades=target,
            phase="parallel_simulation",
            progress_pct=30.0,
            ticks_loaded=len(ticks),
            **self._data_progress_extra(training_mode),
        )

        last_checkpoint = time.time()
        self._consecutive_stall_chunks = 0
        while self.cumulative_trades < target:
            if self._stop_requested():
                return self._handle_user_stop(target=target, ticks=ticks, training_mode=training_mode)

            remaining = max(0, target - self.cumulative_trades)
            chunk_target = min(chunk_size, remaining)
            self._write_progress(
                stage="training_running",
                message=(
                    f"Simulatie-chunk: {self.cumulative_trades:,}/{target:,} trades "
                    f"(doel chunk {chunk_target:,})…"
                ),
                target_trades=target,
                phase="parallel_simulation",
                progress_pct=max(30.0, self._overall_progress_pct(target)),
                **self._data_progress_extra(training_mode),
            )
            chunk: dict[str, Any] = {}
            chunk_trades = 0
            stall_diag: dict[str, Any] = {}
            for attempt in range(1, _STALL_CHUNK_RETRIES + 1):
                chunk = self._simulate_chunk_with_policy(
                    ticks=ticks,
                    chunk_trades=chunk_target,
                    policy=self.current_policy,
                    target_trades=target,
                    training_mode=training_mode,
                )
                if self._stop_requested():
                    return self._handle_user_stop(target=target, ticks=ticks, training_mode=training_mode)
                chunk_trades = int(chunk.get("trades", 0) or 0)
                stall_diag = dict(chunk.get("diagnostics", {}) or {})
                if chunk_trades > 0:
                    break
                self._log_chunk_stall(
                    chunk_target=chunk_target,
                    remaining_trades=remaining,
                    attempt=attempt,
                    max_attempts=_STALL_CHUNK_RETRIES,
                    diagnostics=stall_diag,
                )

            if chunk_trades <= 0:
                stall_outcome = self._handle_chunk_stall(
                    target=target,
                    ticks=ticks,
                    training_mode=training_mode,
                    chunk_target=chunk_target,
                    remaining_trades=remaining,
                    diagnostics=stall_diag,
                )
                if stall_outcome == "grace_complete":
                    self.cumulative_trades = target
                    break
                if stall_outcome == "failed":
                    return self._result_payload(status="birth_failed", ticks=ticks)
                continue

            self._consecutive_stall_chunks = 0
            self.cumulative_trades += chunk_trades
            self._recent_pnl.extend([float(v) for v in chunk.get("pnl_series", [])])
            self._recent_pnl = self._recent_pnl[-500:]
            for traj in chunk.get("trajectories", []):
                if isinstance(traj, dict):
                    self.buffer.add(traj, priority=1.0 + min(10.0, abs(float(traj.get("reward", 0.0)))))

            ppo_phase = "birth_phase"
            if len(self.buffer) >= 256:
                self._ppo_batch_count += 1
                self.current_policy = self.ppo_trainer.update_from_buffer(
                    buffer=self.buffer,
                    timesteps=ppo_update_timesteps,
                    birth_phase=True,
                )
                self.ppo_steps += ppo_update_timesteps
                ppo_phase = "ppo_training"

            self._write_progress(
                stage="training_running",
                message=(
                    f"Birth Phase actief: {self.cumulative_trades:,}/{target:,} trades, "
                    f"{self.ppo_steps:,}/{self._ppo_timesteps_planned_total:,} PPO timesteps (totaal)."
                ),
                target_trades=target,
                phase=ppo_phase,
                progress_pct=self._overall_progress_pct(target),
                chunk_trades=chunk_trades,
                chunk_trades_partial=chunk_trades,
                chunk_pnl=float(chunk.get("total_pnl", 0.0) or 0.0),
                recent_winrate=round(float(chunk.get("winrate", 0.0) or 0.0), 4),
                velocity_trades_per_sec=round(self._velocity_trades_per_sec(), 3),
                estimated_real_days=self._estimate_required_real_days(target),
                sim_ticks_processed=int(stall_diag.get("ticks_processed", 0) or 0),
                **self._sim_diagnostics_extra(stall_diag),
                **self._data_progress_extra(training_mode),
            )
            if self.cumulative_trades % 100_000 == 0:
                self.ppo_trainer.save_intermediate_policy(self.cumulative_trades)
            if time.time() - last_checkpoint >= 20.0:
                self._save_checkpoint(target=target, training_mode=training_mode)
                last_checkpoint = time.time()

        self._ppo_timesteps_planned_total = max(
            int(self._ppo_timesteps_planned_total),
            int(self.ppo_steps) + 50_000,
        )
        self._write_progress(
            stage="training_running",
            message=(
                f"SIM-training afgerond ({self.cumulative_trades:,}/{target:,} trades). "
                f"Final PPO polish gestart."
            ),
            target_trades=target,
            phase="ppo_training",
            progress_pct=self._overall_progress_pct(target),
            **self._data_progress_extra(training_mode),
        )
        self._ppo_batch_count += 1
        self.ppo_trainer.final_birth_polish(self.buffer)
        self.ppo_steps += 50_000
        target_policy_path = self.practice_policy_path if practice_mode else self.final_policy_path
        self.ppo_trainer.save_final_birth_policy(str(target_policy_path))
        if practice_mode:
            self.practice_completed_flag_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
        else:
            self._create_birth_completed_flag()
        self._clear_checkpoint()
        self._write_progress(
            stage="practice_completed" if practice_mode else "completed",
            message=(
                "Practice Birth Phase voltooid met synthetic fallback. "
                "Dit telt niet mee voor live-gang."
                if practice_mode
                else "Birth Phase voltooid. Policy opgeslagen."
            ),
            target_trades=target,
            phase="practice_completed" if practice_mode else "completed",
            progress_pct=100.0,
            **self._data_progress_extra(training_mode),
        )
        return self._result_payload(
            status="practice_completed" if practice_mode else "completed",
            ticks=ticks,
            policy_path_override=target_policy_path,
            training_mode=training_mode,
        )

    # BIRTH ENGINE 2026-05-17
    def _resolve_target_trades(self, target_trades: int | None) -> int:
        if target_trades is None:
            raw = (self.config.get("first_boot", {}) if isinstance(self.config, dict) else {}).get(
                "training_trades", FIRST_BOOT_DEFAULT_TRADES
            )
        else:
            raw = target_trades
        normalized = normalize_first_boot_training_trades(raw)
        return max(FIRST_BOOT_TRAINING_TRADES_MIN, min(FIRST_BOOT_TRAINING_TRADES_MAX, int(normalized)))

    def _load_training_ticks(
        self,
        *,
        max_real_days: int,
        prefer_real_data_only: bool,
        target_trades: int = 0,
        training_mode: str = "certified",
    ) -> list[dict[str, Any]]:
        resolved_target = max(0, int(target_trades))
        self._write_progress(
            stage="loading_data",
            message="Historische marktdata laden voor Birth Phase.",
            target_trades=resolved_target,
            phase="loading_history",
            progress_pct=18.0,
            **self._data_progress_extra(training_mode),
        )
        def _on_history_chunk(
            *,
            chunk_index: int,
            chunk_total: int,
            bars_merged: int,
            chunk_bars: int = 0,
            chunk_phase: str = "fetch",
        ) -> None:
            phase_name = str(chunk_phase or "fetch").strip().lower()
            if phase_name == "expand" or int(chunk_total) > 64:
                progress_phase = "expanding_ticks"
                message = (
                    f"Ticks genereren uit bars: {bars_merged:,}/{chunk_total:,} "
                    f"({100.0 * float(chunk_index) / float(max(1, chunk_total)):.0f}%)"
                )
                progress_pct = min(27.0, 25.0 + (float(chunk_index) / float(max(1, chunk_total))) * 2.0)
            else:
                progress_phase = "loading_history"
                message = (
                    f"Historische data: chunk {chunk_index}/{chunk_total} "
                    f"({bars_merged:,} bars geladen)"
                )
                progress_pct = min(25.0, 18.0 + (float(chunk_index) / float(max(1, chunk_total))) * 7.0)
            self._write_progress(
                stage="loading_data",
                message=message,
                target_trades=resolved_target,
                phase=progress_phase,
                progress_pct=progress_pct,
                loading_chunk=int(chunk_index),
                loading_chunks_total=int(chunk_total),
                bars_loaded=int(bars_merged),
                **self._data_progress_extra(training_mode),
            )

        ticks = self._load_real_historical_ticks(
            days_back=max_real_days,
            limit=None,
            on_chunk=_on_history_chunk,
        )
        self._loaded_real_days = max(1, int(math.ceil(float(len(ticks)) / float(_BIRTH_TICKS_PER_REAL_DAY)))) if ticks else 0
        if ticks:
            self._real_data_pct = self._calculate_real_data_percentage(ticks)
            self._write_progress(
                stage="historical_loaded",
                message=(
                    f"Historische data klaar: {len(ticks):,} ticks "
                    f"(~{self._loaded_real_days} handelsdagen)."
                ),
                target_trades=resolved_target,
                phase="ticks_ready",
                progress_pct=28.0,
                ticks_loaded=len(ticks),
                **self._data_progress_extra(training_mode),
            )
        if ticks and prefer_real_data_only:
            return ticks
        if ticks and not prefer_real_data_only:
            synth_needed = max(2_000, int(len(ticks) * 0.05))
            ticks.extend(self._generate_synthetic_ticks(synth_needed, start_price=float(ticks[-1].get("last", 0.0) or 5000.0)))
            return ticks
        if not prefer_real_data_only:
            return self._generate_synthetic_ticks(max(20_000, max_real_days * 1000), start_price=5000.0)
        return []

    def _load_real_historical_ticks(
        self,
        *,
        days_back: int,
        limit: int,
        on_chunk: Any = None,
    ) -> list[dict[str, Any]]:
        source = self.market_data_service
        if source is not None and hasattr(source, "load_historical_ohlc_extended"):
            try:
                rows = source.load_historical_ohlc_extended(
                    days_back=days_back,
                    limit=limit,
                    ticks_per_bar=4,
                    on_chunk=on_chunk,
                )
                if isinstance(rows, list):
                    return self._normalize_tick_rows(rows, source_label="real_historical")
            except Exception as exc:
                self.logger.warning("birth.load_historical_ohlc_extended_failed detail=%s", exc, exc_info=True)
        ohlc = getattr(self.runtime, "ohlc_1min", None)
        if ohlc is None:
            return []
        try:
            records = ohlc.tail(limit).to_dict("records")
        except Exception:
            return []
        return self._normalize_tick_rows(records, source_label="real_runtime")

    @staticmethod
    def _sim_diagnostics_extra(diagnostics: dict[str, Any]) -> dict[str, Any]:
        return {
            "sim_diagnostics": {
                "ticks_processed": int(diagnostics.get("ticks_processed", 0) or 0),
                "hold_signals": int(diagnostics.get("hold_signals", 0) or 0),
                "buy_signals": int(diagnostics.get("buy_signals", 0) or 0),
                "sell_signals": int(diagnostics.get("sell_signals", 0) or 0),
                "infer_success": int(diagnostics.get("infer_success", 0) or 0),
                "bootstrap_count": int(diagnostics.get("bootstrap_count", 0) or 0),
                "policy_hold_count": int(diagnostics.get("policy_hold_count", 0) or 0),
                "infer_errors": int(diagnostics.get("infer_errors", 0) or 0),
                "open_position_at_end": bool(diagnostics.get("open_position_at_end", False)),
                "exploration_count": int(diagnostics.get("exploration_count", 0) or 0),
                "zero_trade_abort": bool(diagnostics.get("zero_trade_abort", False)),
            }
        }

    def _enrich_ticks_for_sim(self, ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Derive regime/imbalance from price path so bootstrap/policy can open positions on real OHLC ticks."""
        if not ticks:
            return ticks
        lookback = 20
        for i, tick in enumerate(ticks):
            try:
                price = float(tick.get("last", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            bid = float(tick.get("bid", price - 0.125) or price - 0.125)
            ask = float(tick.get("ask", price + 0.125) or price + 0.125)
            spread = max(0.25, ask - bid)
            tick["imbalance"] = max(0.5, min(2.0, 1.0 + (ask - bid) / spread * 0.15))
            if i < lookback:
                tick["regime"] = str(tick.get("regime", "NEUTRAL"))
                continue
            window_start = max(0, i - lookback)
            start_price = float(ticks[window_start].get("last", price) or price)
            if start_price <= 0:
                tick["regime"] = "NEUTRAL"
                continue
            ret = (price - start_price) / start_price
            if ret > 0.0015:
                tick["regime"] = "TREND_UP"
            elif ret < -0.0015:
                tick["regime"] = "TREND_DOWN"
            else:
                tick["regime"] = "NEUTRAL"
        return ticks

    def _normalize_tick_rows(self, rows: list[dict[str, Any]], *, source_label: str) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                price = float(
                    row.get("last")
                    or row.get("close")
                    or row.get("price")
                    or row.get("ask")
                    or 0.0
                )
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            normalized.append(
                {
                    "timestamp": str(row.get("timestamp", "")),
                    "last": price,
                    "bid": float(row.get("bid", price - 0.125) or price - 0.125),
                    "ask": float(row.get("ask", price + 0.125) or price + 0.125),
                    "volume": int(row.get("volume", 1) or 1),
                    "regime": str(row.get("regime", "NEUTRAL")),
                    "imbalance": float(row.get("imbalance", 1.0) or 1.0),
                    "source": source_label,
                }
            )
        return normalized

    def _generate_synthetic_ticks(self, n_ticks: int, *, start_price: float) -> list[dict[str, Any]]:
        rng = random.Random(51 + int(time.time()) % 1000)
        price = max(100.0, float(start_price))
        out: list[dict[str, Any]] = []
        for _ in range(max(1, n_ticks)):
            shock = rng.gauss(0.0, 0.0016)
            price = max(10.0, price * (1.0 + shock))
            out.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "last": float(price),
                    "bid": float(price - 0.125),
                    "ask": float(price + 0.125),
                    "volume": int(1000 + abs(rng.gauss(0.0, 500.0))),
                    "regime": "SYNTHETIC",
                    "imbalance": float(1.0 + rng.uniform(-0.4, 0.4)),
                    "source": "synthetic",
                }
            )
        return out

    def _is_near_complete(self, target: int) -> bool:
        threshold = float(max(1, target)) * _NEAR_COMPLETE_RATIO
        return float(self.cumulative_trades) >= threshold

    def _log_chunk_stall(
        self,
        *,
        chunk_target: int,
        remaining_trades: int,
        attempt: int,
        max_attempts: int,
        diagnostics: dict[str, Any],
    ) -> None:
        self.logger.warning(
            "birth.chunk.stall",
            extra={
                "event_data": {
                    "chunk_target": int(chunk_target),
                    "remaining_trades": int(remaining_trades),
                    "cumulative_trades": int(self.cumulative_trades),
                    "attempt": int(attempt),
                    "max_attempts": int(max_attempts),
                    "near_complete": self._is_near_complete(max(1, self.cumulative_trades + remaining_trades)),
                    **diagnostics,
                }
            },
        )

    def _handle_chunk_stall(
        self,
        *,
        target: int,
        ticks: list[dict[str, Any]],
        training_mode: str,
        chunk_target: int,
        remaining_trades: int,
        diagnostics: dict[str, Any],
    ) -> str:
        """Return ``grace_complete``, ``failed``, or ``continue`` (retry next loop iteration)."""
        self._consecutive_stall_chunks += 1
        near_complete = self._is_near_complete(target)
        stall_extra = {
            "failure_reason": "simulation_stall",
            "retryable": True,
            "remaining_trades": int(remaining_trades),
            "consecutive_stall_chunks": int(self._consecutive_stall_chunks),
            "stall_diagnostics": diagnostics,
            "chunk_target": int(chunk_target),
        }
        if near_complete:
            self._write_progress(
                stage="training_running",
                message=(
                    f"SIM-chunk zonder trades bij {self.cumulative_trades:,}/{target:,} "
                    f"({remaining_trades:,} resterend) — near-complete grace: doel afgerond."
                ),
                target_trades=target,
                phase="simulation_stall_grace",
                progress_pct=self._overall_progress_pct(target),
                **stall_extra,
                **self._data_progress_extra(training_mode),
            )
            self.logger.warning(
                "birth.chunk.stall.grace_complete",
                extra={
                    "event_data": {
                        "cumulative_trades": int(self.cumulative_trades),
                        "target": int(target),
                        **diagnostics,
                    }
                },
            )
            return "grace_complete"

        if self._consecutive_stall_chunks >= _STALL_CONSECUTIVE_MAX:
            self._write_progress(
                stage="failed",
                message=(
                    "Birth Phase stopte: simulatie leverde geen trades op "
                    f"({self._consecutive_stall_chunks} opeenvolgende lege chunks)."
                ),
                target_trades=target,
                phase="simulation_stall",
                progress_pct=self._overall_progress_pct(target),
                **stall_extra,
                **self._data_progress_extra(training_mode),
            )
            return "failed"

        self._write_progress(
            stage="training_running",
            message=(
                f"SIM-chunk zonder trades ({self._consecutive_stall_chunks}/{_STALL_CONSECUTIVE_MAX}); "
                f"volgende chunk wordt geprobeerd ({remaining_trades:,} trades resterend)."
            ),
            target_trades=target,
            phase="simulation_stall_retry",
            progress_pct=self._overall_progress_pct(target),
            **stall_extra,
            **self._data_progress_extra(training_mode),
        )
        return "continue"

    def _build_policy_observation_vector(
        self,
        *,
        tick: dict[str, Any],
        position: dict[str, Any] | None,
        tick_index: int,
        tick_count: int,
    ) -> np.ndarray:
        return build_birth_rl_observation_vector(
            tick=tick,
            position=position,
            tick_index=tick_index,
            tick_count=tick_count,
            recent_pnl=self._recent_pnl,
        )

    # BIRTH ENGINE 2026-05-17
    def _simulate_chunk_with_policy(
        self,
        *,
        ticks: list[dict[str, Any]],
        chunk_trades: int,
        policy: Any,
        target_trades: int = 0,
        training_mode: str = "certified",
    ) -> dict[str, Any]:
        trades = 0
        wins = 0
        total_pnl = 0.0
        pnl_series: list[float] = []
        trajectories: list[dict[str, Any]] = []
        idx = 0
        position: dict[str, Any] | None = None
        local_limit = max(5_000, chunk_trades * 80)
        diagnostics: dict[str, Any] = {
            "ticks_processed": 0,
            "infer_success": 0,
            "infer_errors": 0,
            "bootstrap_count": 0,
            "policy_hold_count": 0,
            "hold_signals": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "open_position_at_end": False,
            "exhausted": False,
            "obs_dim": BIRTH_RL_OBS_DIM,
        }
        tick_count = max(1, len(ticks))
        last_sim_progress = 0.0
        prev_price = float(ticks[0].get("last", 0.0) or 0.0) if ticks else 0.0
        while trades < chunk_trades and idx < local_limit:
            if idx > 0 and idx % 1000 == 0 and self._stop_requested():
                break
            if idx > 0 and idx % 2500 == 0:
                now = time.time()
                if now - last_sim_progress >= 8.0:
                    last_sim_progress = now
                    diagnostics["ticks_processed"] = int(idx)
                    resolved_target = max(1, int(target_trades or chunk_trades))
                    self._write_progress(
                        stage="training_running",
                        message=(
                            f"Simulatie bezig: {self.cumulative_trades + trades:,}/"
                            f"{resolved_target:,} trades "
                            f"({idx:,} ticks, BUY {diagnostics['buy_signals']}/"
                            f"SELL {diagnostics['sell_signals']}/"
                            f"HOLD {diagnostics['hold_signals']})…"
                        ),
                        target_trades=resolved_target,
                        phase="parallel_simulation",
                        progress_pct=max(30.0, self._overall_progress_pct(resolved_target)),
                        trades_done=int(self.cumulative_trades + trades),
                        cumulative_trades=int(self.cumulative_trades + trades),
                        total_trades=int(self.cumulative_trades + trades),
                        chunk_trades_partial=int(trades),
                        sim_ticks_processed=int(idx),
                        **self._sim_diagnostics_extra(diagnostics),
                        **self._data_progress_extra(training_mode),
                    )
            tick = ticks[idx % len(ticks)]
            idx += 1
            if trades == 0 and idx >= _SIM_ZERO_TRADE_ABORT_TICKS:
                diagnostics["zero_trade_abort"] = True
                self.logger.warning(
                    "birth.sim.zero_trade_abort ticks=%s chunk_trades=%s",
                    idx,
                    chunk_trades,
                )
                break
            observation = self._build_observation(tick=tick, position=position)
            obs_vector = self._build_policy_observation_vector(
                tick=tick,
                position=position,
                tick_index=idx,
                tick_count=tick_count,
            )
            action: dict[str, Any]
            action_source: str
            allow_bootstrap = bool(training_mode == "practice" or trades < _BOOTSTRAP_WARMUP_TRADES)
            if (
                trades == 0
                and idx >= _SIM_EXPLORATION_AFTER_TICKS
                and position is None
                and idx % 200 == 0
            ):
                try:
                    cur_px = float(tick.get("last", 0.0) or 0.0)
                except (TypeError, ValueError):
                    cur_px = 0.0
                if cur_px > prev_price:
                    action = {"side": "BUY", "qty": 1, "stop_pct": 0.0075, "target_pct": 0.013}
                    action_source = "exploration"
                elif cur_px < prev_price:
                    action = {"side": "SELL", "qty": 1, "stop_pct": 0.0075, "target_pct": 0.013}
                    action_source = "exploration"
                else:
                    action, action_source = self._resolve_policy_action(
                        policy=policy,
                        observation=observation,
                        tick=tick,
                        observation_vector=obs_vector,
                        allow_bootstrap=allow_bootstrap,
                    )
            else:
                action, action_source = self._resolve_policy_action(
                    policy=policy,
                    observation=observation,
                    tick=tick,
                    observation_vector=obs_vector,
                    allow_bootstrap=allow_bootstrap,
                )
            try:
                prev_price = float(tick.get("last", prev_price) or prev_price)
            except (TypeError, ValueError):
                pass
            side = str(action.get("side", "HOLD")).upper()
            if side == "HOLD":
                diagnostics["hold_signals"] = int(diagnostics["hold_signals"]) + 1
            elif side == "BUY":
                diagnostics["buy_signals"] = int(diagnostics["buy_signals"]) + 1
            elif side == "SELL":
                diagnostics["sell_signals"] = int(diagnostics["sell_signals"]) + 1
            if action_source == "policy":
                diagnostics["infer_success"] = int(diagnostics["infer_success"]) + 1
            elif action_source == "bootstrap":
                diagnostics["bootstrap_count"] = int(diagnostics["bootstrap_count"]) + 1
            elif action_source == "exploration":
                diagnostics["exploration_count"] = int(diagnostics.get("exploration_count", 0)) + 1
            elif action_source == "policy_hold":
                diagnostics["policy_hold_count"] = int(diagnostics.get("policy_hold_count", 0)) + 1
            else:
                diagnostics["infer_errors"] = int(diagnostics["infer_errors"]) + 1
            if position is None and action["side"] != "HOLD":
                self._entry_counter += 1
                position = self._open_position(tick=tick, action=action, entry_tick=idx)
                continue
            if position is None:
                continue
            exited, pnl, reason = self._check_exit(position=position, tick=tick, current_entry_index=idx)
            if not exited:
                continue
            trades += 1
            total_pnl += pnl
            pnl_series.append(float(pnl))
            if pnl > 0:
                wins += 1
            trajectories.append(
                {
                    "observation": dict(observation),
                    "action": dict(action),
                    "reward": float(pnl),
                    "next_observation": self._build_observation(tick=tick, position=None),
                    "done": True,
                    "pnl": float(pnl),
                    "exit_reason": reason,
                    "regime": str(tick.get("regime", "UNKNOWN")),
                }
            )
            position = None
        diagnostics["ticks_processed"] = int(idx)
        diagnostics["open_position_at_end"] = bool(position is not None)
        diagnostics["exhausted"] = bool(idx >= local_limit)
        return {
            "trades": trades,
            "total_pnl": round(total_pnl, 6),
            "winrate": float(wins) / float(max(1, trades)),
            "trajectories": trajectories,
            "pnl_series": pnl_series,
            "diagnostics": diagnostics,
        }

    def _build_observation(self, *, tick: dict[str, Any], position: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "price": float(tick.get("last", 0.0) or 0.0),
            "regime": str(tick.get("regime", "NEUTRAL")),
            "imbalance": float(tick.get("imbalance", 1.0) or 1.0),
            "volume": int(tick.get("volume", 1) or 1),
            "has_position": bool(position is not None),
            "position_side": str(position.get("side", "NONE")) if position else "NONE",
            "unrealized_pnl": self._calculate_unrealized(position=position, tick=tick) if position else 0.0,
        }

    def _resolve_policy_action(
        self,
        *,
        policy: Any,
        observation: dict[str, Any],
        tick: dict[str, Any],
        observation_vector: np.ndarray | None = None,
        allow_bootstrap: bool = True,
    ) -> tuple[dict[str, Any], str]:
        obs_vec = observation_vector
        if obs_vec is None:
            obs_vec = self._build_policy_observation_vector(
                tick=tick,
                position=None,
                tick_index=0,
                tick_count=1,
            )
        if obs_vec.shape[0] != BIRTH_RL_OBS_DIM:
            obs_vec = np.resize(obs_vec, BIRTH_RL_OBS_DIM).astype(np.float32)

        predicted = self._predict_from_policy(policy=policy, observation_vector=obs_vec)
        if predicted is not None and predicted["side"] != "HOLD":
            return predicted, "policy"

        infer = getattr(self.ppo_trainer, "infer_live_action", None)
        if callable(infer):
            try:
                action = infer(obs_vec)
            except Exception:
                action = None
                if not allow_bootstrap:
                    return {"side": "HOLD", "qty": 1, "stop_pct": 0.0075, "target_pct": 0.013}, "policy_hold"
                return self._bootstrap_action(observation=observation, tick=tick), "bootstrap"
            parsed = self._parse_action(action)
            if parsed["side"] != "HOLD":
                return parsed, "policy"
        if not allow_bootstrap:
            return {"side": "HOLD", "qty": 1, "stop_pct": 0.0075, "target_pct": 0.013}, "policy_hold"
        return self._bootstrap_action(observation=observation, tick=tick), "bootstrap"

    def _predict_from_policy(self, *, policy: Any, observation_vector: np.ndarray) -> dict[str, Any] | None:
        if policy is None:
            return None
        predict = getattr(policy, "predict", None)
        if not callable(predict):
            return None
        try:
            action, _ = predict(observation_vector, deterministic=True)
        except Exception:
            self.logger.warning("birth.policy.predict_failed", exc_info=True)
            return None
        action_arr = np.asarray(action, dtype=np.float32).reshape(-1)
        if action_arr.size < 1:
            return None
        side_bucket = int(np.clip(np.round(action_arr[0]), 0, 2))
        side = "HOLD" if side_bucket == 0 else ("BUY" if side_bucket == 1 else "SELL")
        qty = max(1, min(10, int(1 + np.clip(action_arr[1], 0.0, 1.0) * 9))) if action_arr.size > 1 else 1
        stop_pct = float(np.clip(action_arr[2], 0.001, 0.02)) if action_arr.size > 2 else 0.0075
        target_pct = float(np.clip(action_arr[3], 0.001, 0.05)) if action_arr.size > 3 else 0.013
        return {"side": side, "qty": qty, "stop_pct": stop_pct, "target_pct": target_pct}

    def _parse_action(self, action: Any) -> dict[str, Any]:
        if not isinstance(action, dict):
            return {"side": "HOLD", "qty": 1, "stop_pct": 0.0075, "target_pct": 0.013}
        signal = str(action.get("signal", "HOLD") or "HOLD").upper()
        if signal not in {"BUY", "SELL", "HOLD"}:
            signal = "HOLD"
        qty = max(1, min(10, int(action.get("qty", 1) or 1)))
        return {
            "side": signal,
            "qty": qty,
            "stop_pct": 0.0075,
            "target_pct": 0.013,
        }

    def _bootstrap_action(self, *, observation: dict[str, Any], tick: dict[str, Any]) -> dict[str, Any]:
        regime = str(observation.get("regime", "NEUTRAL")).upper()
        imbalance = float(observation.get("imbalance", 1.0) or 1.0)
        side = "HOLD"
        if "TREND_UP" in regime or ("TREND" in regime and imbalance >= 1.0):
            side = "BUY"
        elif "TREND_DOWN" in regime or ("TREND" in regime and imbalance < 1.0):
            side = "SELL"
        elif imbalance > 1.05:
            side = "BUY"
        elif imbalance < 0.95:
            side = "SELL"
        if tick.get("source") == "synthetic" and side != "HOLD":
            side = "HOLD" if random.random() < 0.35 else side
        return {"side": side, "qty": 1, "stop_pct": 0.0075, "target_pct": 0.013}

    def _open_position(self, *, tick: dict[str, Any], action: dict[str, Any], entry_tick: int) -> dict[str, Any]:
        price = float(tick.get("last", 0.0) or 0.0)
        side = str(action.get("side", "HOLD"))
        stop_pct = float(action.get("stop_pct", 0.0075) or 0.0075)
        target_pct = float(action.get("target_pct", 0.013) or 0.013)
        if side == "BUY":
            stop = price * (1.0 - stop_pct)
            target = price * (1.0 + target_pct)
        else:
            stop = price * (1.0 + stop_pct)
            target = price * (1.0 - target_pct)
        return {
            "side": side,
            "entry_price": price,
            "qty": int(action.get("qty", 1) or 1),
            "stop": stop,
            "target": target,
            "entry_idx": int(entry_tick),
        }

    def _check_exit(self, *, position: dict[str, Any], tick: dict[str, Any], current_entry_index: int) -> tuple[bool, float, str]:
        price = float(tick.get("last", 0.0) or 0.0)
        entry = float(position.get("entry_price", 0.0) or 0.0)
        qty = int(position.get("qty", 1) or 1)
        side = str(position.get("side", "BUY"))
        hold_len = int(current_entry_index - int(position.get("entry_idx", current_entry_index)))
        stop_hit = (side == "BUY" and price <= float(position.get("stop", price))) or (
            side == "SELL" and price >= float(position.get("stop", price))
        )
        target_hit = (side == "BUY" and price >= float(position.get("target", price))) or (
            side == "SELL" and price <= float(position.get("target", price))
        )
        timed_exit = hold_len >= 42
        if not (stop_hit or target_hit or timed_exit):
            return False, 0.0, ""
        if side == "BUY":
            pnl = (price - entry) * float(qty) * 5.0
        else:
            pnl = (entry - price) * float(qty) * 5.0
        reason = "target" if target_hit else ("stop" if stop_hit else "time_exit")
        return True, float(pnl), reason

    def _calculate_unrealized(self, *, position: dict[str, Any] | None, tick: dict[str, Any]) -> float:
        if position is None:
            return 0.0
        price = float(tick.get("last", 0.0) or 0.0)
        entry = float(position.get("entry_price", 0.0) or 0.0)
        qty = int(position.get("qty", 1) or 1)
        side = str(position.get("side", "BUY"))
        return (price - entry) * qty if side == "BUY" else (entry - price) * qty

    # BIRTH ENGINE 2026-05-17
    def _save_checkpoint(self, *, target: int, training_mode: str | None = None) -> None:
        mode = str(training_mode or self._active_training_mode or "certified").strip().lower()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_trades": int(target),
            "cumulative_trades": int(self.cumulative_trades),
            "ppo_steps": int(self.ppo_steps),
            "training_mode": mode,
            "practice_mode": mode == "practice",
        }
        encoded = json.dumps(payload, ensure_ascii=True, indent=2)
        for path in (self.checkpoint_path, self.legacy_checkpoint_path):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(encoded, encoding="utf-8")
            except Exception:
                self.logger.warning("birth.checkpoint.write_failed path=%s", path, exc_info=True)

    def _load_checkpoint(self) -> None:
        candidates = [p for p in (self.checkpoint_path, self.legacy_checkpoint_path) if p.exists()]
        if not candidates:
            return
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        self.cumulative_trades = max(0, int(payload.get("cumulative_trades", 0) or 0))
        self.ppo_steps = max(0, int(payload.get("ppo_steps", 0) or 0))

    def _clear_checkpoint(self) -> None:
        for path in (self.checkpoint_path, self.legacy_checkpoint_path):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                self.logger.warning("birth.checkpoint.clear_failed path=%s", path, exc_info=True)

    def _birth_completed_flag_exists(self) -> bool:
        return self.completion_flag_path.exists() or self.legacy_completion_flag_path.exists()

    def _create_birth_completed_flag(self) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        for path in (self.completion_flag_path, self.legacy_completion_flag_path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(stamp, encoding="utf-8")

    def _write_progress(self, *, stage: str, message: str, target_trades: int, phase: str, progress_pct: float, **extra: Any) -> None:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": str(stage).strip().lower(),
            "message": str(message),
            "phase": str(phase).strip().lower(),
            "target_trades": int(target_trades),
            "trades_done": int(self.cumulative_trades),
            "cumulative_trades": int(self.cumulative_trades),
            "total_trades": int(self.cumulative_trades),
            "ppo_steps": int(self.ppo_steps),
            **self._ppo_progress_extra(target_trades=int(target_trades)),
            "progress_pct": round(max(0.0, min(100.0, float(progress_pct))), 2),
            "elapsed_sec": round(max(0.0, time.time() - self.birth_start_time), 2) if self.birth_start_time > 0 else 0.0,
            "recent_pnl_avg": round(float(np.mean(self._recent_pnl)) if self._recent_pnl else 0.0, 4),
        }
        payload.update(extra)
        encoded = json.dumps(payload, ensure_ascii=True, indent=2)
        for path in (self.progress_path, self.legacy_progress_path):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(encoded, encoding="utf-8")
            except Exception:
                self.logger.warning("birth.progress.write_failed path=%s", path, exc_info=True)

    def _overall_progress_pct(self, target: int) -> float:
        trade_ratio = float(self.cumulative_trades) / float(max(1, target))
        trade_component = min(90.0, trade_ratio * 90.0)
        polish_bonus = 5.0 if self.cumulative_trades >= target else 0.0
        return min(99.0, trade_component + polish_bonus)

    def _estimate_required_real_days(self, target: int) -> int:
        return int(math.ceil(float(target) / float(_BIRTH_TICKS_PER_REAL_DAY)))

    def _velocity_trades_per_sec(self) -> float:
        if self.birth_start_time <= 0:
            return 0.0
        elapsed = max(1e-6, time.time() - self.birth_start_time)
        return float(self.cumulative_trades) / float(elapsed)

    def _calculate_real_data_percentage(self, ticks: list[dict[str, Any]]) -> float:
        if not ticks:
            return 0.0
        real = 0
        for tick in ticks:
            source = str(tick.get("source", "")).lower()
            if source.startswith("real"):
                real += 1
        return round((float(real) / float(max(1, len(ticks)))) * 100.0, 3)

    def _result_payload(
        self,
        *,
        status: str,
        ticks: list[dict[str, Any]],
        policy_path_override: Path | None = None,
        training_mode: str = "certified",
    ) -> dict[str, Any]:
        payload = {
            "status": str(status),
            "total_trades": int(self.cumulative_trades),
            "ppo_steps": int(self.ppo_steps),
            "duration_seconds": round(max(0.0, time.time() - self.birth_start_time), 2),
            "real_data_pct": self._calculate_real_data_percentage(ticks),
            "policy_path": str(policy_path_override or self.final_policy_path),
            "training_mode": str(training_mode),
        }
        payload["report_path"] = self._write_birth_report(payload)
        return payload

    def _write_birth_report(self, payload: dict[str, Any]) -> str:
        # BIRTH ENGINE 2026-05-17
        out_dir = self.workspace_root / "journal" / "simulator"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"lumina_birth_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = out_dir / filename
        report = dict(payload)
        report["timestamp"] = datetime.now(timezone.utc).isoformat()
        report["trades"] = int(payload.get("total_trades", 0) or 0)
        report["elapsed_sec"] = float(payload.get("duration_seconds", 0.0) or 0.0)
        report["synthetic_pct"] = round(100.0 - float(payload.get("real_data_pct", 0.0) or 0.0), 3)
        report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
        return str(report_path)
