"""Continuous runtime SLO evaluation for production headless mode."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.promotion_readiness import _reconciler_status_path
from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry
from lumina_core.runtime.production_config import (
    load_production_section,
    resolve_heartbeat_path,
    resolve_slo_live_path,
)

logger = logging.getLogger("lumina.runtime.slo")

_MONITORING_PATHS = (
    Path("state/monitoring_runtime_metrics.json"),
    Path("state/runtime_monitoring.json"),
)


@dataclass(slots=True)
class SloEvaluation:
    status: str  # pass | warn | fail
    breaches: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "breaches": list(self.breaches),
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


class RuntimeSloMonitor:
    """Evaluate live SLO thresholds from runtime state files and observability."""

    def __init__(
        self,
        *,
        mode: str,
        container: Any | None = None,
        prod_cfg: dict[str, Any] | None = None,
        started_at: float | None = None,
    ) -> None:
        self.mode = str(mode or "sim").strip().lower()
        self.container = container
        self.prod_cfg = prod_cfg if prod_cfg is not None else load_production_section()
        self._slo = self.prod_cfg.get("slo") if isinstance(self.prod_cfg.get("slo"), dict) else {}
        self._started_at = started_at if started_at is not None else time.time()

    def _parse_timestamp_age_s(self, payload: dict[str, Any]) -> float | None:
        ts = str(payload.get("timestamp") or payload.get("evaluated_at") or "")
        if not ts:
            return None
        try:
            evaluated = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - evaluated).total_seconds()
        except Exception:
            return None

    def _read_monitoring_snapshot(self) -> tuple[dict[str, Any] | None, float | None]:
        for path in _MONITORING_PATHS:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    age = self._parse_timestamp_age_s(payload)
                    return payload, age
            except Exception:
                logger.debug("runtime_slo.monitoring_read_failed path=%s", path, exc_info=True)
        return None, None

    def _supervisor_tick_age_s(self) -> float | None:
        _, age = self._read_monitoring_snapshot()
        return age

    def _heartbeat_age_s(self) -> float | None:
        path = resolve_heartbeat_path()
        if not path.exists():
            return None
        try:
            mtime = path.stat().st_mtime
            return time.time() - mtime
        except Exception:
            return None

    def _reconciler_pending(self) -> int | None:
        path = _reconciler_status_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return int(data.get("pending_count", 0) or 0)
        except Exception:
            return None

    def _reconciler_status_age_s(self) -> float | None:
        path = _reconciler_status_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                age = self._parse_timestamp_age_s(data)
                if age is not None:
                    return age
            mtime = path.stat().st_mtime
            return time.time() - mtime
        except Exception:
            return None

    def _websocket_heartbeat_age_s(self) -> float | None:
        obs = getattr(self.container, "observability_service", None) if self.container else None
        if obs is None:
            return None
        collector = getattr(obs, "collector", None)
        if collector is None:
            return None
        try:
            raw = collector.latest("lumina_websocket_last_heartbeat_age_s")
            return float(raw) if raw is not None else None
        except Exception:
            return None

    def _daily_pnl(self) -> float | None:
        engine = getattr(self.container, "engine", None) if self.container else None
        if engine is None:
            return None
        risk = getattr(engine, "risk_controller", None)
        if risk is None:
            return None
        state = getattr(risk, "state", None)
        if state is None:
            return None
        return float(getattr(state, "daily_pnl", 0.0) or 0.0)

    def _consecutive_losses(self) -> int | None:
        engine = getattr(self.container, "engine", None) if self.container else None
        if engine is None:
            return None
        risk = getattr(engine, "risk_controller", None)
        if risk is None:
            return None
        return int(getattr(risk, "consecutive_losses", 0) or 0)

    def _dead_daemon_count(self) -> int:
        return len(RuntimeDaemonRegistry.get().dead_daemons())

    def _within_startup_grace(self) -> bool:
        grace_s = float(self._slo.get("startup_grace_s", 180) or 180)
        return (time.time() - self._started_at) < grace_s

    def _status_for_issues(self, *, breaches: list[str], warnings: list[str]) -> str:
        if breaches:
            return "fail" if self.mode == "real" else "warn"
        if warnings:
            return "warn"
        return "pass"

    def evaluate(
        self,
        *,
        deferred_restart_age_s: float | None = None,
    ) -> SloEvaluation:
        breaches: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, Any] = {}
        in_grace = self._within_startup_grace()
        metrics["startup_grace_active"] = in_grace

        stale_s = float(self._slo.get("supervisor_tick_stale_s", 120) or 120)
        tick_age = self._supervisor_tick_age_s()
        metrics["supervisor_tick_age_s"] = tick_age
        if tick_age is not None and tick_age > stale_s:
            breaches.append(f"supervisor_tick_stale:{tick_age:.0f}s>{stale_s:.0f}s")
        elif tick_age is None and not in_grace:
            msg = "supervisor_tick_missing"
            if self.mode == "real":
                breaches.append(msg)
            else:
                warnings.append(msg)

        heartbeat_max = float(self._slo.get("heartbeat_stale_s", 45) or 45)
        hb_age = self._heartbeat_age_s()
        metrics["heartbeat_age_s"] = hb_age
        if hb_age is not None and hb_age > heartbeat_max:
            breaches.append(f"heartbeat_stale:{hb_age:.0f}s>{heartbeat_max:.0f}s")

        pending_max = int(self._slo.get("reconcile_pending_max", 0) or 0)
        pending = self._reconciler_pending()
        metrics["reconcile_pending"] = pending
        if pending is not None and pending > pending_max:
            breaches.append(f"reconcile_pending:{pending}>{pending_max}")

        recon_stale_s = float(self._slo.get("reconciler_status_stale_s", 120) or 120)
        recon_age = self._reconciler_status_age_s()
        metrics["reconciler_status_age_s"] = recon_age
        if recon_age is not None and recon_age > recon_stale_s:
            breaches.append(f"reconciler_status_stale:{recon_age:.0f}s>{recon_stale_s:.0f}s")
        elif recon_age is None and not in_grace and self.mode == "real":
            breaches.append("reconciler_status_missing")

        ws_max = float(self._slo.get("websocket_heartbeat_max_s", 60) or 60)
        ws_age = self._websocket_heartbeat_age_s()
        metrics["websocket_heartbeat_age_s"] = ws_age
        if ws_age is not None and ws_age > ws_max:
            breaches.append(f"websocket_heartbeat_stale:{ws_age:.0f}s>{ws_max:.0f}s")

        dead_count = self._dead_daemon_count()
        metrics["dead_daemon_count"] = dead_count
        dead_max = int(self._slo.get("daemon_dead_max", 0) or 0)
        if dead_count > dead_max:
            breaches.append(f"daemon_dead:{dead_count}>{dead_max}")

        metrics["deferred_restart_age_s"] = deferred_restart_age_s
        deferred_max = float(self._slo.get("deferred_restart_max_s", 3600) or 3600)
        if deferred_restart_age_s is not None and deferred_restart_age_s > deferred_max:
            breaches.append(
                f"deferred_restart:{deferred_restart_age_s:.0f}s>{deferred_max:.0f}s"
            )

        if self.mode == "real":
            daily_loss_threshold = float(self._slo.get("daily_loss_usd", -800) or -800)
            daily_pnl = self._daily_pnl()
            metrics["daily_pnl"] = daily_pnl
            if daily_pnl is not None and daily_pnl < daily_loss_threshold:
                breaches.append(f"daily_loss:{daily_pnl:.2f}<{daily_loss_threshold:.2f}")

            losses_max = int(self._slo.get("consecutive_losses_max", 5) or 5)
            consecutive = self._consecutive_losses()
            metrics["consecutive_losses"] = consecutive
            if consecutive is not None and consecutive > losses_max:
                breaches.append(f"consecutive_losses:{consecutive}>{losses_max}")

        status = self._status_for_issues(breaches=breaches, warnings=warnings)
        return SloEvaluation(
            status=status,
            breaches=tuple(breaches),
            warnings=tuple(warnings),
            metrics=metrics,
        )

    def persist(self, evaluation: SloEvaluation) -> Path:
        path = resolve_slo_live_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evaluation.to_dict(), indent=2), encoding="utf-8")
        return path

    def tick(self, *, deferred_restart_age_s: float | None = None) -> SloEvaluation:
        evaluation = self.evaluate(deferred_restart_age_s=deferred_restart_age_s)
        self.persist(evaluation)
        return evaluation
