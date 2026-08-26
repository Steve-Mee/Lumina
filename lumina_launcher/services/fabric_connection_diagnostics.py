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


def _resolve_diag_instrument(explicit: str | None = None) -> str:
    """Prefer full contract names. Bare MES/MNQ roots are expanded by NT provider too.

    Priority: multi-token explicit → config trading.instrument → explicit root → MES SEP26.
    """
    raw = str(explicit or "").strip()
    if raw and len(raw.split()) >= 2:
        return raw

    instrument = ""
    try:
        import yaml

        candidates = [
            Path.cwd() / "config.yaml",
            Path(__file__).resolve().parents[2] / "config.yaml",
        ]
        for cfg_path in candidates:
            if not cfg_path.is_file():
                continue
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                continue
            trading = data.get("trading") if isinstance(data.get("trading"), dict) else {}
            instrument = str(trading.get("instrument") or "").strip()
            if instrument:
                break
            broker = data.get("broker") if isinstance(data.get("broker"), dict) else {}
            nt = broker.get("ninjatrader") if isinstance(broker.get("ninjatrader"), dict) else {}
            instruments = nt.get("instruments") or []
            if isinstance(instruments, list) and instruments:
                instrument = str(instruments[0] or "").strip()
            if instrument:
                break
    except Exception:
        instrument = ""

    if instrument:
        return instrument
    return raw or "MES SEP26"


def run_fabric_connection_diagnostics(
    *,
    include_safe_mode: bool = True,
    instrument: str = "",
) -> FabricConnectionReport:
    """Run ordered SIM-only Fabric diagnostics. Never touches CrossTrade."""
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()
    instrument = _resolve_diag_instrument(instrument)

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
