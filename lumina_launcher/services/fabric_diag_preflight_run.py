"""Fabric preflight run (M5)."""
from __future__ import annotations

import json
import os

import logging
import time
from dataclasses import dataclass, field
from typing import Any


def _p():
    from lumina_launcher.services import fabric_diag_preflight as p
    return p

logger = logging.getLogger(__name__)

def finalize_report(
    checks: list[Any],
    started: str,
    t0: float,
    target: str,
    gateway_mode: str,
    remediation: list[str],
) -> Any:
    critical_fail = any(
        c.status == "fail" and c.id in _p().CRITICAL_CHECK_IDS for c in checks
    )
    any_fail = any(c.status == "fail" for c in checks)
    any_warn = any(c.status == "warn" for c in checks)
    if critical_fail or any_fail:
        overall: Any = "red"
    elif any_warn:
        overall = "amber"
    else:
        overall = "green"

    passed = sum(1 for c in checks if c.status == "pass")
    failed = sum(1 for c in checks if c.status == "fail")
    summary = f"{passed} passed, {failed} failed, overall={overall}"

    # Dedupe remediation
    seen: set[str] = set()
    rem: list[str] = []
    for item in remediation:
        if item not in seen:
            seen.add(item)
            rem.append(item)

    return _p().FabricConnectionReport(
        overall=overall,
        started_at=started,
        duration_ms=int((time.perf_counter() - t0) * 1000),
        target=target,
        gateway_mode=gateway_mode,
        checks=checks,
        summary=summary,
        remediation=rem,
    )

@dataclass
class PreflightContext:
    """Carries preflight outcomes into live gRPC checks (keyword-constructible)."""

    host: str
    port: int
    gateway_mode: str
    target: str
    token: str
    checks: list[Any] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)
    early_report: Any | None = None

