"""Fabric Link Health SSOT — one truth for LUMINA Link + Operator Vault + Birth.

Live color (level) is never derived from paper certificate alone.
Certificate is proof of dual-plane diagnostic, not proof of host liveness.
"""

from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from lumina_launcher.services.fabric_link_certificate import (
    BIRTH_FABRIC_LINK_MAX_AGE_HOURS,
    PROOF_BADGE_MAX_AGE_HOURS,
    is_halt_active,
    read_certificate,
    read_halt,
)

# Host stop→start grace for RESTARTING (seconds).
RESTARTING_GRACE_SEC = 8.0

FabricLevel = Literal["RED", "AMBER", "GREEN", "RESTARTING"]


def fabric_status_json_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric-nt-host.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric-nt-host.json"
    return Path.home() / ".config" / "LUMINA" / "fabric-nt-host.json"


def fabric_json_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric.json"
    return Path.home() / ".config" / "LUMINA" / "fabric.json"


def fabric_deploy_manifest_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric-deploy-manifest.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric-deploy-manifest.json"
    return Path.home() / ".config" / "LUMINA" / "fabric-deploy-manifest.json"


def _read_deploy_manifest() -> dict[str, Any]:
    """Last deploy integrity snapshot (bridge hash/size) for operator timeline."""
    p = fabric_deploy_manifest_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_host_snapshot(path: Path | None = None) -> dict[str, Any]:
    """Read NT/SimHost status file written by FabricRuntimeStatus.Persist()."""
    p = path or fabric_status_json_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_grpc_target(host_snap: dict[str, Any] | None = None) -> tuple[str, int]:
    snap = host_snap if host_snap is not None else read_host_snapshot()
    host = str(snap.get("bind_host") or snap.get("host_bind") or "").strip()
    port_raw = snap.get("port")
    try:
        port = int(port_raw) if port_raw is not None else 0
    except (TypeError, ValueError):
        port = 0

    if not host or port <= 0:
        try:
            cfg_path = fabric_json_path()
            if cfg_path.is_file():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                if isinstance(cfg, dict):
                    host = host or str(cfg.get("BindHost") or cfg.get("bind_host") or "").strip()
                    if port <= 0:
                        port = int(cfg.get("BindPort") or cfg.get("port") or 0)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    if not host:
        host = "127.0.0.1"
    if port <= 0:
        port = 50051
    return host, port


def tcp_listening(host: str, port: int, timeout: float = 1.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_updated_age_sec(snap: dict[str, Any]) -> float | None:
    raw = snap.get("updated_utc") or snap.get("updated_at")
    if not raw:
        return None
    try:
        text = str(raw).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, time.time() - dt.timestamp())
    except (TypeError, ValueError):
        return None


def compute_level(
    *,
    host_state: str,
    port_listening: bool,
    active_sessions: int,
    safe_mode: str,
    auth_ok: bool,
    host_code: str = "",
    updated_age_sec: float | None = None,
) -> tuple[FabricLevel, str]:
    """Shared color dictionary for Link + Vault (fail-closed).

    GREEN  = host usable + live Brain (session or supervisor auth) + not SAFE/FULL_SAFE
    AMBER  = host usable but waiting for Brain / SAFE mode
    RED    = host not usable
    RESTARTING = brief clean stop window while recycle likely
    """
    state = (host_state or "").strip().lower()
    sm = (safe_mode or "NORMAL").strip().upper()
    sessions = max(0, int(active_sessions or 0))
    code = (host_code or "").strip().lower()
    live_brain = bool(auth_ok) or sessions > 0

    if state in {"stopped", "error", "not_started", ""} or not port_listening:
        # Clean stop with very fresh stamp → recycle, not permanent failure.
        if (
            state == "stopped"
            and code in {"clean", "not_running", ""}
            and updated_age_sec is not None
            and updated_age_sec <= RESTARTING_GRACE_SEC
        ):
            return (
                "RESTARTING",
                "Host restarting — wait a few seconds (do not Repair yet)",
            )
        if code == "port_in_use":
            return "RED", "Bridge failed - port in use (stop SimHost / Repair in Lumina)"
        if code == "no_token":
            return "RED", "Bridge failed - fabric token missing (Repair in Lumina app)"
        if state == "error":
            return "RED", "Bridge error - open Lumina -> Setup -> Repair connection"
        if not port_listening and state == "running":
            return "RED", "Host claims running but port not listening — Repair connection"
        return "RED", "Bridge not running - open Lumina -> Setup -> Repair connection"

    # Host up + port open
    if sm == "FULL_SAFE":
        return "AMBER", "Full safe mode - new orders blocked (Brain heartbeat / recover)"
    if sm == "SAFE" and not live_brain:
        return "AMBER", "Safe mode - waiting for Lumina Brain heartbeats"
    if sm == "SAFE" and live_brain:
        # Heartbeats may clear SAFE shortly; still not full GREEN.
        return "AMBER", "Safe mode clearing - Brain connected"
    if live_brain:
        return "GREEN", "Lumina Brain connected"
    return "AMBER", "Bridge ready - open Lumina to trade / train"


