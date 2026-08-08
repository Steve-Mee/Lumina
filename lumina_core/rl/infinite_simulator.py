"""Infinite multi-day / nightly simulator (M5 façade).

Worker helpers: ``infinite_simulator_worker``.
Ops (load/sim/train): ``infinite_simulator_ops``.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.simulator_data_support import (
    MIN_SIMULATOR_BARS,
    require_real_simulator_data_strict,
)
from lumina_core.logging_utils import correlation_id, get_logger
from lumina_core.rl.infinite_simulator_ops import InfiniteSimulatorOpsMixin

logger = get_logger("lumina.simulation.nightly")


class InfiniteSimulator(InfiniteSimulatorOpsMixin):
    """Nightly high-volume SIM replay + RL feed (never REAL capital)."""

    def __init__(
        self,
        *,
        runtime: Any,
        market_data_service: Any,
        ppo_trainer: Any = None,
        workers: int | None = None,
        target_trades_per_night: int = 1_000_000,
        point_value: float = 5.0,
    ) -> None:
        import os

        self.runtime = runtime
        self.market_data_service = market_data_service
        self.ppo_trainer = ppo_trainer
        cpu = os.cpu_count() or 2
        self.workers = max(1, int(workers) if workers is not None else max(1, cpu - 1))
        self.target_trades_per_night = max(1000, int(target_trades_per_night))
        self.point_value = float(point_value)

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
                        cap = max(
                            MIN_SIMULATOR_BARS,
                            int(neuro_cfg.get("max_bars_in_report", cap) or cap),
                        )
                    reflection_report["simulator_data"] = list(real_ticks[-cap:])
                    reflection_report["neuro_simulator_data_source"] = "simulator_real_ticks"
                orchestrator.run_nightly_reflection(
                    nightly_report=reflection_report,
                    dry_run=str(getattr(self.runtime.engine.config, "trade_mode", "paper"))
                    .strip()
                    .lower()
                    in {"sim", "paper"},
                )
            except Exception:
                logger.exception("InfiniteSimulator failed during nightly reflection handoff")
        return report

    def run_nightly_simulation(self, *, num_trades_total: int = 1_000_000) -> dict[str, Any]:
        self.target_trades_per_night = max(1000, int(num_trades_total))
        return self.run_nightly()


__all__ = ["InfiniteSimulator"]