def run_preflight(
    *,
    started: str,
    t0: float,
    load_fabric_json: Any,
    load_broker_config: Any,
    fabric_json_path: Any,
    resolve_token: Any,
    tcp_check: Any,
    is_localhost: Any,
) -> PreflightContext:
    """Ordered SIM-only preflight. Callers inject helpers so façade monkeypatches work."""
    checks: list[Any] = []
    remediation: list[str] = []

    fabric_cfg = load_fabric_json()
    broker = load_broker_config()
    nt = broker.get("ninjatrader") if isinstance(broker.get("ninjatrader"), dict) else {}
    fabric_yaml = nt.get("fabric") if isinstance(nt.get("fabric"), dict) else {}

    host = str(
        fabric_yaml.get("host")
        or fabric_cfg.get("BindHost")
        or os.getenv("LUMINA_FABRIC_HOST")
        or "127.0.0.1"
    ).strip()
    port = int(
        fabric_yaml.get("port")
        or fabric_cfg.get("BindPort")
        or os.getenv("LUMINA_FABRIC_PORT")
        or 50051
    )
    gateway_mode = str(
        fabric_cfg.get("GatewayMode")
        or fabric_yaml.get("gateway_mode")
        or "nt"
    ).strip().lower()
    target = f"{host}:{port}"

    # 1 token (SSOT: fabric.json AuthToken heals stale process env)
    t = time.perf_counter()
    token = resolve_token()
    token_meta: dict[str, Any] = {}
    try:
        from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

        sec = fabric_secret_read(heal=True)
        token_meta = sec.as_dict()
        if sec.token:
            token = str(sec.token)
    except Exception:
        token_meta = {}
    if token:
        src = str(token_meta.get("source") or "env")
        mismatch = bool(token_meta.get("mismatch"))
        msg = f"Token ready (source={src}, len={len(token)})"
        if mismatch:
            msg += " — healed process env to match fabric.json (was divergent)"
        checks.append(
            _p().DiagnosticCheck(
                id="token_present",
                title="Fabric auth token",
                status="pass",
                message=msg,
                detail=json.dumps(token_meta, default=str)[:400] if token_meta else None,
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
    else:
        checks.append(
            _p().DiagnosticCheck(
                id="token_present",
                title="Fabric auth token",
                status="fail",
                message="Missing LUMINA_FABRIC_TOKEN",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        remediation.append(
            "Generate LUMINA_FABRIC_TOKEN on the Credentials step (or run scripts/install_fabric_token.ps1), "
            "then restart NinjaTrader if using the AddOn."
        )

    # 2 fabric.json
    t = time.perf_counter()
    fj_path = fabric_json_path()
    if fabric_cfg:
        gw = str(fabric_cfg.get("GatewayMode", "nt")).lower()
        status: Any = "pass"
        msg = f"Found {fj_path} (GatewayMode={gw})"
        known = {
            "nt",
            "ninjatrader",
            "account",
            "sim101",
            "memory",
            "simhost",
            "mock",
            "sim",  # legacy in-memory; NT AddOn upgrades to Account bind
        }
        if gw not in known:
            status = "warn"
            msg += " — unexpected GatewayMode"
        elif gw in {"nt", "ninjatrader", "account", "sim101"}:
            status = "pass"
            msg += " — NT Account gateway (Sim101 bind; real SIM path)"
        elif gw in {"memory", "simhost", "mock"}:
            status = "pass"
            msg += " — in-memory gateway (execution-only; historical_bars needs NT AddOn)"
        elif gw == "sim":
            status = "warn"
            msg += " — legacy label; product path is GatewayMode=nt (Sim101 Account). Re-run token install / bootstrap to migrate."
        checks.append(
            _p().DiagnosticCheck(
                id="fabric_json",
                title="fabric.json host config",
                status=status,
                message=msg,
                detail=json.dumps(
                    {k: fabric_cfg.get(k) for k in ("BindHost", "BindPort", "AuthTokenEnv", "AccountName", "GatewayMode")},
                    default=str,
                ),
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
    else:
        checks.append(
            _p().DiagnosticCheck(
                id="fabric_json",
                title="fabric.json host config",
                status="warn",
                message=f"No fabric.json at {fj_path} — host defaults will apply",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        remediation.append("Save credentials once or run install_fabric_token.ps1 to create fabric.json.")

    # 3 config alignment
    t = time.perf_counter()
    live_provider = str(broker.get("live_provider") or "ninjatrader").lower()
    nt_enabled = bool(nt.get("enabled", False))
    if live_provider == "ninjatrader" and nt_enabled:
        checks.append(
            _p().DiagnosticCheck(
                id="config_alignment",
                title="Brain config (live_provider)",
                status="pass",
                message="broker.live_provider=ninjatrader and ninjatrader.enabled=true",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
    elif live_provider == "ninjatrader" and not nt_enabled:
        checks.append(
            _p().DiagnosticCheck(
                id="config_alignment",
                title="Brain config (live_provider)",
                status="fail",
                message="live_provider=ninjatrader requires ninjatrader.enabled=true",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        remediation.append("Set broker.ninjatrader.enabled: true in config.yaml.")
    else:
        checks.append(
            _p().DiagnosticCheck(
                id="config_alignment",
                title="Brain config (live_provider)",
                status="warn",
                message=f"live_provider={live_provider} (Fabric path uses ninjatrader)",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        remediation.append("Set broker.live_provider: ninjatrader and ninjatrader.enabled: true for native Fabric.")

    # Localhost only for live gRPC tests
    if not is_localhost(host):
        checks.append(
            _p().DiagnosticCheck(
                id="port_listen",
                title="Fabric port reachable",
                status="fail",
                message=f"Host {host} rejected — diagnostics only allow localhost (fail-closed)",
            )
        )
        remediation.append("Bind Fabric to 127.0.0.1 only (BindLocalhostOnly=true).")
        return PreflightContext(
            host=host,
            port=port,
            gateway_mode=gateway_mode,
            target=target,
            token=token,
            checks=checks,
            remediation=remediation,
            early_report=finalize_report(checks, started, t0, target, gateway_mode, remediation),
        )

    # 4 TCP + token-aligned SimHost (start or restart if stale token)
    t = time.perf_counter()
    ok_tcp, tcp_msg = tcp_check(host, port)
    simhost_detail: str | None = None
    # Memory/CI gateway only: auto-start SimHost when nothing listens.
    # Never auto-start SimHost for GatewayMode=nt — that steals :50051 from the NT AddOn
    # (historical_bars → HOST_NO_NT_DATA). Product path expects NinjaTrader + Repair.
    if bool(token) and is_localhost(host) and gateway_mode in {
        "memory",
        "simhost",
        "mock",
        "sim",  # legacy name still maps to memory gateway outside NT
    }:
        try:
            from lumina_launcher.services.fabric_simhost import ensure_simhost_token_aligned

            account = str(
                fabric_cfg.get("AccountName")
                or fabric_yaml.get("account")
                or "Sim101"
            )
            ensure = ensure_simhost_token_aligned(
                host=host,
                port=port,
                token=token,
                account=account,
                wait_sec=8.0,
            )
            simhost_detail = (
                f"auto_simhost status={ensure.get('status')} "
                f"auth={ensure.get('authenticated')} "
                f"msg={ensure.get('message')} pid={ensure.get('pid')}"
            )
            logger.info("fabric.diag.auto_simhost %s", simhost_detail)
            if ensure.get("listening"):
                ok_tcp, tcp_msg = True, str(ensure.get("message") or "SimHost listening")
            elif not ok_tcp:
                tcp_msg = f"{tcp_msg}; {ensure.get('message')}"
        except Exception as exc:
            logger.warning("fabric.diag.auto_simhost_failed: %s", exc)
            simhost_detail = f"auto_simhost exception: {exc}"

    if ok_tcp:
        checks.append(
            _p().DiagnosticCheck(
                id="port_listen",
                title="Fabric port reachable",
                status="pass",
                message=f"{target} accepts TCP",
                detail=simhost_detail or tcp_msg,
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
    else:
        # Product path (GatewayMode=nt): NT AddOn owns :50051 — never suggest SimHost thrash.
        nt_mode = str(gateway_mode or "").strip().lower() in {
            "nt",
            "ninjatrader",
            "account",
            "sim101",
            "",
        }
        if nt_mode:
            port_msg = (
                f"Cannot reach {target} — NinjaTrader Fabric host is not listening. "
                "Open Control Center → New → LUMINA (starts host), or run Repair connection."
            )
            port_remediation = (
                "1) Confirm NinjaTrader.exe is running and datafeed Connected. "
                "2) Control Center → New → LUMINA (host must show GREEN / listening). "
                "3) If port stays closed: close LUMINA Link window, wait 3s, open New → LUMINA again. "
                "4) Still red: Repair connection in Lumina (redeploy AddOn), then restart NT once."
            )
        else:
            port_msg = f"Cannot reach {target}"
            port_remediation = (
                "Start ONE Fabric host: SimHost or NT8 AddOn (not both) on 127.0.0.1:50051. "
                "SIM auto-start looks for Lumina.Execution.Fabric.SimHost.exe under integrations/."
            )
        checks.append(
            _p().DiagnosticCheck(
                id="port_listen",
                title="Fabric port reachable",
                status="fail",
                message=port_msg,
                detail=simhost_detail or tcp_msg,
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        remediation.append(port_remediation)
        return PreflightContext(
            host=host,
            port=port,
            gateway_mode=gateway_mode,
            target=target,
            token=token,
            checks=checks,
            remediation=remediation,
            early_report=finalize_report(checks, started, t0, target, gateway_mode, remediation),
        )

    if not token:
        return PreflightContext(
            host=host,
            port=port,
            gateway_mode=gateway_mode,
            target=target,
            token=token,
            checks=checks,
            remediation=remediation,
            early_report=finalize_report(checks, started, t0, target, gateway_mode, remediation),
        )

    return PreflightContext(
        host=host,
        port=port,
        gateway_mode=gateway_mode,
        target=target,
        token=token,
        checks=checks,
        remediation=remediation,
        early_report=None,
    )