def _live_auth_attention_meaning(live_d: dict[str, Any]) -> str | None:
    """Map Brain supervisor failure to operator copy (never hide AUTH_FAILED as SAFE wait)."""
    if live_d.get("auth_ok") or live_d.get("connected"):
        return None
    code = str(live_d.get("last_error_code") or "").strip().upper()
    err = str(live_d.get("last_error") or "").strip()
    if code in {"AUTH_FAILED", "TOKEN_EMPTY", "AUTH_TIMEOUT"}:
        if code == "TOKEN_EMPTY":
            return "Fabric token missing on Brain — set LUMINA_FABRIC_TOKEN in Setup"
        if code == "AUTH_TIMEOUT":
            return "Fabric auth timed out — host busy or port blocked; retry"
        # AUTH_FAILED: usually stale host token vs dual-written fabric.json SSOT.
        return (
            "Fabric token rejected by host — aligning SSOT. "
            "If this persists: reopen New → LUMINA (host reloads token)."
        )
    if code in {"CONNECTION_REFUSED", "NT_PROCESS_GONE"}:
        return err or "Fabric host not reachable — start NinjaTrader / New → LUMINA"
    return None


def _proof_block(
    workspace_root: Path | None,
) -> dict[str, Any]:
    cert = read_certificate(workspace_root)
    if not cert or str(cert.get("overall", "")).lower() != "green":
        return {
            "certified": False,
            "overall": "none",
            "age_sec": None,
            "target": None,
            "stale": False,
            "badge_ok": False,
        }
    ts = float(cert.get("ts_unix") or 0)
    age = (time.time() - ts) if ts > 0 else None
    badge_ok = age is not None and age <= PROOF_BADGE_MAX_AGE_HOURS * 3600
    birth_ok_age = age is not None and age <= BIRTH_FABRIC_LINK_MAX_AGE_HOURS * 3600
    return {
        "certified": bool(birth_ok_age),  # usable as dual-plane proof within birth window
        "overall": "green",
        "age_sec": age,
        "target": cert.get("target"),
        "stale": bool(age is not None and not birth_ok_age),
        "badge_ok": bool(badge_ok),
        "ts_unix": ts,
    }


