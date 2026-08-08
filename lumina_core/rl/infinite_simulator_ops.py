"""InfiniteSimulator data/sim/train ops (M5 extract)."""
from __future__ import annotations

import math
import random
import time
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.rl.infinite_simulator_worker import (
    _notify_first_boot_training_progress,
    _simulate_worker,
)

logger = get_logger("lumina.simulation.nightly")


class InfiniteSimulatorOpsMixin:
    def _load_real_historical_ticks(self, days_back: int, limit: int) -> list[dict[str, Any]]:
        from lumina_core.birth.history_loader import load_historical_ticks

        return load_historical_ticks(
            market_data_service=self.market_data_service,
            runtime=self.runtime,
            days_back=days_back,
            limit=limit,
        )

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
