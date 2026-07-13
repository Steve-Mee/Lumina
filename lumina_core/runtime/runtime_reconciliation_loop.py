"""Active reconciliation health loop for production headless runtime."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.promotion_readiness import _check_reconciler, _reconciler_status_path
from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry
from lumina_core.runtime.production_config import load_production_section, resolve_reconciliation_report_path
from lumina_core.runtime.safe_restart_policy import SafeRestartPolicy

logger = logging.getLogger("lumina.runtime.reconciliation")

_CRITICAL_DAEMONS = ("supervisor-loop", "trade-reconciler")


@dataclass(slots=True)
class ReconciliationResult:
    ok: bool
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


class RuntimeReconciliationLoop:
    """Periodic reconciler health, daemon liveness, and read-only position drift checks."""

    def __init__(
        self,
        *,
        mode: str,
        container: Any,
        restart_policy: SafeRestartPolicy,
        prod_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.mode = str(mode or "sim").strip().lower()
        self.container = container
        self.restart_policy = restart_policy
        self.prod_cfg = prod_cfg if prod_cfg is not None else load_production_section()
        slo = self.prod_cfg.get("slo") if isinstance(self.prod_cfg.get("slo"), dict) else {}
        self._reconciler_stale_s = float(slo.get("reconciler_status_stale_s", 120) or 120)

    def _reconciler_status_age_s(self) -> float | None:
        path = _reconciler_status_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                ts = str(data.get("timestamp") or data.get("evaluated_at") or data.get("updated_at") or "")
                if ts:
                    evaluated = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    return (datetime.now(timezone.utc) - evaluated).total_seconds()
            return time.time() - path.stat().st_mtime
        except Exception:
            return None

    def _check_reconciler_health(self) -> tuple[list[str], list[str], dict[str, Any]]:
        issues: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, Any] = {}

        path = _reconciler_status_path()
        metrics["reconciler_status_exists"] = path.exists()
        age = self._reconciler_status_age_s()
        metrics["reconciler_status_age_s"] = age

        if not path.exists():
            if self.mode == "real":
                issues.append("reconciler_status_missing")
            else:
                warnings.append("reconciler_status_missing")
        elif age is not None and age > self._reconciler_stale_s:
            issues.append(f"reconciler_status_stale:{age:.0f}s>{self._reconciler_stale_s:.0f}s")

        ok, reason = _check_reconciler(status_path=path)
        metrics["reconciler_check_ok"] = ok
        if not ok and reason:
            issues.append(reason)

        return issues, warnings, metrics

    def _check_daemon_liveness(self) -> tuple[list[str], list[str], dict[str, Any]]:
        issues: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, Any] = {}

        registry = RuntimeDaemonRegistry.get()
        dead = registry.dead_daemons()
        metrics["dead_daemons"] = list(dead)
        metrics["daemon_snapshot"] = registry.snapshot()

        for name in _CRITICAL_DAEMONS:
            if name in dead:
                issues.append(f"critical_daemon_dead:{name}")

        return issues, warnings, metrics

    def _check_position_drift(self) -> tuple[list[str], list[str], dict[str, Any]]:
        """Read-only broker vs engine position comparison (REAL only)."""
        issues: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, Any] = {}

        if self.mode != "real":
            return issues, warnings, metrics

        engine = getattr(self.container, "engine", None)
        broker = getattr(self.container, "broker", None)
        if engine is None or broker is None:
            return issues, warnings, metrics

        engine_qty = int(getattr(engine, "live_position_qty", 0) or 0)
        metrics["engine_live_qty"] = engine_qty

        get_positions = getattr(broker, "get_positions", None)
        if not callable(get_positions):
            warnings.append("broker_positions_unavailable")
            return issues, warnings, metrics

        try:
            positions = get_positions()
        except Exception as exc:
            warnings.append(f"broker_positions_error:{type(exc).__name__}")
            return issues, warnings, metrics

        instrument = str(getattr(getattr(engine, "config", None), "instrument", "") or "").strip()
        broker_qty = 0
        for pos in positions or []:
            symbol = str(getattr(pos, "symbol", getattr(pos, "instrument", "")) or "").strip()
            if instrument and symbol and symbol != instrument:
                continue
            broker_qty = int(getattr(pos, "quantity", getattr(pos, "qty", 0)) or 0)
            break

        metrics["broker_qty"] = broker_qty
        if broker_qty != engine_qty:
            drift_msg = f"position_drift:engine={engine_qty},broker={broker_qty}"
            issues.append(drift_msg)

        return issues, warnings, metrics

    def evaluate(self) -> ReconciliationResult:
        issues: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, Any] = {}

        for chunk_issues, chunk_warnings, chunk_metrics in (
            self._check_reconciler_health(),
            self._check_daemon_liveness(),
            self._check_position_drift(),
        ):
            issues.extend(chunk_issues)
            warnings.extend(chunk_warnings)
            metrics.update(chunk_metrics)

        return ReconciliationResult(
            ok=not issues,
            issues=tuple(issues),
            warnings=tuple(warnings),
            metrics=metrics,
        )

    def persist(self, result: ReconciliationResult) -> Path:
        path = resolve_reconciliation_report_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        return path

    def tick(self) -> ReconciliationResult:
        result = self.evaluate()
        self.persist(result)
        self.restart_policy.write_deferred_status(self.container)
        return result
