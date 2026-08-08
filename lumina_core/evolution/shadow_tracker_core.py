"""ShadowDeploymentTracker core state/lifecycle methods."""
from __future__ import annotations

import json
import math
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.logging_utils import correlation_id, get_logger, log_shadow_verdict
from lumina_core.evolution.shadow_helpers import *  # noqa: F403

logger = get_logger("lumina.evolution.shadow")

class ShadowDeploymentTrackerCore:
    """Tracks shadow runs for DNA candidates and computes promotion verdicts.

    State is persisted as a JSON file so it survives restarts.
    Thread-safe for concurrent reads.
    """

    def __init__(
        self,
        *,
        state_path: Path | None = None,
        min_days: float | None = None,
        min_trades: int | None = None,
        pvalue_threshold: float = 0.1,
        effect_size_threshold: float = 0.2,
    ) -> None:
        self._path = state_path or _DEFAULT_SHADOW_PATH
        self._lock = threading.Lock()

        evo_cfg = ConfigLoader.section("evolution", default={}) or {}
        shadow_cfg = evo_cfg.get("shadow_validation", {}) if isinstance(evo_cfg, dict) else {}
        if not isinstance(shadow_cfg, dict):
            shadow_cfg = {}

        self._min_days = float(min_days if min_days is not None else shadow_cfg.get("min_days", 3))
        self._min_trades = int(min_trades if min_trades is not None else shadow_cfg.get("min_trades", 20))
        self._pvalue_threshold = float(pvalue_threshold)
        self._effect_size_threshold = float(effect_size_threshold)
    def _load(self) -> dict[str, ShadowRun]:
        try:
            if not self._path.exists():
                return {}
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return {}
            return {k: ShadowRun.from_dict(v) for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("ShadowDeploymentTracker: failed to load state: %s", exc)
            return {}
    def _save(self, runs: dict[str, ShadowRun]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({k: v.to_dict() for k, v in runs.items()}, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("ShadowDeploymentTracker: failed to save state: %s", exc)
    def start_shadow(self, dna_hash: str) -> ShadowRun:
        """Register a new shadow run for *dna_hash*.

        Idempotent — if the hash is already tracked and still running,
        the existing run is returned.
        """
        with correlation_id(str(dna_hash)):
            with self._lock:
                runs = self._load()
                existing = runs.get(dna_hash)
                if existing and existing.status == "running":
                    try:
                        logger.info(
                            "shadow.start_shadow.active",
                            extra={"event_data": {"event": "shadow.start_shadow.active", "dna_hash": dna_hash[:12]}},
                        )
                    except Exception:
                        pass
                    return existing

                run = ShadowRun(dna_hash=dna_hash)
                runs[dna_hash] = run
                self._save(runs)
                try:
                    logger.info(
                        "shadow.start_shadow",
                        extra={
                            "event_data": {
                                "event": "shadow.start_shadow",
                                "dna_hash": dna_hash[:12],
                                "shadow_run_id": dna_hash[:12],
                                "min_days": self._min_days,
                                "min_trades": self._min_trades,
                            }
                        },
                    )
                except Exception:
                    pass
                return run
    def record_pnl(
        self,
        dna_hash: str,
        *,
        sim_pnl: float | None = None,
        paper_pnl: float | None = None,
    ) -> None:
        """Append a PnL observation to the shadow run."""
        with correlation_id(str(dna_hash)):
            with self._lock:
                runs = self._load()
                run = runs.get(dna_hash)
                if run is None or run.status != "running":
                    return
                if sim_pnl is not None:
                    run.sim_pnl_history.append(float(sim_pnl))
                    run.total_sim_pnl += float(sim_pnl)
                if paper_pnl is not None:
                    run.paper_pnl_history.append(float(paper_pnl))
                    run.total_paper_pnl += float(paper_pnl)
                run.trade_count += 1
                self._save(runs)
                if run.trade_count % 5 == 0:
                    try:
                        logger.info(
                            "shadow.record_pnl",
                            extra={
                                "event_data": {
                                    "event": "shadow.record_pnl",
                                    "dna_hash": dna_hash[:12],
                                    "shadow_run_id": dna_hash[:12],
                                    "trade_count": run.trade_count,
                                    "sim_pnl": run.total_sim_pnl,
                                    "paper_pnl": run.total_paper_pnl,
                                }
                            },
                        )
                    except Exception:
                        pass
    def is_shadow_complete(self, dna_hash: str) -> bool:
        """True when the minimum duration and trade count have been reached."""
        with self._lock:
            runs = self._load()
            run = runs.get(dna_hash)
        if run is None:
            return False
        is_complete = run.days_elapsed >= self._min_days and run.trade_count >= self._min_trades
        try:
            logger.info(
                "shadow.is_complete",
                extra={
                    "event_data": {
                        "event": "shadow.is_complete",
                        "dna_hash": dna_hash[:12],
                        "shadow_run_id": dna_hash[:12],
                        "days_elapsed": run.days_elapsed,
                        "trade_count": run.trade_count,
                        "is_complete": is_complete,
                    }
                },
            )
        except Exception:
            pass
        return is_complete
    def mark_promoted(self, dna_hash: str) -> None:
        """Mark the shadow run as promoted."""
        with self._lock:
            runs = self._load()
            if dna_hash in runs:
                runs[dna_hash].status = "promoted"
                runs[dna_hash].end_ts = _utcnow()
                self._save(runs)
                try:
                    logger.info(
                        "shadow.mark_promoted",
                        extra={
                            "event_data": {
                                "event": "shadow.mark_promoted",
                                "dna_hash": dna_hash[:12],
                                "shadow_run_id": dna_hash[:12],
                                "total_sim_pnl": runs[dna_hash].total_sim_pnl,
                                "total_paper_pnl": runs[dna_hash].total_paper_pnl,
                                "trade_count": runs[dna_hash].trade_count,
                            }
                        },
                    )
                except Exception:
                    pass
    def get_all_runs(self) -> dict[str, ShadowRun]:
        with self._lock:
            return self._load()
