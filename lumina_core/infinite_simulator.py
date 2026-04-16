# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import json
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

from lumina_core.engine.valuation_engine import ValuationEngine


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

    def run_nightly(self) -> dict[str, Any]:
        start = time.time()
        real_ticks = self._load_real_historical_ticks(days_back=45, limit=150000)
        synthetic_ticks = self._generate_synthetic_ticks(
            n_ticks=max(250000, len(real_ticks) * 3),
            seed=int(time.time()) % 1_000_000,
            start_price=float(real_ticks[-1]["last"]) if real_ticks else 5000.0,
        )

        ticks = real_ticks + synthetic_ticks
        if not ticks:
            return {"status": "no_data", "trades": 0}

        summary = self._run_parallel_simulation(ticks, self.target_trades_per_night)
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

        orchestrator = getattr(getattr(self.runtime, "engine", None), "meta_agent_orchestrator", None)
        if orchestrator is not None and hasattr(orchestrator, "run_nightly_reflection"):
            try:
                orchestrator.run_nightly_reflection(
                    nightly_report=report,
                    dry_run=str(getattr(self.runtime.engine.config, "trade_mode", "paper")).strip().lower() in {"sim", "paper"},
                )
            except Exception:
                pass
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
        payloads = [
            {
                "ticks": ticks,
                "target_trades": per_worker,
                "seed": int(time.time()) + i * 13,
                "point_value": self.point_value,
                "symbol": str(getattr(self.runtime, "INSTRUMENT", getattr(self.runtime.engine.config, "instrument", "MES"))),
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
        except Exception:
            with mp.Pool(processes=worker_count) as pool:
                results = pool.map(_simulate_worker, payloads)

        total_trades = int(sum(int(r.get("trades", 0)) for r in results))
        total_wins = int(sum(int(r.get("wins", 0)) for r in results))
        net_pnl = float(sum(float(r.get("net_pnl", 0.0)) for r in results))
        sharpes = [float(r.get("sharpe", 0.0)) for r in results]
        samples: list[dict[str, Any]] = []
        for r in results:
            samples.extend(list(r.get("samples", [])))

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
                f"Sim trade {s.get('regime','NEUTRAL')} qty={s.get('qty',1)} "
                f"entry={float(s.get('entry',0.0)):.2f} exit={float(s.get('exit',0.0)):.2f} "
                f"pnl={float(s.get('pnl',0.0)):.2f}"
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
        except Exception:
            return

    def _train_rl(self, ticks: list[dict[str, Any]]) -> None:
        if self.ppo_trainer is None:
            return
        try:
            # Keep training set bounded for nightly cycle.
            train_rows = ticks[-200000:]
            self.ppo_trainer.train_nightly_on_infinite_simulator(train_rows, timesteps=300000)
        except Exception:
            return
