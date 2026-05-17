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

from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_TRADES,
    FIRST_BOOT_TRAINING_TRADES_MAX,
    FIRST_BOOT_TRAINING_TRADES_MIN,
    normalize_first_boot_training_trades,
)
from lumina_core.logging_utils import get_logger
from lumina_core.ppo_trainer import PPOTrainer

logger = get_logger("lumina.birth_engine")
_BIRTH_TICKS_PER_REAL_DAY = 1560


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

    def run_birth_phase(
        self,
        target_trades: int | None = None,
        max_real_days: int = 365,
        prefer_real_data_only: bool = True,
        chunk_size: int = 50_000,
        ppo_update_timesteps: int = 25_000,
        force: bool = False,
        practice_mode: bool = False,
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
        ticks = self._load_training_ticks(max_real_days=max_days, prefer_real_data_only=prefer_real_data_only)
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
        if self._can_resume_checkpoint(target=target, training_mode=training_mode) and not force:
            self._load_checkpoint()
            self.logger.info("birth.resume checkpoint trades=%s ppo_steps=%s", self.cumulative_trades, self.ppo_steps)
        else:
            if self._read_checkpoint_payload() is not None and not force:
                self.logger.info(
                    "birth.checkpoint.skipped_resume target=%s training_mode=%s",
                    target,
                    training_mode,
                )
            self.cumulative_trades = 0
            self.ppo_steps = 0
            self.buffer.clear()
            self.current_policy = self.ppo_trainer.create_fresh_birth_policy()
            self._clear_checkpoint()
        if self.current_policy is None:
            self.current_policy = self.ppo_trainer.create_fresh_birth_policy()

        self._ppo_timesteps_planned_total = self._estimate_ppo_timesteps_planned(
            target_trades=target,
            chunk_size=chunk_size,
            ppo_update_timesteps=ppo_update_timesteps,
        )

        last_checkpoint = time.time()
        while self.cumulative_trades < target:
            if self._stop_requested():
                return self._handle_user_stop(target=target, ticks=ticks, training_mode=training_mode)

            remaining = max(0, target - self.cumulative_trades)
            chunk_target = min(chunk_size, remaining)
            chunk = self._simulate_chunk_with_policy(ticks=ticks, chunk_trades=chunk_target, policy=self.current_policy)
            if self._stop_requested():
                return self._handle_user_stop(target=target, ticks=ticks, training_mode=training_mode)
            chunk_trades = int(chunk.get("trades", 0) or 0)
            if chunk_trades <= 0:
                self._write_progress(
                    stage="failed",
                    message="Birth Phase stopte: simulatie leverde geen trades op.",
                    target_trades=target,
                    phase="simulation_stall",
                    progress_pct=self._overall_progress_pct(target),
                    **self._data_progress_extra(training_mode),
                )
                return self._result_payload(status="birth_failed", ticks=ticks)

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
                chunk_pnl=float(chunk.get("total_pnl", 0.0) or 0.0),
                recent_winrate=round(float(chunk.get("winrate", 0.0) or 0.0), 4),
                velocity_trades_per_sec=round(self._velocity_trades_per_sec(), 3),
                estimated_real_days=self._estimate_required_real_days(target),
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

    def _load_training_ticks(self, *, max_real_days: int, prefer_real_data_only: bool) -> list[dict[str, Any]]:
        self._write_progress(
            stage="loading_data",
            message="Historische marktdata laden voor Birth Phase.",
            target_trades=0,
            phase="loading_history",
            progress_pct=18.0,
        )
        limit = max(10_000, max_real_days * 2200)
        ticks = self._load_real_historical_ticks(days_back=max_real_days, limit=limit)
        self._loaded_real_days = max(1, int(math.ceil(float(len(ticks)) / float(_BIRTH_TICKS_PER_REAL_DAY)))) if ticks else 0
        if ticks and prefer_real_data_only:
            return ticks
        if ticks and not prefer_real_data_only:
            synth_needed = max(2_000, int(len(ticks) * 0.05))
            ticks.extend(self._generate_synthetic_ticks(synth_needed, start_price=float(ticks[-1].get("last", 0.0) or 5000.0)))
            return ticks
        if not prefer_real_data_only:
            return self._generate_synthetic_ticks(max(20_000, max_real_days * 1000), start_price=5000.0)
        return []

    def _load_real_historical_ticks(self, *, days_back: int, limit: int) -> list[dict[str, Any]]:
        source = self.market_data_service
        if source is not None and hasattr(source, "load_historical_ohlc_extended"):
            try:
                rows = source.load_historical_ohlc_extended(days_back=days_back, limit=limit, ticks_per_bar=4)
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

    # BIRTH ENGINE 2026-05-17
    def _simulate_chunk_with_policy(
        self,
        *,
        ticks: list[dict[str, Any]],
        chunk_trades: int,
        policy: Any,
    ) -> dict[str, Any]:
        trades = 0
        wins = 0
        total_pnl = 0.0
        pnl_series: list[float] = []
        trajectories: list[dict[str, Any]] = []
        idx = 0
        position: dict[str, Any] | None = None
        local_limit = max(5_000, chunk_trades * 80)
        while trades < chunk_trades and idx < local_limit:
            if idx > 0 and idx % 1000 == 0 and self._stop_requested():
                break
            tick = ticks[idx % len(ticks)]
            idx += 1
            observation = self._build_observation(tick=tick, position=position)
            action = self._resolve_policy_action(policy=policy, observation=observation, tick=tick)
            if position is None and action["side"] != "HOLD":
                self._entry_counter += 1
                position = self._open_position(tick=tick, action=action, entry_tick=self._entry_counter)
                continue
            if position is None:
                continue
            exited, pnl, reason = self._check_exit(position=position, tick=tick, current_entry_index=self._entry_counter)
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
        return {
            "trades": trades,
            "total_pnl": round(total_pnl, 6),
            "winrate": float(wins) / float(max(1, trades)),
            "trajectories": trajectories,
            "pnl_series": pnl_series,
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

    def _resolve_policy_action(self, *, policy: Any, observation: dict[str, Any], tick: dict[str, Any]) -> dict[str, Any]:
        infer = getattr(self.ppo_trainer, "infer_live_action", None)
        if callable(infer):
            try:
                action = infer(np.asarray([observation["price"]], dtype=np.float32))
            except Exception:
                action = None
            parsed = self._parse_action(action)
            if parsed["side"] != "HOLD":
                return parsed
        return self._bootstrap_action(observation=observation, tick=tick)

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
        if "TREND" in regime and imbalance >= 1.0:
            side = "BUY"
        elif "TREND" in regime and imbalance < 1.0:
            side = "SELL"
        elif imbalance > 1.2:
            side = "BUY"
        elif imbalance < 0.8:
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
