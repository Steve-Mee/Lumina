# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import json
import logging
import math
import multiprocessing as mp
import os
import random
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.evolution.simulator_data_support import (
    MIN_SIMULATOR_BARS,
    require_real_simulator_data_strict,
    select_first_boot_ppo_bars,
)
from lumina_core.first_boot_progress import resolve_ppo_progress_interval
from lumina_core.first_boot_ui import (
    FIRST_BOOT_EST_TRADES_PER_REAL_DAY as _FIRST_BOOT_TRADES_PER_REAL_DAY,
    normalize_first_boot_training_trades,
)
from lumina_core.logging_utils import correlation_id, get_logger

logger = get_logger("lumina.simulation.nightly")
_FIRST_BOOT_TICKS_PER_REAL_DAY = 1560
_FIRST_BOOT_PAUSE_FLAG_PATH = Path("state/first_boot_pause_requested")
_FIRST_BOOT_CHECKPOINT_PATH = Path("state/first_boot_checkpoint.json")
_FIRST_BOOT_CHUNK_DEFAULT_TRADES = 100_000


def _notify_first_boot_training_progress(stage: str, message: str, **extra: object) -> None:
    """Update ``state/first_boot_progress.json`` during long first-boot phases (lazy-import avoids cycles)."""
    try:
        from lumina_core.engine.runtime_entrypoint import _write_first_boot_progress

        _write_first_boot_progress(stage, message, **extra)
    except Exception:
        logger.debug("first_boot.training_progress.notify_failed", exc_info=True)


def _is_first_boot_pause_requested() -> bool:
    return _FIRST_BOOT_PAUSE_FLAG_PATH.exists()