def build_fabric_link_health(
    *,
    workspace_root: Path | None = None,
    live: dict[str, Any] | None = None,
    host_snap: dict[str, Any] | None = None,
    port_listening: bool | None = None,
    invalidate_on_host_down: bool = False,
) -> dict[str, Any]:
    """Build canonical FabricLinkHealth payload (schema_version=1).

    ``invalidate_on_host_down`` defaults False so pure gate checks (Birth) are
    side-effect free. Live status polls should pass True to clear sticky certs.
    """
    snap = dict(host_snap) if host_snap is not None else read_host_snapshot()
    host, port = resolve_grpc_target(snap)
    listening = (
        bool(port_listening)
        if port_listening is not None
        else tcp_listening(host, port)
    )

    host_state = str(snap.get("state") or "").strip().lower()
    if not host_state:
        # No status file: infer from port only.
        host_state = "running" if listening else "stopped"
    host_code = str(snap.get("code") or "")
    safe_mode = str(snap.get("safe_mode") or "NORMAL")
    try:
        sessions = int(snap.get("active_sessions") or 0)
    except (TypeError, ValueError):
        sessions = 0
    updated_age = _parse_updated_age_sec(snap)

    # Stale SSOT: host JSON claims running but TCP is dead (classic ShutdownAsync hang
    # or AddOn stop mid-flight). Treat as stopped so gates fail-closed with truth.
    if host_state == "running" and not listening:
        if updated_age is None or updated_age > 5.0:
            host_state = "stopped"
            host_code = "stale_running_port_closed"
            sessions = 0

    live_d = dict(live or {})
    auth_ok = bool(live_d.get("auth_ok"))
    if not auth_ok and live_d.get("connected") and live_d.get("session_id"):
        auth_ok = True
    # In-process host sessions also count as live brain.
    if sessions > 0:
        auth_ok = True

    level, meaning = compute_level(
        host_state=host_state,
        port_listening=listening,
        active_sessions=sessions,
        safe_mode=safe_mode,
        auth_ok=auth_ok,
        host_code=host_code,
        updated_age_sec=updated_age,
    )
    # Override generic SAFE "waiting for heartbeats" when Brain already failed auth —
    # that is the cold-start Systems Go false-negative (stale host token).
    auth_meaning = _live_auth_attention_meaning(live_d)
    if auth_meaning and level in {"AMBER", "RED"} and not auth_ok:
        meaning = auth_meaning

    host_up = listening and host_state == "running"
    # RESTARTING: not host_up yet but not permanent red for gates that wait.
    proof = _proof_block(workspace_root)
    halt = is_halt_active(workspace_root)

    # Fail-closed: paper cert cannot claim live readiness when host is down.
    if invalidate_on_host_down and not listening and host_state in {
        "stopped",
        "error",
        "",
    }:
        # Soft: do not delete cert on every poll during RESTARTING grace.
        if level == "RED":
            try:
                from lumina_launcher.services.fabric_link_certificate import (
                    invalidate_certificate,
                )

                # Only invalidate if cert claims green while host is hard-down
                # longer than grace (avoid thrash on recycle).
                if proof.get("overall") == "green" and (
                    updated_age is None or updated_age > RESTARTING_GRACE_SEC
                ):
                    invalidate_certificate(
                        workspace_root, reason="host_down_live_ssot"
                    )
                    proof = _proof_block(workspace_root)
            except Exception:
                pass

    gate_birth_ok = bool(
        host_up
        and not halt
        and proof.get("certified")
        and str(proof.get("overall") or "") == "green"
    )
    if not host_up:
        gate_reason = "FABRIC_HOST_DOWN"
    elif halt:
        gate_reason = "FABRIC_HALT"
    elif not proof.get("certified"):
        gate_reason = (
            "FABRIC_LINK_STALE"
            if proof.get("stale")
            else "FABRIC_LINK_NOT_GREEN"
        )
    else:
        gate_reason = "OK"

    # Token plane: compare Brain secret fingerprint vs host token_fp (no secret on wire).
    brain_fp = ""
    host_fp = str(snap.get("token_fp") or snap.get("TokenFingerprint") or "").strip()
    token_plane_aligned = True
    try:
        from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

        sec = fabric_secret_read(heal=True)
        brain_fp = str(sec.fingerprint or "")
        if host_fp and brain_fp and host_fp != brain_fp:
            token_plane_aligned = False
            if level == "GREEN":
                level = "AMBER"
                meaning = (
                    "Token plane MISALIGNED — Brain and host secrets differ "
                    "(auto-healed env; re-Test connection / restart NT if persists)"
                )
            elif level == "AMBER" and not auth_ok:
                meaning = (
                    "Token plane MISALIGNED — host may still hold stale secret; "
                    "Repair connection if auth fails"
                )
        if sec.mismatch and token_plane_aligned:
            # Surfaces were divergent but host_fp unknown — still surface honesty.
            meaning = meaning  # keep compute_level meaning
    except Exception:
        token_plane_aligned = True  # fail open on plane check only when read crashes

    # Backward-compatible "green": live GREEN only (never paper-only).
    # host_ready: cold-start / Systems Go can treat AMBER host-up as progress.
    green = level == "GREEN" and token_plane_aligned
    host_ready = host_up or level == "RESTARTING"
    if not token_plane_aligned and gate_birth_ok:
        gate_birth_ok = False
        gate_reason = "TOKEN_PLANE_MISALIGNED"

    deploy_manifest = _read_deploy_manifest()
    return {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "state": host_state or "stopped",
            "code": host_code,
            "kind": str(snap.get("host") or "unknown"),
            "grpc": f"{host}:{port}",
            "bind_host": host,
            "port": port,
            "pid": snap.get("pid"),
            "port_listening": listening,
            "historical_provider": str(snap.get("historical") or ""),
            "safe_mode": safe_mode,
            "active_sessions": sessions,
            "gateway": str(snap.get("gateway") or ""),
            "account": str(snap.get("account") or ""),
            "token_fp": host_fp or None,
            "last_hist": {
                "instrument": snap.get("last_hist_instrument"),
                "bars": snap.get("last_hist_bars"),
                "code": snap.get("last_hist_code"),
                "at": snap.get("last_hist_utc"),
            },
            "updated_utc": snap.get("updated_utc"),
            "deploy": deploy_manifest,
            "updated_age_sec": updated_age,
        },
        "live": {
            "supervisor_running": bool(live_d.get("running")),
            "auth_ok": auth_ok,
            "connected": bool(live_d.get("connected")),
            "session_id": str(live_d.get("session_id") or ""),
            "last_error_code": str(live_d.get("last_error_code") or ""),
            "last_error": str(live_d.get("last_error") or ""),
            "target": str(live_d.get("target") or f"{host}:{port}"),
            "safe_mode": live_d.get("safe_mode"),
            "token_fp": brain_fp or None,
        },
        "token_plane": {
            "aligned": token_plane_aligned,
            "brain_fp": brain_fp or None,
            "host_fp": host_fp or None,
        },
        "proof": proof,
        "level": level,
        "meaning": meaning,
        "green": green,
        "host_ready": host_ready,
        "gate_birth_ok": gate_birth_ok,
        "gate_reason": gate_reason,
        "halt": read_halt(workspace_root) if halt else None,
        "certificate": read_certificate(workspace_root),
        # reason: keep short code for existing clients
        "reason": (
            "TOKEN_PLANE_MISALIGNED"
            if not token_plane_aligned
            else (
                "LIVE_GREEN"
                if green
                else (
                    "HOST_READY_AMBER"
                    if host_up and level == "AMBER"
                    else (
                        "HOST_RESTARTING"
                        if level == "RESTARTING"
                        else gate_reason
                        if not host_up
                        else f"LEVEL_{level}"
                    )
                )
            )
        ),
    }
