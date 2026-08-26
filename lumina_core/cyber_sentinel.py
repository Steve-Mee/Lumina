"""Cyber Security / Sentinel — network/token domain only (ADR-0040 / ADR-0041).

Hard veto rank equals ConstitutionalGuard **only** for:
- Network binding & exposure
- Token / credential handling
- Authn/Authz anomalies
- Intrusion indicators
- Unauthorized external connections

Sentinel MUST NOT place or mutate trades, strategy DNA, or position sizing.
Those remain ConstitutionalGuard + PromotionGate.

30d: bind veto + observe hooks.
90d: observe→contain agent, IP allowlist, weak-token ban, API TLS gates.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

VetoDomain = Literal[
    "network_bind",
    "token",
    "auth",
    "intrusion",
    "external_connection",
    "bus",
    "rate_limit",
]

_AUDIT_REL = Path("logs") / "sentinel_audit.jsonl"
_CONTAINMENT_REL = Path("state") / "sentinel_containment.json"
_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})

# Dev-only tokens never allowed on non-SIM capital-adjacent modes.
_WEAK_FABRIC_TOKENS = frozenset(
    {
        "sim-dev-token",
        "changeme",
        "password",
        "secret",
        "default",
        "token",
    }
)

# Auth failure threshold → network containment (not trade kill).
_AUTH_WINDOW_SEC = 60.0
_AUTH_FAIL_THRESHOLD = 20
_RATE_WINDOW_SEC = 60.0
_RATE_LIMIT_THRESHOLD = 30
_BUS_WINDOW_SEC = 300.0
_BUS_UNAUTHORIZED_THRESHOLD = 5

_lock = threading.RLock()
_auth_fails: deque[float] = deque(maxlen=500)
_rate_hits: deque[float] = deque(maxlen=500)
_bus_rejects: deque[float] = deque(maxlen=200)


@dataclass(frozen=True)
class SentinelVeto:
    domain: VetoDomain
    code: str
    message: str
    hard: bool = True


@dataclass
class ContainmentState:
    active: bool = False
    reason: str = ""
    code: str = ""
    since_unix: float = 0.0
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_loopback_host(host: str) -> bool:
    h = str(host or "").strip().lower()
    if h in _LOOPBACK:
        return True
    if h.startswith("127."):
        return True
    # IPv6 loopback variants
    if h in {"::ffff:127.0.0.1"}:
        return True
    return False


def is_sentinel_active() -> bool:
    return str(os.getenv("LUMINA_SENTINEL_ACTIVE", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }


def parse_ip_allowlist(raw: str | None = None) -> list[ipaddress._BaseNetwork]:
    text = str(raw if raw is not None else os.getenv("LUMINA_IP_ALLOWLIST", "")).strip()
    if not text:
        return []
    networks: list[ipaddress._BaseNetwork] = []
    for part in text.replace(";", ",").split(","):
        item = part.strip()
        if not item:
            continue
        try:
            if "/" in item:
                networks.append(ipaddress.ip_network(item, strict=False))
            else:
                ip = ipaddress.ip_address(item)
                networks.append(ipaddress.ip_network(f"{ip}/{ip.max_prefixlen}", strict=False))
        except ValueError:
            logger.warning("sentinel: invalid allowlist entry %r ignored", item)
    return networks


def client_ip_allowed(client_host: str, *, allowlist_raw: str | None = None) -> bool:
    """Loopback always allowed; otherwise must match LUMINA_IP_ALLOWLIST when set."""
    if is_loopback_host(client_host):
        return True
    networks = parse_ip_allowlist(allowlist_raw)
    if not networks:
        # Empty allowlist: only loopback is safe when non-loopback binds are gated separately.
        # For middleware: if allowlist empty and client non-loopback → deny only when
        # containment active or non-loopback server mode requires allowlist.
        return False
    try:
        host = str(client_host or "").strip()
        if host.startswith("::ffff:"):
            host = host.split("::ffff:", 1)[1]
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def evaluate_api_bind(host: str) -> SentinelVeto | None:
    """Hard veto non-loopback API bind unless multi-layer opt-in is complete."""
    if is_loopback_host(host):
        return None

    allow = str(os.getenv("LUMINA_ALLOW_NON_LOOPBACK", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }
    mtls = str(os.getenv("LUMINA_MTLS_ENABLED", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }
    tls_cert = str(os.getenv("LUMINA_API_TLS_CERT", "")).strip()
    tls_key = str(os.getenv("LUMINA_API_TLS_KEY", "")).strip()
    has_tls = bool(tls_cert and tls_key and Path(tls_cert).is_file() and Path(tls_key).is_file())
    allowlist = str(os.getenv("LUMINA_IP_ALLOWLIST", "")).strip()
    sentinel_on = is_sentinel_active()

    missing: list[str] = []
    if not allow:
        missing.append("LUMINA_ALLOW_NON_LOOPBACK")
    if not (mtls or has_tls):
        missing.append("LUMINA_MTLS_ENABLED|LUMINA_API_TLS_CERT+KEY")
    if not allowlist:
        missing.append("LUMINA_IP_ALLOWLIST")
    if not sentinel_on:
        missing.append("LUMINA_SENTINEL_ACTIVE")

    if missing:
        return SentinelVeto(
            domain="network_bind",
            code="NON_LOOPBACK_FORBIDDEN",
            message=(
                f"Non-loopback bind {host!r} is a permanent non-goal without "
                f"TLS/mTLS + allowlist + Sentinel. Missing: {', '.join(missing)}"
            ),
            hard=True,
        )
    return None


def resolve_api_bind_host(default: str = "127.0.0.1") -> str:
    """Resolve Command Deck bind host; raise on Sentinel hard veto."""
    host = str(os.getenv("LUMINA_API_BIND") or default).strip() or default
    veto = evaluate_api_bind(host)
    if veto is not None and veto.hard:
        _audit_veto(veto, host=host)
        raise RuntimeError(veto.message)
    return host


def resolve_uvicorn_ssl() -> dict[str, str] | None:
    """Return uvicorn ssl kwargs when TLS cert/key env are set and valid."""
    cert = str(os.getenv("LUMINA_API_TLS_CERT", "")).strip()
    key = str(os.getenv("LUMINA_API_TLS_KEY", "")).strip()
    if not cert and not key:
        return None
    if not cert or not key:
        raise RuntimeError(
            "Partial TLS config: set both LUMINA_API_TLS_CERT and LUMINA_API_TLS_KEY"
        )
    if not Path(cert).is_file() or not Path(key).is_file():
        raise RuntimeError("LUMINA_API_TLS_CERT/KEY paths must exist")
    return {"ssl_certfile": cert, "ssl_keyfile": key}


def assert_fabric_token_safe(token: str, *, mode_context: str = "sim") -> None:
    """Reject weak/dev tokens outside SIM (ADR-0041).

    ``sim-dev-token`` is SimHost-only. Brain in sim_real_guard/real must never use it.
    """
    tok = str(token or "").strip()
    if not tok:
        raise RuntimeError("Fabric auth token is empty (fail-closed)")
    mode = str(mode_context or "sim").strip().lower()
    weak = tok.lower() in _WEAK_FABRIC_TOKENS
    if not weak:
        return
    if mode in {"sim", "paper"}:
        # Explicit opt-in still required for sim-dev-token in process env for Brain.
        if tok.lower() == "sim-dev-token":
            allow = str(os.getenv("LUMINA_FABRIC_ALLOW_SIM_DEV_TOKEN", "")).strip().lower() in {
                "1",
                "true",
                "yes",
            }
            if not allow:
                observe_fabric_token_reject(code="sim_dev_token_without_allow")
                raise RuntimeError(
                    "sim-dev-token blocked for Brain unless LUMINA_FABRIC_ALLOW_SIM_DEV_TOKEN=true "
                    "(SimHost may use it locally; production tokens required otherwise)"
                )
        observe_fabric_token_reject(code=f"weak_token_sim_allowed:{tok[:8]}")
        return
    observe_fabric_token_reject(code=f"weak_token_forbidden:{mode}")
    raise RuntimeError(
        f"Weak Fabric token forbidden in mode={mode!r} (use a strong LUMINA_FABRIC_TOKEN)"
    )


# ── Containment SSOT ──────────────────────────────────────────────────────────


def containment_path(workspace_root: Path | None = None) -> Path:
    root = workspace_root or Path(os.getenv("LUMINA_WORKSPACE") or ".").resolve()
    return root / _CONTAINMENT_REL


def read_containment(workspace_root: Path | None = None) -> ContainmentState:
    path = containment_path(workspace_root)
    if not path.is_file():
        return ContainmentState()
    try:
        data: dict[str, Any] | None = None
        try:
            from lumina_core.crypto_at_rest import read_json_secure

            data = read_json_secure(path)
        except Exception:
            data = None
        if data is None:
            raw = path.read_text(encoding="utf-8-sig")
            parsed = json.loads(raw)
            data = parsed if isinstance(parsed, dict) else None
        if not isinstance(data, dict):
            return ContainmentState()
        return ContainmentState(
            active=bool(data.get("active")),
            reason=str(data.get("reason") or ""),
            code=str(data.get("code") or ""),
            since_unix=float(data.get("since_unix") or 0.0),
            actions=list(data.get("actions") or []),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return ContainmentState()


def is_containment_active(workspace_root: Path | None = None) -> bool:
    return bool(read_containment(workspace_root).active)


def activate_containment(
    *,
    reason: str,
    code: str,
    actions: list[str] | None = None,
    workspace_root: Path | None = None,
) -> ContainmentState:
    """Fail-closed network/token containment — never mutates orders/trades."""
    state = ContainmentState(
        active=True,
        reason=str(reason or "unspecified"),
        code=str(code or "CONTAIN"),
        since_unix=time.time(),
        actions=list(
            actions
            or [
                "block_non_loopback_clients",
                "require_api_key_off_loopback",
                "reject_weak_fabric_tokens",
            ]
        ),
    )
    path = containment_path(workspace_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from lumina_core.crypto_at_rest import encryption_enabled, write_json_secure

            if encryption_enabled():
                write_json_secure(path, state.to_dict())
            else:
                path.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
        except Exception:
            path.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
    except OSError:
        logger.warning("sentinel containment write failed", exc_info=True)
    _append_audit(
        workspace_root,
        {
            "kind": "containment_activate",
            "code": state.code,
            "reason": state.reason,
            "actions": state.actions,
        },
    )
    logger.error(
        "sentinel.containment ACTIVE code=%s reason=%s actions=%s",
        state.code,
        state.reason,
        state.actions,
    )
    return state


def clear_containment(
    *,
    reason: str = "operator_clear",
    workspace_root: Path | None = None,
) -> None:
    """Human/operator clear only — Twin may propose, not auto-clear without policy."""
    path = containment_path(workspace_root)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        logger.warning("sentinel containment clear failed", exc_info=True)
    _append_audit(workspace_root, {"kind": "containment_clear", "reason": reason})
    logger.warning("sentinel.containment cleared reason=%s", reason)


# ── Observe + threshold evaluate ──────────────────────────────────────────────


def observe_auth_failure(
    *,
    principal: str,
    reason: str,
    workspace_root: Path | None = None,
) -> None:
    now = time.time()
    with _lock:
        _auth_fails.append(now)
        _trim(_auth_fails, now, _AUTH_WINDOW_SEC)
        count = len(_auth_fails)
    _append_audit(
        workspace_root,
        {
            "kind": "auth_failure",
            "principal": principal,
            "reason": reason,
            "window_count": count,
        },
    )
    if count >= _AUTH_FAIL_THRESHOLD:
        activate_containment(
            reason=f"auth_failure_burst count={count} window={_AUTH_WINDOW_SEC}s",
            code="AUTH_BURST",
            workspace_root=workspace_root,
        )


def observe_rate_limit(
    *,
    client_id: str,
    workspace_root: Path | None = None,
) -> None:
    now = time.time()
    with _lock:
        _rate_hits.append(now)
        _trim(_rate_hits, now, _RATE_WINDOW_SEC)
        count = len(_rate_hits)
    _append_audit(
        workspace_root,
        {"kind": "rate_limit", "client_id": client_id, "window_count": count},
    )
    if count >= _RATE_LIMIT_THRESHOLD:
        activate_containment(
            reason=f"rate_limit_burst count={count}",
            code="RATE_BURST",
            workspace_root=workspace_root,
        )


def observe_fabric_token_reject(
    *,
    code: str = "token_reject",
    workspace_root: Path | None = None,
) -> None:
    _append_audit(
        workspace_root,
        {"kind": "fabric_token_reject", "code": code},
    )


def observe_unauthorized_producer(
    *,
    topic: str,
    producer: str,
    workspace_root: Path | None = None,
) -> None:
    now = time.time()
    with _lock:
        _bus_rejects.append(now)
        _trim(_bus_rejects, now, _BUS_WINDOW_SEC)
        count = len(_bus_rejects)
    _append_audit(
        workspace_root,
        {
            "kind": "unauthorized_producer",
            "topic": topic,
            "producer": producer,
            "window_count": count,
        },
    )
    if count >= _BUS_UNAUTHORIZED_THRESHOLD:
        activate_containment(
            reason=f"bus unauthorized_producer burst count={count} last={producer}@{topic}",
            code="BUS_UNAUTHORIZED_BURST",
            workspace_root=workspace_root,
        )


def evaluate_client_access(
    client_host: str,
    *,
    workspace_root: Path | None = None,
) -> SentinelVeto | None:
    """Middleware gate: containment + allowlist for non-loopback clients."""
    if is_loopback_host(client_host):
        return None
    if is_containment_active(workspace_root):
        state = read_containment(workspace_root)
        return SentinelVeto(
            domain="intrusion",
            code="CONTAINMENT_ACTIVE",
            message=f"Sentinel containment active: {state.code} — {state.reason}",
            hard=True,
        )
    # When allowlist configured, enforce for all non-loopback clients.
    if str(os.getenv("LUMINA_IP_ALLOWLIST", "")).strip():
        if not client_ip_allowed(client_host):
            return SentinelVeto(
                domain="external_connection",
                code="IP_NOT_ALLOWLISTED",
                message=f"Client {client_host!r} not in LUMINA_IP_ALLOWLIST",
                hard=True,
            )
    # Non-loopback API without allowlist is only legal if bind already passed full gate;
    # still require allowlist for remote clients when server is non-loopback.
    bind = str(os.getenv("LUMINA_API_BIND") or "127.0.0.1").strip()
    if not is_loopback_host(bind) and not str(os.getenv("LUMINA_IP_ALLOWLIST", "")).strip():
        return SentinelVeto(
            domain="network_bind",
            code="ALLOWLIST_REQUIRED",
            message="Non-loopback server requires LUMINA_IP_ALLOWLIST for remote clients",
            hard=True,
        )
    return None


def status_snapshot(workspace_root: Path | None = None) -> dict[str, Any]:
    """Operator/status payload — no secrets."""
    now = time.time()
    with _lock:
        _trim(_auth_fails, now, _AUTH_WINDOW_SEC)
        _trim(_rate_hits, now, _RATE_WINDOW_SEC)
        _trim(_bus_rejects, now, _BUS_WINDOW_SEC)
        auth_n = len(_auth_fails)
        rate_n = len(_rate_hits)
        bus_n = len(_bus_rejects)
    c = read_containment(workspace_root)
    return {
        "sentinel_active_flag": is_sentinel_active(),
        "containment": c.to_dict(),
        "windows": {
            "auth_fails": auth_n,
            "rate_hits": rate_n,
            "bus_unauthorized": bus_n,
        },
        "thresholds": {
            "auth_fails": _AUTH_FAIL_THRESHOLD,
            "rate_hits": _RATE_LIMIT_THRESHOLD,
            "bus_unauthorized": _BUS_UNAUTHORIZED_THRESHOLD,
        },
        "domain": "network_token_only",
        "trades_forbidden": True,
    }


def _trim(q: deque[float], now: float, window: float) -> None:
    while q and (now - q[0]) > window:
        q.popleft()


def _audit_veto(veto: SentinelVeto, *, host: str = "") -> None:
    logger.error(
        "sentinel.veto domain=%s code=%s host=%s msg=%s",
        veto.domain,
        veto.code,
        host,
        veto.message,
    )
    _append_audit(
        None,
        {
            "kind": "veto",
            "domain": veto.domain,
            "code": veto.code,
            "host": host,
            "message": veto.message,
            "hard": veto.hard,
        },
    )


def _append_audit(workspace_root: Path | None, payload: dict[str, Any]) -> None:
    root = workspace_root or Path(os.getenv("LUMINA_WORKSPACE") or ".").resolve()
    path = root / _AUDIT_REL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        logger.warning("sentinel audit write failed", exc_info=True)
