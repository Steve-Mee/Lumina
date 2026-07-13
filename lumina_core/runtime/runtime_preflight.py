"""Runtime startup preflight — fail-closed before production headless bootstrap."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.promotion_readiness import _check_reconciler, _reconciler_status_path
from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry
from lumina_core.runtime.production_config import load_production_section, resolve_preflight_report_path

logger = logging.getLogger("lumina.runtime.preflight")


@dataclass(slots=True)
class RuntimePreflightReport:
    ok: bool
    mode: str
    checks: dict[str, str] = field(default_factory=dict)
    failure_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "checks": dict(self.checks),
            "failure_reasons": list(self.failure_reasons),
            "warnings": list(self.warnings),
            "message": self.message,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


def _norm_mode(mode: str) -> str:
    aliases = {
        "paper": "paper",
        "sim": "sim",
        "simulation": "sim",
        "sim_real_guard": "sim_real_guard",
        "real": "real",
        "live": "real",
        "nightly": "sim",
    }
    return aliases.get(str(mode or "").strip().lower(), "sim")


def _is_realish(mode: str) -> bool:
    return _norm_mode(mode) in {"real", "paper", "sim_real_guard"}


def _check_birth_certificate(*, required: bool) -> tuple[bool, str | None]:
    if not required:
        return True, None
    try:
        from lumina_core.runtime_bootstrap import _assert_birth_phase_completed

        _assert_birth_phase_completed()
        return True, None
    except Exception as exc:
        return False, f"birth_certificate:{exc}"


def _check_config_startup() -> tuple[bool, str | None]:
    try:
        ok = ConfigLoader.validate_startup(raise_on_error=True)
        return bool(ok), None
    except Exception as exc:
        return False, f"config_startup:{exc}"


def _check_broker_connect(container: Any | None, *, required: bool, mode: str) -> tuple[bool, str | None]:
    if not required or container is None:
        return True, None
    broker = getattr(container, "broker", None)
    if broker is None:
        return False, "broker_missing"

    config = getattr(container, "config", None)
    live_provider = str(getattr(config, "broker_live_provider", "crosstrade") or "crosstrade").strip().lower()
    if live_provider == "ninjatrader":
        try:
            from lumina_core.broker.ninjatrader.bridge_service import get_ninjatrader_bridge_service

            state = get_ninjatrader_bridge_service().get_connection_state()
            if state.is_connected:
                return True, None
            if _norm_mode(mode) in {"real", "sim_real_guard"}:
                return False, "ninjatrader_not_connected"
            return True, None
        except Exception as exc:
            if _norm_mode(mode) in {"real", "sim_real_guard"}:
                return False, f"ninjatrader_connect_error:{type(exc).__name__}"
            return True, None

    try:
        connected = bool(broker.connect())
        if not connected:
            return False, "broker_connect_failed"
        return True, None
    except Exception as exc:
        return False, f"broker_connect_error:{type(exc).__name__}"


def _check_reconciler_healthy(*, required: bool) -> tuple[bool, str | None]:
    if not required:
        return True, None
    ok, reason = _check_reconciler(status_path=_reconciler_status_path())
    if ok:
        return True, None
    return False, reason or "reconciler_unhealthy"


def _check_session_guard(mode: str) -> tuple[bool, str | None, str | None]:
    """Return (ok, failure_reason, warning)."""
    if _norm_mode(mode) != "real":
        return True, None, None
    allow_outside = os.getenv("LUMINA_REAL_OUTSIDE_SESSION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if allow_outside:
        return True, None, "real_outside_session_override"
    try:
        from lumina_core.risk.session_guard import SessionGuard

        guard = SessionGuard()
        if guard.is_trading_session():
            return True, None, None
        return False, "session_guard:outside_trading_session", None
    except Exception as exc:
        return False, f"session_guard_error:{type(exc).__name__}", None


def _check_slo_report_freshness(mode: str) -> tuple[bool, str | None]:
    if _norm_mode(mode) == "sim":
        return True, None
    path = Path("state/slo_report.json")
    if not path.exists():
        return True, "slo_report_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        ts = str(payload.get("timestamp_utc", "") or "")
        if not ts:
            return True, "slo_report_no_timestamp"
        evaluated = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - evaluated).total_seconds() / 3600.0
        if age_h > 24.0:
            return True, f"slo_report_stale_hours:{age_h:.1f}"
    except Exception:
        return True, "slo_report_unreadable"
    return True, None


def _check_ohlc_post_bootstrap(container: Any | None, mode: str) -> tuple[bool, str | None, str | None]:
    """Post-bootstrap OHLC quality. REAL fails on empty primary OHLC."""
    if container is None:
        return True, None, None
    engine = getattr(container, "engine", None)
    df = getattr(engine, "ohlc_1min", None) if engine is not None else None
    rows = len(df) if df is not None else 0
    if rows == 0:
        if _norm_mode(mode) == "real":
            return False, "ohlc_primary_empty", None
        return True, None, "ohlc_primary_empty_warn"
    if rows < 120:
        return True, None, f"ohlc_rows_low:{rows}"
    return True, None, None


_CRITICAL_DAEMONS = ("supervisor-loop", "trade-reconciler")


def _check_critical_daemons_registered(mode: str) -> tuple[bool, str | None, str | None]:
    """Return (ok, failure_reason, warning)."""
    registry = RuntimeDaemonRegistry.get()
    snapshot = registry.snapshot()
    missing = [name for name in _CRITICAL_DAEMONS if name not in snapshot]
    if not missing:
        return True, None, None
    msg = f"critical_daemons_missing:{','.join(missing)}"
    if _norm_mode(mode) == "real":
        return False, msg, None
    return True, None, msg


def _check_reconciler_status_file(mode: str) -> tuple[bool, str | None, str | None]:
    path = _reconciler_status_path()
    if path.exists():
        return True, None, None
    msg = "reconciler_status_file_missing"
    if _norm_mode(mode) == "real":
        return False, msg, None
    return True, None, msg


def _check_observability_started(container: Any | None, mode: str) -> tuple[bool, str | None, str | None]:
    if container is None:
        return True, None, None
    obs = getattr(container, "observability_service", None)
    if obs is None:
        msg = "observability_service_missing"
        if _norm_mode(mode) == "real":
            return True, None, msg
        return True, None, None
    started = bool(getattr(obs, "_started", False) or getattr(obs, "started", False))
    if started:
        return True, None, None
    return True, None, "observability_not_started"


def _check_monitoring_webhook(mode: str) -> tuple[bool, str | None, str | None]:
    if _norm_mode(mode) != "real":
        return True, None, None
    try:
        monitoring = ConfigLoader.section("monitoring", default={}) or {}
        if not isinstance(monitoring, dict):
            return True, None, None
        if not bool(monitoring.get("enabled", False)):
            return True, None, "monitoring_disabled"
        webhook = monitoring.get("webhook")
        if isinstance(webhook, dict) and str(webhook.get("url", "") or "").strip():
            return True, None, None
        return True, None, "monitoring_webhook_not_configured"
    except Exception:
        return True, None, "monitoring_config_unreadable"


def run_preflight_early(
    *,
    mode: str,
    container: Any | None = None,
    prod_cfg: dict[str, Any] | None = None,
) -> RuntimePreflightReport:
    """Checks that can run before bootstrap (or with a started container for broker probe)."""
    normalized = _norm_mode(mode)
    cfg = prod_cfg if prod_cfg is not None else load_production_section()
    preflight_cfg = cfg.get("preflight") if isinstance(cfg.get("preflight"), dict) else {}

    require_birth = bool(preflight_cfg.get("require_birth_certificate", True))
    require_broker = bool(preflight_cfg.get("require_broker_connect", True))
    require_reconciler = bool(preflight_cfg.get("require_reconciler_healthy", True))

    if normalized == "sim":
        require_broker = bool(preflight_cfg.get("require_broker_connect_sim", False))
        require_reconciler = bool(preflight_cfg.get("require_reconciler_healthy_sim", False))

    checks: dict[str, str] = {}
    failures: list[str] = []
    warnings: list[str] = []

    ok, reason = _check_birth_certificate(required=require_birth)
    checks["birth_certificate"] = "pass" if ok else "fail"
    if not ok and reason:
        failures.append(reason)

    ok, reason = _check_config_startup()
    checks["config_startup"] = "pass" if ok else "fail"
    if not ok and reason:
        failures.append(reason)

    if _is_realish(normalized) and require_reconciler:
        ok, reason = _check_reconciler_healthy(required=True)
        checks["reconciler"] = "pass" if ok else "fail"
        if not ok and reason:
            failures.append(reason)

    ok, fail_reason, warn = _check_session_guard(normalized)
    checks["session_guard"] = "pass" if ok else "fail"
    if not ok and fail_reason:
        failures.append(fail_reason)
    if warn:
        warnings.append(warn)

    _, slo_warn = _check_slo_report_freshness(normalized)
    checks["slo_report"] = "warn" if slo_warn else "pass"
    if slo_warn:
        warnings.append(slo_warn)

    if require_broker and container is not None:
        ok, reason = _check_broker_connect(container, required=True, mode=normalized)
        checks["broker_connect"] = "pass" if ok else "fail"
        if not ok and reason:
            failures.append(reason)

    ok = not failures
    message = "Runtime preflight OK" if ok else "Runtime preflight failed — fail-closed"
    return RuntimePreflightReport(
        ok=ok,
        mode=normalized,
        checks=checks,
        failure_reasons=tuple(failures),
        warnings=tuple(warnings),
        message=message,
    )


def run_preflight_post_bootstrap(
    *,
    mode: str,
    container: Any,
) -> RuntimePreflightReport:
    """OHLC and broker checks after historical data is loaded."""
    normalized = _norm_mode(mode)
    checks: dict[str, str] = {}
    failures: list[str] = []
    warnings: list[str] = []

    ok, fail_reason, warn = _check_ohlc_post_bootstrap(container, normalized)
    checks["ohlc_quality"] = "pass" if ok else "fail"
    if not ok and fail_reason:
        failures.append(fail_reason)
    if warn:
        warnings.append(warn)

    cfg = load_production_section()
    preflight_cfg = cfg.get("preflight") if isinstance(cfg.get("preflight"), dict) else {}
    require_broker = bool(preflight_cfg.get("require_broker_connect", True))
    if normalized == "sim":
        require_broker = bool(preflight_cfg.get("require_broker_connect_sim", False))

    if require_broker:
        ok, reason = _check_broker_connect(container, required=True, mode=normalized)
        checks["broker_connect_post"] = "pass" if ok else "fail"
        if not ok and reason:
            failures.append(reason)

    ok, fail_reason, warn = _check_critical_daemons_registered(normalized)
    checks["critical_daemons"] = "pass" if ok else "fail"
    if not ok and fail_reason:
        failures.append(fail_reason)
    if warn:
        warnings.append(warn)

    ok, fail_reason, warn = _check_reconciler_status_file(normalized)
    checks["reconciler_status_file"] = "pass" if ok else "fail"
    if not ok and fail_reason:
        failures.append(fail_reason)
    if warn:
        warnings.append(warn)

    ok, fail_reason, warn = _check_observability_started(container, normalized)
    checks["observability"] = "pass" if ok else "fail"
    if not ok and fail_reason:
        failures.append(fail_reason)
    if warn:
        warnings.append(warn)

    ok, fail_reason, warn = _check_monitoring_webhook(normalized)
    checks["monitoring_webhook"] = "pass" if ok else "warn"
    if warn:
        warnings.append(warn)

    ok = not failures
    return RuntimePreflightReport(
        ok=ok,
        mode=normalized,
        checks=checks,
        failure_reasons=tuple(failures),
        warnings=tuple(warnings),
        message="Post-bootstrap preflight OK" if ok else "Post-bootstrap preflight failed",
    )


def persist_preflight_report(report: RuntimePreflightReport) -> Path:
    path = resolve_preflight_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return path


def merge_preflight_reports(*reports: RuntimePreflightReport) -> RuntimePreflightReport:
    if not reports:
        return RuntimePreflightReport(ok=True, mode="sim")
    mode = reports[0].mode
    checks: dict[str, str] = {}
    failures: list[str] = []
    warnings: list[str] = []
    for report in reports:
        checks.update(report.checks)
        failures.extend(report.failure_reasons)
        warnings.extend(report.warnings)
    ok = not failures
    return RuntimePreflightReport(
        ok=ok,
        mode=mode,
        checks=checks,
        failure_reasons=tuple(failures),
        warnings=tuple(warnings),
        message="Runtime preflight OK" if ok else "Runtime preflight failed — fail-closed",
    )
