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
from lumina_core.logging_utils import correlation_id, get_logger

logger = get_logger("lumina.simulation.nightly")


def _notify_first_boot_training_progress(stage: str, message: str, **extra: object) -> None:
    """Update ``state/first_boot_progress.json`` during long first-boot phases (lazy-import avoids cycles)."""
    try:
        from lumina_core.engine.runtime_entrypoint import _write_first_boot_progress

        _write_first_boot_progress(stage, message, **extra)
    except Exception:
        logger.debug("first_boot.training_progress.notify_failed", exc_info=True)


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


__all__ = ["_notify_first_boot_training_progress", "_simulate_worker"]