def _load_first_boot_checkpoint(requested_trades: int) -> dict[str, Any]:
    if not _FIRST_BOOT_CHECKPOINT_PATH.exists():
        return {}
    try:
        payload = json.loads(_FIRST_BOOT_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("first_boot.checkpoint.read_failed", exc_info=True)
        return {}
    if not isinstance(payload, dict):
        return {}
    if int(payload.get("requested_trades", 0) or 0) != int(requested_trades):
        return {}
    return payload


def _write_first_boot_checkpoint(payload: dict[str, Any]) -> None:
    try:
        _FIRST_BOOT_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _FIRST_BOOT_CHECKPOINT_PATH.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.warning("first_boot.checkpoint.write_failed", exc_info=True)


def _clear_first_boot_checkpoint() -> None:
    try:
        if _FIRST_BOOT_CHECKPOINT_PATH.exists():
            _FIRST_BOOT_CHECKPOINT_PATH.unlink()
    except Exception:
        logger.warning("first_boot.checkpoint.clear_failed", exc_info=True)


def _simulate_worker(payload: dict[str, Any]) -> dict[str, Any]:
    ticks: list[dict[str, Any]] = payload["ticks"]
    target_trades = int(payload["target_trades"])
    seed = int(payload["seed"])
    point_value = float(payload.get("point_value", 5.0))
    max_hold_ticks = int(payload.get("max_hold_ticks", 24))
    symbol = str(payload.get("symbol", "MES"))
    valuation = ValuationEngine()

    rng = random.Random(seed)
    idx = 0
    trades = 0
    wins = 0
    pnl_values: list[float] = []
    sample_experiences: list[dict[str, Any]] = []

    position = 0
    qty = 0
    entry = 0.0
    stop = 0.0
    target = 0.0
    hold_ticks = 0

    while trades < target_trades and ticks:
        tick = ticks[idx % len(ticks)]
        idx += 1

        price = float(tick.get("last", 0.0))
        if price <= 0:
            continue

        volume = float(tick.get("volume", 0.0))
        regime = str(tick.get("regime", "NEUTRAL")).upper()
        imbalance = float(tick.get("imbalance", 1.0))

        if position == 0:
            entry_prob = 0.22 if "TREND" in regime else 0.14
            if rng.random() < entry_prob:
                side = 1 if (imbalance >= 1.0 and rng.random() < 0.55) else -1
                if "RANGING" in regime and rng.random() < 0.6:
                    side *= -1
                position = side
                qty = rng.randint(1, 4)
                entry = price
                stop_dist = (0.7 + rng.random() * 0.8) * 0.25
                target_dist = (1.2 + rng.random() * 1.8) * 0.25
                if side > 0:
                    stop = price - stop_dist
                    target = price + target_dist
                else:
                    stop = price + stop_dist
                    target = price - target_dist
                hold_ticks = 0
            continue

        hold_ticks += 1
        stop_hit = (position > 0 and price <= stop) or (position < 0 and price >= stop)
        target_hit = (position > 0 and price >= target) or (position < 0 and price <= target)
        timed_exit = hold_ticks >= max_hold_ticks

        if stop_hit or target_hit or timed_exit:
            slippage_ticks = valuation.slippage_ticks(
                volume=volume,
                avg_volume=max(1.0, volume),
                regime=regime,
                slippage_scale=1.0,
            )
            fill = valuation.apply_exit_fill(
                symbol=symbol,
                price=price,
                side=position,
                slippage_ticks=slippage_ticks,
            )

            gross = valuation.pnl_dollars(
                symbol=symbol,
                entry_price=entry,
                exit_price=fill,
                side=position,
                quantity=qty,
            )
            # Keep compatibility with existing point value calibration if payload overrides symbol spec.
            if abs(point_value - valuation.point_value(symbol)) > 1e-9:
                gross = (fill - entry) * position * qty * point_value
            net = gross - valuation.commission_dollars(symbol=symbol, quantity=qty, sides=2)

            pnl_values.append(net)
            trades += 1
            if net > 0:
                wins += 1

            if len(sample_experiences) < 1500 and (trades % 20 == 0):
                sample_experiences.append(
                    {
                        "regime": regime,
                        "entry": entry,
                        "exit": fill,
                        "qty": qty,
                        "pnl": net,
                        "reason": "target" if target_hit else "stop" if stop_hit else "timed",
                    }
                )

            position = 0
            qty = 0
            entry = 0.0
            stop = 0.0
            target = 0.0
            hold_ticks = 0

    mean_pnl = float(statistics.mean(pnl_values)) if pnl_values else 0.0
    std_pnl = float(statistics.pstdev(pnl_values)) if len(pnl_values) > 1 else 0.0
    sharpe = (mean_pnl / std_pnl) * math.sqrt(252.0) if std_pnl > 1e-9 else 0.0

    return {
        "trades": trades,
        "wins": wins,
        "net_pnl": float(sum(pnl_values)),
        "mean_pnl": mean_pnl,
        "sharpe": float(sharpe),
        "samples": sample_experiences,
    }


@dataclass(slots=True)
class InfiniteSimulator:
    runtime: Any
    market_data_service: Any
    ppo_trainer: Any | None = None
    workers: int = max(2, (os.cpu_count() or 4) - 1)
    target_trades_per_night: int = 1_000_000
    point_value: float = 5.0

    def run_first_boot_training(
        self,
        *,
        target_trades: int,
        prefer_real_data_only: bool,
        max_real_days: int,
        allow_minimal_synthetic_fallback: bool = False,
    ) -> dict[str, Any]:
        # BIRTH ENGINE 2026-05-17
        logger.warning(
            "InfiniteSimulator.run_first_boot_training is deprecated for normal runtime flow; "
            "use LuminaBirthEngine as canonical first-boot path."
        )
        start = time.time()
        run_id = datetime.now(timezone.utc).strftime("fb-%Y%m%d%H%M%S")
        requested_trades = normalize_first_boot_training_trades(target_trades)
        max_days = max(30, min(3_650, int(max_real_days)))
        estimated_real_days = int(math.ceil(float(requested_trades) / float(_FIRST_BOOT_TRADES_PER_REAL_DAY)))
        chunk_cfg = ConfigLoader.section("first_boot", default={}) or {}
        chunk_trades = _FIRST_BOOT_CHUNK_DEFAULT_TRADES
        if isinstance(chunk_cfg, dict):
            try:
                chunk_trades = int(chunk_cfg.get("chunk_trades", _FIRST_BOOT_CHUNK_DEFAULT_TRADES) or _FIRST_BOOT_CHUNK_DEFAULT_TRADES)
            except Exception:
                chunk_trades = _FIRST_BOOT_CHUNK_DEFAULT_TRADES
        chunk_trades = max(10_000, min(1_000_000, chunk_trades))
        logger.info(
            "simulation.first_boot.start",
            extra={
                "event_data": {
                    "event": "simulation.first_boot.start",
                    "run_id": run_id,
                    "target_trades": requested_trades,
                    "prefer_real_data_only": bool(prefer_real_data_only),
                    "max_real_days": max_days,
                    "estimated_real_days": estimated_real_days,
                    "chunk_trades": chunk_trades,
                }
            },
        )
        logger.info("Laden van %s dagen echte historische data...", max_days)
        real_ticks = self._load_real_historical_ticks(days_back=max_days, limit=max(150000, max_days * 2000))
        if not real_ticks:
            return {
                "status": "blocked_no_real_data",
                "requested_trades": requested_trades,
                "target_trades": 0,
                "trades": 0,
                "executed_trades": 0,
                "real_ticks": 0,
                "synthetic_ticks": 0,
                "estimated_real_days": estimated_real_days,
                "actual_real_days_loaded": 0,
                "real_days_loaded": 0,
                "synthetic_pct": 0.0,
                "synthetic_ratio": 0.0,
            }

        actual_real_days = max(1, int(math.ceil(len(real_ticks) / float(_FIRST_BOOT_TICKS_PER_REAL_DAY))))
        _notify_first_boot_training_progress(
            "training_running",
            f"Historische data geladen: {len(real_ticks)} ticks (~{actual_real_days} dagen-equivalent), "
            f"tot {max_days} dagen opgevraagd.",
            actual_real_days_loaded=actual_real_days,
            estimated_real_days=estimated_real_days,
            max_real_days=max_days,
            real_ticks=len(real_ticks),
            progress_pct=40,
            phase="historical_loaded",
        )
        configured_real_trade_capacity = int(max_days * _FIRST_BOOT_TRADES_PER_REAL_DAY)
        actual_real_trade_capacity = int(actual_real_days * _FIRST_BOOT_TRADES_PER_REAL_DAY)
        target_effective = requested_trades
        synthetic_ticks: list[dict[str, Any]] = []
        status = "ok_real_only" if prefer_real_data_only else "ok_flexible_data_policy"
        if not prefer_real_data_only:
            logger.info(
                "simulation.first_boot.flexible_data_policy",
                extra={
                    "event_data": {
                        "event": "simulation.first_boot.flexible_data_policy",
                        "run_id": run_id,
                        "reason": "prefer_real_data_only_disabled",
                    }
                },
            )

        if prefer_real_data_only and requested_trades > actual_real_trade_capacity:
            missing_trades = requested_trades - actual_real_trade_capacity
            synth_needed = max(5000, int(missing_trades * 4))
            synthetic_ticks = self._generate_synthetic_ticks(
                n_ticks=synth_needed,
                seed=int(time.time()) % 1_000_000,
                start_price=float(real_ticks[-1]["last"]) if real_ticks else 5000.0,
            )
            status = "ok_minimal_synthetic_fallback"
            _notify_first_boot_training_progress(
                "training_running",
                "First-boot target overschrijdt real-data capaciteit; minimale synthetische top-up wordt toegevoegd.",
                requested_trades=requested_trades,
                actual_real_trade_capacity=actual_real_trade_capacity,
                synthetic_ticks=len(synthetic_ticks),
                progress_pct=50,
                phase="synthetic_top_up",
            )
            logger.warning(
                "simulation.first_boot.synthetic_fallback",
                extra={
                    "event_data": {
                        "event": "simulation.first_boot.synthetic_fallback",
                        "run_id": run_id,
                        "missing_trades": missing_trades,
                        "synthetic_ticks": len(synthetic_ticks),
                        "requested_trades": requested_trades,
                        "actual_real_trade_capacity": actual_real_trade_capacity,
                        "allow_minimal_synthetic_fallback_requested": bool(allow_minimal_synthetic_fallback),
                        "forced_for_target_completion": True,
                    }
                },
            )

        ticks = list(real_ticks) + list(synthetic_ticks)
        checkpoint = _load_first_boot_checkpoint(requested_trades)
        cumulative_trades = max(0, int(checkpoint.get("cumulative_trades", 0) or 0))
        chunk_index = max(0, int(checkpoint.get("chunk_index", 0) or 0))
        total_wins = max(0, int(checkpoint.get("wins", 0) or 0))
        total_net_pnl = float(checkpoint.get("net_pnl", 0.0) or 0.0)
        chunk_sharpes_raw = checkpoint.get("chunk_sharpes", [])
        chunk_sharpes = [float(x) for x in chunk_sharpes_raw] if isinstance(chunk_sharpes_raw, list) else []
        if cumulative_trades > requested_trades:
            cumulative_trades = requested_trades
        _notify_first_boot_training_progress(
            "training_running",
            f"Parallel SIM wordt uitgevoerd in chunks (doel {target_effective} trades, chunk {chunk_trades} trades).",
            target_trades_effective=target_effective,
            workers=int(self.workers),
            cumulative_trades=cumulative_trades,
            requested_trades=requested_trades,
            progress_pct=52,
            phase="parallel_simulation",
            velocity_trades_per_sec=0.0,
            eta_minutes=None,
        )
        sim_started_at = time.time()
        while cumulative_trades < requested_trades:
            if _is_first_boot_pause_requested():
                elapsed_sim_sec = max(1.0, time.time() - sim_started_at)
                live_tps = float(cumulative_trades) / elapsed_sim_sec if cumulative_trades > 0 else 0.0
                remaining_trades = max(0, requested_trades - cumulative_trades)
                eta_minutes = None
                if elapsed_sim_sec >= 30.0 and live_tps > 0:
                    eta_minutes = round((float(remaining_trades) / live_tps) / 60.0, 1)
                pause_msg = (
                    f"Pauzeverzoek ontvangen. First-boot training pauzeert op {cumulative_trades:,}/{requested_trades:,} trades."
                )
                _notify_first_boot_training_progress(
                    "paused",
                    pause_msg,
                    cumulative_trades=cumulative_trades,
                    remaining_trades=remaining_trades,
                    requested_trades=requested_trades,
                    progress_pct=min(99.0, (100.0 * float(cumulative_trades) / float(max(1, requested_trades)))),
                    phase="paused",
                    velocity_trades_per_sec=round(live_tps, 3),
                    eta_minutes=eta_minutes,
                )
                _write_first_boot_checkpoint(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "run_id": run_id,
                        "requested_trades": requested_trades,
                        "cumulative_trades": cumulative_trades,
                        "chunk_index": chunk_index,
                        "wins": total_wins,
                        "net_pnl": total_net_pnl,
                        "chunk_sharpes": chunk_sharpes,
                    }
                )
                return {
                    "timestamp": datetime.now().isoformat(),
                    "status": "paused",
                    "requested_trades": requested_trades,
                    "target_trades": requested_trades,
                    "trades": cumulative_trades,
                    "executed_trades": cumulative_trades,
                    "wins": total_wins,
                    "net_pnl": total_net_pnl,
                    "mean_worker_sharpe": float(statistics.mean(chunk_sharpes) if chunk_sharpes else 0.0),
                    "estimated_real_days": estimated_real_days,
                    "actual_real_days_loaded": actual_real_days,
                    "real_days_loaded": actual_real_days,
                    "max_real_days": max_days,
                    "configured_real_trade_capacity": configured_real_trade_capacity,
                    "actual_real_trade_capacity": actual_real_trade_capacity,
                    "real_ticks": len(real_ticks),
                    "synthetic_ticks": len(synthetic_ticks),
                    "synthetic_pct": round((float(len(synthetic_ticks)) / float(max(1, len(ticks)))) * 100.0, 3),
                    "synthetic_ratio": round(float(len(synthetic_ticks)) / float(max(1, len(ticks))), 6),
                    "elapsed_sec": round(time.time() - start, 2),
                }
            chunk_target = min(chunk_trades, requested_trades - cumulative_trades)
            summary = self._run_parallel_simulation(ticks, chunk_target)
            chunk_done = int(summary.get("trades", 0) or 0)
            chunk_done = max(0, min(chunk_target, chunk_done))
            cumulative_trades += chunk_done
            chunk_wins = int(round(float(summary.get("winrate", 0.0)) * float(chunk_done)))
            total_wins += max(0, chunk_wins)
            total_net_pnl += float(summary.get("net_pnl", 0.0) or 0.0)
            chunk_sharpes.append(float(summary.get("mean_worker_sharpe", 0.0) or 0.0))
            chunk_index += 1
            _write_first_boot_checkpoint(
                {
                    "timestamp": datetime.now().isoformat(),
                    "run_id": run_id,
                    "requested_trades": requested_trades,
                    "cumulative_trades": cumulative_trades,
                    "chunk_index": chunk_index,
                    "wins": total_wins,
                    "net_pnl": total_net_pnl,
                    "chunk_sharpes": chunk_sharpes,
                }
            )
            elapsed_sim_sec = max(1.0, time.time() - sim_started_at)
            live_tps = float(cumulative_trades) / elapsed_sim_sec if cumulative_trades > 0 else 0.0
            remaining_trades = max(0, requested_trades - cumulative_trades)
            eta_minutes = None
            if elapsed_sim_sec >= 30.0 and live_tps > 0:
                eta_minutes = round((float(remaining_trades) / live_tps) / 60.0, 1)
            _notify_first_boot_training_progress(
                "training_running",
                f"Parallel SIM chunk {chunk_index} voltooid ({cumulative_trades:,}/{requested_trades:,} trades).",
                chunk_index=chunk_index,
                chunk_trades=chunk_done,
                cumulative_trades=cumulative_trades,
                requested_trades=requested_trades,
                remaining_trades=remaining_trades,
                progress_pct=min(67.0, 52.0 + (15.0 * float(cumulative_trades) / float(max(1, requested_trades)))),
                phase="parallel_simulation",
                velocity_trades_per_sec=round(live_tps, 3),
                eta_minutes=eta_minutes,
            )
            if chunk_done <= 0:
                break
        sim_resume_only = cumulative_trades >= requested_trades and chunk_index > 0
        if sim_resume_only:
            _notify_first_boot_training_progress(
                "training_running",
                "SIM-checkpoint al compleet; PPO policy-training wordt hervat vanaf bestaande first-boot status.",
                sim_trades=int(cumulative_trades),
                sim_completed=True,
                ppo_resume_only=True,
                progress_pct=68,
                phase="ppo_training",
                eta_minutes=None,
            )
        else:
            _notify_first_boot_training_progress(
                "training_running",
                "PPO policy-training (Stable-Baselines3); SIM-deel afgerond, neural net trainen…",
                sim_trades=int(cumulative_trades),
                sim_completed=bool(cumulative_trades >= requested_trades),
                ppo_resume_only=False,
                progress_pct=68,
                phase="ppo_training",
                eta_minutes=None,
            )
        ppo_error: str | None = None
        try:
            self._train_rl(ticks)
        except Exception as exc:
            ppo_error = str(exc)
            status = "ppo_failed"

        synthetic_pct = float(len(synthetic_ticks) / max(1, len(ticks)))
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "requested_trades": requested_trades,
            "target_trades": requested_trades,
            "trades": int(cumulative_trades),
            "executed_trades": int(cumulative_trades),
            "wins": int(total_wins),
            "net_pnl": float(total_net_pnl),
            "mean_worker_sharpe": float(statistics.mean(chunk_sharpes) if chunk_sharpes else 0.0),
            "estimated_real_days": estimated_real_days,
            "actual_real_days_loaded": actual_real_days,
            "real_days_loaded": actual_real_days,
            "max_real_days": max_days,
            "configured_real_trade_capacity": configured_real_trade_capacity,
            "actual_real_trade_capacity": actual_real_trade_capacity,
            "real_ticks": len(real_ticks),
            "synthetic_ticks": len(synthetic_ticks),
            "synthetic_pct": round(synthetic_pct * 100.0, 3),
            "synthetic_ratio": round(synthetic_pct, 6),
            "chunk_trades": chunk_trades,
            "chunk_count": chunk_index,
            "elapsed_sec": round(time.time() - start, 2),
            "sim_completed": bool(cumulative_trades >= requested_trades),
            "ppo_resume_only": bool(sim_resume_only),
        }
        if ppo_error:
            report["ppo_error"] = ppo_error
        out_dir = Path("journal/simulator")
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / f"first_boot_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
        if ppo_error is None:
            _clear_first_boot_checkpoint()
            if _FIRST_BOOT_PAUSE_FLAG_PATH.exists():
                try:
                    _FIRST_BOOT_PAUSE_FLAG_PATH.unlink()
                except Exception:
                    logger.warning("first_boot.pause_flag.clear_failed", exc_info=True)
        logger.info(
            "simulation.first_boot.complete",
            extra={
                "event_data": {
                    "event": "simulation.first_boot.complete",
                    "run_id": run_id,
                    "status": status,
                    "target_trades": requested_trades,
                    "trades": int(report.get("trades", 0)),
                    "estimated_real_days": estimated_real_days,
                    "actual_real_days_loaded": actual_real_days,
                    "real_ticks": len(real_ticks),
                    "synthetic_ticks": len(synthetic_ticks),
                    "synthetic_pct": float(report["synthetic_pct"]),
                }
            },
        )
        return report

    def run_nightly(self) -> dict[str, Any]:
        start = time.time()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        with correlation_id(run_id):
            try:
                logger.info(
                    "simulation.nightly.start",
                    extra={
                        "event_data": {
                            "event": "simulation.nightly.start",
                            "run_id": run_id,
                            "target_trades": int(self.target_trades_per_night),
                        }
                    },
                )
            except Exception:
                pass
        real_ticks = self._load_real_historical_ticks(days_back=45, limit=150000)
        historical_only = require_real_simulator_data_strict()
        if historical_only:
            synthetic_ticks: list[dict[str, Any]] = []
            if len(real_ticks) < MIN_SIMULATOR_BARS:
                return {
                    "status": "insufficient_historical_data",
                    "real_ticks": len(real_ticks),
                    "trades": 0,
                    "wins": 0,
                    "net_pnl": 0.0,
                    "sharpe": 0.0,
                    "samples": [],
                }
            ticks = list(real_ticks)
        else:
            synthetic_ticks = self._generate_synthetic_ticks(
                n_ticks=max(250000, len(real_ticks) * 3),
                seed=int(time.time()) % 1_000_000,
                start_price=float(real_ticks[-1]["last"]) if real_ticks else 5000.0,
            )
            ticks = real_ticks + synthetic_ticks
        if not ticks:
            return {"status": "no_data", "trades": 0}

        try:
            logger.info(
                "simulation.nightly.ticks_ready",
                extra={
                    "event_data": {
                        "event": "simulation.nightly.ticks_ready",
                        "run_id": run_id,
                        "real_ticks": len(real_ticks),
                        "total_ticks": len(ticks),
                        "synthetic_ticks": len(synthetic_ticks),
                        "target_trades": int(self.target_trades_per_night),
                    }
                },
            )
        except Exception:
            pass

        summary = self._run_parallel_simulation(ticks, self.target_trades_per_night)
        try:
            logger.info(
                "simulation.nightly.worker_summary",
                extra={
                    "event_data": {
                        "event": "simulation.nightly.worker_summary",
                        "run_id": run_id,
                        "trades": int(summary.get("trades", 0)),
                        "net_pnl": float(summary.get("net_pnl", 0.0)),
                        "sharpe": float(summary.get("mean_worker_sharpe", 0.0)),
                    }
                },
            )
        except Exception:
            pass
        self._feed_vector_db(summary)
        self._evolve_bible(summary)
        self._train_rl(ticks)

        out_dir = Path("journal/simulator")
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "ok",
            "workers": self.workers,
            "real_ticks": len(real_ticks),
            "synthetic_ticks": len(synthetic_ticks),
            "elapsed_sec": round(time.time() - start, 2),
            **summary,
        }
        report_path = out_dir / f"nightly_sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
        try:
            logger.info(
                "simulation.nightly.complete",
                extra={
                    "event_data": {
                        "event": "simulation.nightly.complete",
                        "run_id": run_id,
                        "real_ticks": len(real_ticks),
                        "synthetic_ticks": len(synthetic_ticks),
                        "total_trades": int(report.get("trades", 0)),
                        "overall_sharpe": float(report.get("mean_worker_sharpe", 0.0)),
                    }
                },
            )
        except Exception:
            pass

        orchestrator = getattr(getattr(self.runtime, "engine", None), "meta_agent_orchestrator", None)
        if orchestrator is not None and hasattr(orchestrator, "run_nightly_reflection"):
            try:
                reflection_report = dict(report)
                if len(real_ticks) >= MIN_SIMULATOR_BARS:
                    cap = 12000
                    neuro_cfg = ConfigLoader.section("evolution", "neuroevolution", default={}) or {}
                    if isinstance(neuro_cfg, dict):
                        cap = max(MIN_SIMULATOR_BARS, int(neuro_cfg.get("max_bars_in_report", cap) or cap))
                    reflection_report["simulator_data"] = list(real_ticks[-cap:])
                    reflection_report["neuro_simulator_data_source"] = "simulator_real_ticks"
                orchestrator.run_nightly_reflection(
                    nightly_report=reflection_report,
                    dry_run=str(getattr(self.runtime.engine.config, "trade_mode", "paper")).strip().lower()
                    in {"sim", "paper"},
                )
            except Exception:
                logger.exception("InfiniteSimulator failed during nightly reflection handoff")
        return report

    def run_nightly_simulation(self, *, num_trades_total: int = 1_000_000) -> dict[str, Any]:
        self.target_trades_per_night = max(1000, int(num_trades_total))
        return self.run_nightly()

    def _load_real_historical_ticks(self, days_back: int, limit: int) -> list[dict[str, Any]]:
        if hasattr(self.market_data_service, "load_historical_ohlc_extended"):
            ticks = self.market_data_service.load_historical_ohlc_extended(
                days_back=days_back,
                limit=limit,
                ticks_per_bar=4,
            )
            return ticks if isinstance(ticks, list) else []

        ohlc = getattr(self.runtime, "ohlc_1min", None)
        if ohlc is None or len(ohlc) == 0:
            return []

        rows = ohlc.tail(limit).to_dict("records")
        ticks: list[dict[str, Any]] = []
        for row in rows:
            price = float(row.get("close", 0.0))
            if price <= 0:
                continue
            ticks.append(
                {
                    "timestamp": str(row.get("timestamp", "")),
                    "last": price,
                    "bid": price - 0.125,
                    "ask": price + 0.125,
                    "volume": int(row.get("volume", 1)),
                }
            )
        return ticks

    def _generate_synthetic_ticks(self, n_ticks: int, seed: int, start_price: float = 5000.0) -> list[dict[str, Any]]:
        rng = random.Random(seed)
        regimes = ["TRENDING", "RANGING", "VOLATILE"]
        transition = {
            "TRENDING": [0.86, 0.10, 0.04],
            "RANGING": [0.12, 0.82, 0.06],
            "VOLATILE": [0.22, 0.18, 0.60],
        }

        regime = "RANGING"
        price = max(10.0, start_price)
        volume = 1500.0
        ticks: list[dict[str, Any]] = []

        for i in range(n_ticks):
            probs = transition[regime]
            regime = rng.choices(regimes, probs)[0]

            if regime == "TRENDING":
                drift = 0.00015 if rng.random() > 0.4 else -0.00012
                sigma = 0.0012
            elif regime == "VOLATILE":
                drift = 0.0
                sigma = 0.0038
            else:
                drift = 0.0
                sigma = 0.0010

            # Fat tails via Student-t shock and occasional jump events.
            fat_tail = rng.gauss(0.0, sigma) + (rng.random() - 0.5) * sigma * 4.0
            if rng.random() < 0.004:
                fat_tail += rng.choice([-1.0, 1.0]) * sigma * (4.0 + rng.random() * 5.0)

            next_price = price * (1.0 + drift + fat_tail)
            price = max(10.0, next_price) if math.isfinite(next_price) else 10.0

            # Bound synthetic volume growth to avoid float overflow in long runs.
            next_volume = volume * (0.95 + rng.random() * 0.1) * (1.3 if regime == "VOLATILE" else 1.0)
            if not math.isfinite(next_volume):
                next_volume = 100.0
            volume = min(10_000_000.0, max(100.0, next_volume))
            spread = 0.25 if regime != "VOLATILE" else 0.5
            imbalance = 1.0 + (rng.random() - 0.5) * (0.6 if regime == "RANGING" else 1.2)

            ticks.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "last": float(price),
                    "bid": float(price - spread / 2.0),
                    "ask": float(price + spread / 2.0),
                    "volume": int(volume),
                    "regime": regime,
                    "imbalance": float(max(0.2, imbalance)),
                    "source": "synthetic",
                    "idx": i,
                }
            )

        return ticks

    def _run_parallel_simulation(self, ticks: list[dict[str, Any]], total_target: int) -> dict[str, Any]:
        worker_count = max(1, self.workers)
        per_worker = math.ceil(total_target / worker_count)
        try:
            est_mb = round(len(ticks) * 200 / (1024 * 1024), 1)
            logger.info(
                "simulation.parallel_sim.begin",
                extra={
                    "event_data": {
                        "event": "simulation.parallel_sim.begin",
                        "total_target_trades": int(total_target),
                        "workers": int(worker_count),
                        "per_worker_target_trades": int(per_worker),
                        "tick_count": len(ticks),
                        "approx_tick_payload_mb_per_worker": est_mb,
                        "note": (
                            "CPU-bound tick replay; op Windows kan multiprocessing-pickle lang duren "
                            "voordat workers starten — geen deadlock."
                        ),
                    }
                },
            )
        except Exception:
            pass
        payloads = [
            {
                "ticks": ticks,
                "target_trades": per_worker,
                "seed": int(time.time()) + i * 13,
                "point_value": self.point_value,
                "symbol": str(
                    getattr(self.runtime, "INSTRUMENT", getattr(self.runtime.engine.config, "instrument", "MES"))
                ),
            }
            for i in range(worker_count)
        ]

        results: list[dict[str, Any]] = []
        ran_with = "multiprocessing"
        try:
            import ray  # type: ignore

            if not ray.is_initialized():
                ray.init(ignore_reinit_error=True, include_dashboard=False, logging_level=40)

            remote_fn = ray.remote(_simulate_worker)
            futures = [remote_fn.remote(p) for p in payloads]
            results = ray.get(futures)
            ran_with = "ray"
        except ModuleNotFoundError:
            logger.info(
                "simulation.parallel_ray_unavailable",
                extra={
                    "event_data": {
                        "event": "simulation.parallel_ray_unavailable",
                        "fallback": "multiprocessing",
                        "reason": "ray_not_installed",
                    }
                },
            )
            with mp.Pool(processes=worker_count) as pool:
                results = pool.map(_simulate_worker, payloads)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/infinite_simulator.py:346")
            with mp.Pool(processes=worker_count) as pool:
                results = pool.map(_simulate_worker, payloads)

        total_trades = int(sum(int(r.get("trades", 0)) for r in results))
        total_wins = int(sum(int(r.get("wins", 0)) for r in results))
        net_pnl = float(sum(float(r.get("net_pnl", 0.0)) for r in results))
        sharpes = [float(r.get("sharpe", 0.0)) for r in results]
        samples: list[dict[str, Any]] = []
        for r in results:
            samples.extend(list(r.get("samples", [])))

        try:
            logger.info(
                "simulation.parallel_sim.complete",
                extra={
                    "event_data": {
                        "event": "simulation.parallel_sim.complete",
                        "executor": ran_with,
                        "aggregate_trades": total_trades,
                        "workers": int(worker_count),
                    }
                },
            )
        except Exception:
            pass

        return {
            "executor": ran_with,
            "trades": total_trades,
            "winrate": float(total_wins / max(1, total_trades)),
            "net_pnl": net_pnl,
            "mean_worker_sharpe": float(statistics.mean(sharpes) if sharpes else 0.0),
            "sample_experiences": samples[:4000],
        }

    def _feed_vector_db(self, summary: dict[str, Any]) -> None:
        samples = list(summary.get("sample_experiences", []))
        store_fn = getattr(self.runtime, "store_experience_to_vector_db", None)
        if not callable(store_fn):
            return

        for s in samples[:800]:
            context = (
                f"Sim trade {s.get('regime', 'NEUTRAL')} qty={s.get('qty', 1)} "
                f"entry={float(s.get('entry', 0.0)):.2f} exit={float(s.get('exit', 0.0)):.2f} "
                f"pnl={float(s.get('pnl', 0.0)):.2f}"
            )
            metadata = {
                "type": "infinite_sim_trade",
                "outcome": "win" if float(s.get("pnl", 0.0)) > 0 else "loss",
                "date": datetime.now().isoformat(),
                "regime": s.get("regime", "NEUTRAL"),
            }
            try:
                store_fn(context, metadata)
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/infinite_simulator.py:387")
                continue

    def _evolve_bible(self, summary: dict[str, Any]) -> None:
        evolve_fn = getattr(self.runtime, "evolve_bible", None)
        if not callable(evolve_fn):
            return

        winrate = float(summary.get("winrate", 0.0))
        net_pnl = float(summary.get("net_pnl", 0.0))
        updates = {
            "last_reflection": (
                f"{datetime.now().date()} InfiniteSim nightly: trades={int(summary.get('trades', 0))}, "
                f"winrate={winrate:.2%}, net_pnl={net_pnl:.2f}"
            ),
            "probability_model": {
                "base_winrate": round(max(0.2, min(0.9, winrate)), 3),
                "confluence_bonus": 0.24 if winrate >= 0.5 else 0.18,
                "risk_penalty": 0.06 if net_pnl >= 0 else 0.09,
            },
            "filters": [
                "volume_delta > 1.8x avg",
                "tape_imbalance > 1.4",
                "fast_path_confidence > 0.75",
            ],
        }
        try:
            evolve_fn(updates)
            try:
                logger.info(
                    "simulation.bible_rules_appended",
                    extra={
                        "event_data": {
                            "event": "simulation.bible_rules_appended",
                            "count": len(list(updates.get("filters", []))),
                            "top_fitness": float(summary.get("winrate", 0.0)),
                        }
                    },
                )
            except Exception:
                pass
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/infinite_simulator.py:415")
            return

    def _train_rl(self, ticks: list[dict[str, Any]]) -> None:
        if self.ppo_trainer is None:
            raise RuntimeError("ppo_trainer unavailable")
        try:
            # Keep training set bounded for nightly cycle.
            train_rows = select_first_boot_ppo_bars(ticks, cap=200_000)
            first_boot_cfg = ConfigLoader.section("first_boot", default={}) or {}
            interval_payload = {"first_boot": first_boot_cfg} if isinstance(first_boot_cfg, dict) else {}
            interval = resolve_ppo_progress_interval(interval_payload)
            self.ppo_trainer.train_nightly_on_infinite_simulator(
                train_rows,
                timesteps=300000,
                report_first_boot_progress=True,
                ppo_progress_interval=interval,
            )
        except Exception as exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/infinite_simulator.py:425")
            _notify_first_boot_training_progress(
                "failed",
                "PPO policy-training is mislukt; runtime blijft fail-closed.",
                phase="ppo_training_failed",
                ppo_error=str(exc)[:500],
            )
            raise
