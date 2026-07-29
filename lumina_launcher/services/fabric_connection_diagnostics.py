"""Post-install NinjaTrader Execution Fabric connection diagnostics (SIM only).

Tests Brain ↔ Fabric gRPC directly — never CrossTrade.

Preflight: ``fabric_diag_preflight``. Live gRPC: ``fabric_diag_live``.
This module keeps the public ``run_fabric_connection_diagnostics`` façade and
re-exports helpers so tests can monkeypatch module attributes.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_launcher.services.fabric_diag_live import run_live_checks
from lumina_launcher.services.fabric_diag_preflight import (  # noqa: F401
    CRITICAL_CHECK_IDS,
    CheckStatus,
    DiagnosticCheck,
    FabricConnectionReport,
    OverallStatus,
    PreflightContext,
    _audit_path,
    _is_localhost,
    _load_broker_config,
    _resolve_token,
    _tcp_check,
    finalize_report,
    run_preflight,
)
from lumina_launcher.services.fabric_diag_preflight import (
    _fabric_json_path as _default_fabric_json_path,
)

# Alias preserved for callers/tests that patched ``_finalize``.
_finalize = finalize_report


def _fabric_json_path() -> Path:
    """Module-local so monkeypatch + ``_load_fabric_json`` share one namespace."""
    return _default_fabric_json_path()


def _load_fabric_json() -> dict[str, Any]:
    """Uses this module's ``_fabric_json_path`` (monkeypatch-friendly)."""
    path = _fabric_json_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def run_fabric_connection_diagnostics(
    *,
    include_safe_mode: bool = True,
    instrument: str = "MES",
) -> FabricConnectionReport:
    """Run ordered SIM-only Fabric diagnostics. Never touches CrossTrade."""
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()

    # Resolve helpers via this module so monkeypatch.setattr(diag, "_tcp_check", ...) works.
    ctx = run_preflight(
        started=started,
        t0=t0,
        load_fabric_json=_load_fabric_json,
        load_broker_config=_load_broker_config,
        fabric_json_path=_fabric_json_path,
        resolve_token=_resolve_token,
        tcp_check=_tcp_check,
        is_localhost=_is_localhost,
    )
    if ctx.early_report is not None:
        return ctx.early_report

    run_live_checks(
        host=ctx.host,
        port=ctx.port,
        token=ctx.token,
        instrument=instrument,
        include_safe_mode=include_safe_mode,
        checks=ctx.checks,
        remediation=ctx.remediation,
        audit_path=_audit_path,
    )
    return _finalize(
        ctx.checks,
        started,
        t0,
        ctx.target,
        ctx.gateway_mode,
        ctx.remediation,
    )
