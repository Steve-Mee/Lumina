"""Fabric connection diagnostics — preflight checks (Wave B2 PR-C1).

Token / fabric.json / config / TCP. Shared types + finalize live here.
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

CheckStatus = Literal["pass", "fail", "warn", "skip"]
OverallStatus = Literal["green", "amber", "red"]

CRITICAL_CHECK_IDS = frozenset(
    {
        "token_present",
        "port_listen",
        "auth_ok",
        "place_order",
        "flatten",
        "safe_mode_enter",
    }
)


@dataclass
class DiagnosticCheck:
    id: str
    title: str
    status: CheckStatus
    message: str
    detail: str | None = None
    duration_ms: int = 0


@dataclass
class FabricConnectionReport:
    overall: OverallStatus
    started_at: str
    duration_ms: int
    target: str
    gateway_mode: str
    checks: list[DiagnosticCheck] = field(default_factory=list)
    summary: str = ""
    remediation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "target": self.target,
            "gateway_mode": self.gateway_mode,
            "checks": [asdict(c) for c in self.checks],
            "summary": self.summary,
            "remediation": self.remediation,
        }


def _fabric_json_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric.json"
    return Path.home() / ".config" / "LUMINA" / "fabric.json"


def _audit_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric-audit.jsonl"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric-audit.jsonl"
    return Path.home() / ".config" / "LUMINA" / "fabric-audit.jsonl"


def _resolve_token() -> str:
    return str(
        os.getenv("LUMINA_FABRIC_TOKEN") or os.getenv("LUMINA_NT8_API_KEY") or ""
    ).strip()


def _load_fabric_json() -> dict[str, Any]:
    path = _fabric_json_path()
    if not path.is_file():
        return {}
    try:
        # PowerShell Set-Content often writes UTF-8 BOM — accept utf-8-sig.
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_broker_config() -> dict[str, Any]:
    """Load broker section from LUMINA_CONFIG / config.yaml (cwd-independent)."""
    try:
        import yaml
    except ImportError:
        return {}
    candidates = [
        Path(os.getenv("LUMINA_CONFIG", "") or ""),
        Path.cwd() / "config.yaml",
        Path.cwd().parent / "config.yaml",
    ]
    for path in candidates:
        if not path or not str(path).strip() or not path.is_file():
            continue
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                broker = raw.get("broker")
                return broker if isinstance(broker, dict) else {}
        except Exception:
            continue
    return {}


def _tcp_check(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "TCP connect ok"
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _is_localhost(host: str) -> bool:
    h = host.strip().lower()
    return h in {"127.0.0.1", "localhost", "::1"}


def finalize_report(
    checks: list[DiagnosticCheck],
    started: str,
    t0: float,
    target: str,
    gateway_mode: str,
    remediation: list[str],
) -> FabricConnectionReport:
    critical_fail = any(
        c.status == "fail" and c.id in CRITICAL_CHECK_IDS for c in checks
    )
    any_fail = any(c.status == "fail" for c in checks)
    any_warn = any(c.status == "warn" for c in checks)
    if critical_fail or any_fail:
        overall: OverallStatus = "red"
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

    return FabricConnectionReport(
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
    host: str
    port: int
    gateway_mode: str
    target: str
    token: str
    checks: list[DiagnosticCheck]
    remediation: list[str]
    early_report: FabricConnectionReport | None = None


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
    checks: list[DiagnosticCheck] = []
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
        or "sim"
    ).strip().lower()
    target = f"{host}:{port}"

    # 1 token
    t = time.perf_counter()
    token = resolve_token()
    if token:
        checks.append(
            DiagnosticCheck(
                id="token_present",
                title="Fabric auth token",
                status="pass",
                message="LUMINA_FABRIC_TOKEN (or legacy LUMINA_NT8_API_KEY) is set",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
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
        gw = str(fabric_cfg.get("GatewayMode", "sim")).lower()
        status: CheckStatus = "pass"
        msg = f"Found {fj_path} (GatewayMode={gw})"
        if gw not in {"sim", "nt", "ninjatrader"}:
            status = "warn"
            msg += " — unexpected GatewayMode"
        if gw in {"nt", "ninjatrader"}:
            status = "warn"
            msg += " — prefer GatewayMode=sim until NtOrderGateway is bound"
        checks.append(
            DiagnosticCheck(
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
            DiagnosticCheck(
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
    live_provider = str(broker.get("live_provider") or "crosstrade").lower()
    nt_enabled = bool(nt.get("enabled", False))
    if live_provider == "ninjatrader" and nt_enabled:
        checks.append(
            DiagnosticCheck(
                id="config_alignment",
                title="Brain config (live_provider)",
                status="pass",
                message="broker.live_provider=ninjatrader and ninjatrader.enabled=true",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
    elif live_provider == "ninjatrader" and not nt_enabled:
        checks.append(
            DiagnosticCheck(
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
            DiagnosticCheck(
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
            DiagnosticCheck(
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

    # 4 TCP
    t = time.perf_counter()
    ok_tcp, tcp_msg = tcp_check(host, port)
    if ok_tcp:
        checks.append(
            DiagnosticCheck(
                id="port_listen",
                title="Fabric port reachable",
                status="pass",
                message=f"{target} accepts TCP",
                detail=tcp_msg,
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                id="port_listen",
                title="Fabric port reachable",
                status="fail",
                message=f"Cannot reach {target}",
                detail=tcp_msg,
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        remediation.append(
            "Start ONE Fabric host: SimHost or NT8 AddOn (not both) on 127.0.0.1:50051."
        )
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
