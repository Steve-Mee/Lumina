"""Post-install NinjaTrader Execution Fabric connection diagnostics (SIM only).

Tests Brain ↔ Fabric gRPC directly — never CrossTrade.
"""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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


def run_fabric_connection_diagnostics(
    *,
    include_safe_mode: bool = True,
    instrument: str = "MES",
) -> FabricConnectionReport:
    """Run ordered SIM-only Fabric diagnostics. Never touches CrossTrade."""
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()
    checks: list[DiagnosticCheck] = []
    remediation: list[str] = []

    fabric_cfg = _load_fabric_json()
    broker = _load_broker_config()
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
    token = _resolve_token()
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
    fj_path = _fabric_json_path()
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
    if not _is_localhost(host):
        checks.append(
            DiagnosticCheck(
                id="port_listen",
                title="Fabric port reachable",
                status="fail",
                message=f"Host {host} rejected — diagnostics only allow localhost (fail-closed)",
            )
        )
        remediation.append("Bind Fabric to 127.0.0.1 only (BindLocalhostOnly=true).")
        return _finalize(checks, started, t0, target, gateway_mode, remediation)

    # 4 TCP
    t = time.perf_counter()
    ok_tcp, tcp_msg = _tcp_check(host, port)
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
        return _finalize(checks, started, t0, target, gateway_mode, remediation)

    if not token:
        return _finalize(checks, started, t0, target, gateway_mode, remediation)

    # Live gRPC checks
    try:
        from lumina_core.broker.broker_bridge.schemas import Order
        from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient
    except ImportError as exc:
        checks.append(
            DiagnosticCheck(
                id="auth_ok",
                title="Fabric auth (correct token)",
                status="fail",
                message=f"grpc / fabric client unavailable: {exc}",
            )
        )
        remediation.append("Install grpcio and generate fabric stubs (scripts/generate_fabric_proto.py).")
        return _finalize(checks, started, t0, target, gateway_mode, remediation)

    def make_client(auth: str, *, hb_ms: int = 500) -> FabricGrpcClient:
        return FabricGrpcClient(
            FabricConfig(
                host=host,
                port=port,
                auth_token=auth,
                mode_context="sim",
                heartbeat_interval_ms=hb_ms,
                connect_timeout_seconds=5.0,
                command_timeout_seconds=8.0,
            )
        )

    # 5 auth ok
    t = time.perf_counter()
    client: FabricGrpcClient | None = None
    try:
        client = make_client(token)
        if client.connect():
            checks.append(
                DiagnosticCheck(
                    id="auth_ok",
                    title="Fabric auth (correct token)",
                    status="pass",
                    message=f"Authenticated session={client.session_id} account={client.account_name}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    id="auth_ok",
                    title="Fabric auth (correct token)",
                    status="fail",
                    message="Auth failed with configured token",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
            remediation.append("Token mismatch: set the same LUMINA_FABRIC_TOKEN for Brain and NT8 (User env), then restart NT.")
            try:
                client.disconnect()
            except Exception:
                pass
            return _finalize(checks, started, t0, target, gateway_mode, remediation)
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="auth_ok",
                title="Fabric auth (correct token)",
                status="fail",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        return _finalize(checks, started, t0, target, gateway_mode, remediation)

    # 6 auth reject (wrong token)
    t = time.perf_counter()
    bad = make_client("definitely-wrong-token-" + uuid.uuid4().hex[:8], hb_ms=0)
    try:
        bad_ok = bad.connect()
        if bad_ok:
            checks.append(
                DiagnosticCheck(
                    id="auth_reject",
                    title="Auth rejects wrong token",
                    status="fail",
                    message="Wrong token was accepted — security fail-closed broken",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
            remediation.append("Fabric host must reject invalid AuthToken.")
        else:
            checks.append(
                DiagnosticCheck(
                    id="auth_reject",
                    title="Auth rejects wrong token",
                    status="pass",
                    message="Invalid token correctly rejected",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
    finally:
        try:
            bad.disconnect()
        except Exception:
            pass

    # 7 account state
    t = time.perf_counter()
    try:
        assert client is not None
        account, _positions, code = client.get_account_state()
        if code == "ok" and account is not None:
            checks.append(
                DiagnosticCheck(
                    id="account_state",
                    title="Account state snapshot",
                    status="pass",
                    message=f"equity={getattr(account, 'equity', None)}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    id="account_state",
                    title="Account state snapshot",
                    status="warn",
                    message=f"GetAccountState code={code}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="account_state",
                title="Account state snapshot",
                status="warn",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )

    # 8 place
    t = time.perf_counter()
    place_ok = False
    try:
        assert client is not None
        cid = f"diag-place-{uuid.uuid4().hex[:8]}"
        place = client.place_order_sync(
            Order(symbol=instrument, side="BUY", quantity=1, order_type="MARKET"),
            client_order_id=cid,
            correlation_id=f"corr-{cid}",
        )
        place_ok = place.get("type") != "error"
        checks.append(
            DiagnosticCheck(
                id="place_order",
                title=f"Place SIM order ({instrument})",
                status="pass" if place_ok else "fail",
                message=str(place.get("message") or place.get("type") or place),
                detail=json.dumps(place, default=str)[:500],
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        if not place_ok:
            remediation.append(f"Place failed: {place}. Check SAFE_MODE and host logs.")
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="place_order",
                title=f"Place SIM order ({instrument})",
                status="fail",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )

    # 9 flatten
    t = time.perf_counter()
    try:
        assert client is not None
        flat = client.flatten_sync(instrument=instrument)
        flat_ok = flat.get("type") != "error"
        checks.append(
            DiagnosticCheck(
                id="flatten",
                title="Flatten position",
                status="pass" if flat_ok else "fail",
                message=str(flat.get("type") or flat),
                detail=json.dumps(flat, default=str)[:500],
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )
        if not flat_ok:
            remediation.append(f"Flatten failed: {flat}")
    except Exception as exc:
        checks.append(
            DiagnosticCheck(
                id="flatten",
                title="Flatten position",
                status="fail",
                message=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )

    try:
        assert client is not None
        client.disconnect()
    except Exception:
        pass
    client = None

    # 10–12 SAFE_MODE path
    if include_safe_mode:
        t = time.perf_counter()
        c2 = make_client(token, hb_ms=0)
        try:
            if not c2.connect():
                checks.append(
                    DiagnosticCheck(
                        id="safe_mode_enter",
                        title="SAFE_MODE blocks new orders",
                        status="skip",
                        message="Could not reconnect for SAFE_MODE probe",
                        duration_ms=int((time.perf_counter() - t) * 1000),
                    )
                )
            else:
                # Wait past default 5s heartbeat timeout
                time.sleep(6.2)
                rej = c2.place_order_sync(
                    Order(symbol=instrument, side="BUY", quantity=1, order_type="MARKET"),
                    client_order_id=f"diag-safe-{uuid.uuid4().hex[:6]}",
                )
                safe_hit = (
                    str(rej.get("code", "")).upper() == "SAFE_MODE"
                    or "SAFE" in str(rej).upper()
                )
                checks.append(
                    DiagnosticCheck(
                        id="safe_mode_enter",
                        title="SAFE_MODE blocks new orders",
                        status="pass" if safe_hit else "fail",
                        message=(
                            "Place rejected with SAFE_MODE after heartbeat timeout"
                            if safe_hit
                            else f"Expected SAFE_MODE reject, got {rej}"
                        ),
                        detail=json.dumps(rej, default=str)[:500],
                        duration_ms=int((time.perf_counter() - t) * 1000),
                    )
                )
                if not safe_hit:
                    remediation.append(
                        "Heartbeat watchdog did not enter SAFE_MODE — check Fabric host HeartbeatTimeoutMs."
                    )

                t2 = time.perf_counter()
                flat_safe = c2.flatten_sync(instrument=instrument)
                flat_safe_ok = flat_safe.get("type") != "error"
                checks.append(
                    DiagnosticCheck(
                        id="safe_mode_flatten_allowed",
                        title="Flatten allowed in SAFE_MODE",
                        status="pass" if flat_safe_ok else "fail",
                        message=str(flat_safe.get("type") or flat_safe),
                        duration_ms=int((time.perf_counter() - t2) * 1000),
                    )
                )
        finally:
            try:
                c2.disconnect()
            except Exception:
                pass

        # 12 reauth clears
        t = time.perf_counter()
        c3 = make_client(token, hb_ms=500)
        try:
            if c3.connect():
                time.sleep(0.6)
                place2 = c3.place_order_sync(
                    Order(symbol=instrument, side="BUY", quantity=1, order_type="MARKET"),
                    client_order_id=f"diag-reauth-{uuid.uuid4().hex[:6]}",
                )
                reauth_ok = place2.get("type") != "error"
                checks.append(
                    DiagnosticCheck(
                        id="reauth_clears_safe",
                        title="Re-auth recovers trading",
                        status="pass" if reauth_ok else "warn",
                        message=(
                            "Place accepted after re-auth"
                            if reauth_ok
                            else f"Still blocked after re-auth: {place2}"
                        ),
                        duration_ms=int((time.perf_counter() - t) * 1000),
                    )
                )
                try:
                    c3.flatten_sync(instrument=instrument)
                except Exception:
                    pass
            else:
                checks.append(
                    DiagnosticCheck(
                        id="reauth_clears_safe",
                        title="Re-auth recovers trading",
                        status="warn",
                        message="Reconnect after SAFE_MODE failed",
                        duration_ms=int((time.perf_counter() - t) * 1000),
                    )
                )
        finally:
            try:
                c3.disconnect()
            except Exception:
                pass
    else:
        checks.append(
            DiagnosticCheck(
                id="safe_mode_enter",
                title="SAFE_MODE blocks new orders",
                status="skip",
                message="Skipped (include_safe_mode=false)",
            )
        )

    # 13 audit trail
    t = time.perf_counter()
    audit = _audit_path()
    if audit.is_file():
        try:
            lines = audit.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            joined = "\n".join(lines)
            has_auth = "auth_ok" in joined or "authenticated" in joined
            has_place = "place_order" in joined
            has_safe = "SafeMode" in joined or "HeartbeatTimeout" in joined or "safety_alert" in joined
            ok_audit = has_auth or has_place
            checks.append(
                DiagnosticCheck(
                    id="audit_trail",
                    title="Audit log evidence",
                    status="pass" if ok_audit else "warn",
                    message=f"{audit.name}: auth={has_auth} place={has_place} safety={has_safe}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
        except OSError as exc:
            checks.append(
                DiagnosticCheck(
                    id="audit_trail",
                    title="Audit log evidence",
                    status="warn",
                    message=f"Could not read audit: {exc}",
                    duration_ms=int((time.perf_counter() - t) * 1000),
                )
            )
    else:
        checks.append(
            DiagnosticCheck(
                id="audit_trail",
                title="Audit log evidence",
                status="warn",
                message=f"No audit file at {audit}",
                duration_ms=int((time.perf_counter() - t) * 1000),
            )
        )

    return _finalize(checks, started, t0, target, gateway_mode, remediation)


def _finalize(
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
