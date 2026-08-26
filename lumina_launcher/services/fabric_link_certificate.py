"""Persist Fabric link certification (GREEN-only) — fail-closed gate for Birth."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CERT_FILENAME = "fabric_link_certificate.json"
HALT_FILENAME = "fabric_halt.json"
FINGERPRINT_FILENAME = "ninjatrader_fingerprint.json"


def _state_dir(workspace_root: Path | None = None) -> Path:
    root = workspace_root or Path(os.getenv("LUMINA_WORKSPACE", ".")).resolve()
    path = root / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def token_fingerprint(token: str) -> str:
    raw = str(token or "").strip().encode("utf-8")
    if not raw:
        return ""
    return hashlib.sha256(raw).hexdigest()[:16]


def certificate_path(workspace_root: Path | None = None) -> Path:
    return _state_dir(workspace_root) / CERT_FILENAME


def halt_path(workspace_root: Path | None = None) -> Path:
    return _state_dir(workspace_root) / HALT_FILENAME


def fingerprint_path(workspace_root: Path | None = None) -> Path:
    return _state_dir(workspace_root) / FINGERPRINT_FILENAME


def write_certificate(
    *,
    overall: str,
    target: str,
    token: str,
    workspace_root: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> Path | None:
    """Persist GREEN dual-plane proof only.

    ADR-0040: dual-plane GREEN requires objective historical_bars proof
    (Fabric + NT BarsRequest path), not order-plane alone. Callers that
    already gated ``overall==green`` via CRITICAL_CHECK_IDS (includes
    historical_bars) may omit extra; if ``extra`` provides checks or
    historical_bars status, fail closed when history is not pass.
    """
    if str(overall).lower() != "green":
        return None

    extra_d = dict(extra or {})
    hist_status = str(extra_d.get("historical_bars") or extra_d.get("historical_bars_status") or "").strip().lower()
    checks = extra_d.get("checks")
    # When caller supplies dual-plane evidence, require historical_bars PASS.
    # overall==green without extra is allowed only when CRITICAL_CHECK_IDS already
    # forced historical_bars (diagnostic finalize) — callers should still pass checks.
    if hist_status and hist_status not in {"pass", "ok", "green"}:
        logger.warning(
            "write_certificate refused: historical_bars=%s (dual-plane proof required)",
            hist_status,
        )
        return None
    if isinstance(checks, list):
        hist = next(
            (
                c
                for c in checks
                if isinstance(c, dict) and str(c.get("id") or "") == "historical_bars"
            ),
            None,
        )
        if hist is None:
            logger.warning(
                "write_certificate refused: checks provided without historical_bars "
                "(dual-plane proof required per ADR-0040)"
            )
            return None
        if str(hist.get("status") or "").lower() not in {
            "pass",
            "ok",
            "green",
        }:
            logger.warning(
                "write_certificate refused: historical_bars check not pass (status=%s)",
                hist.get("status"),
            )
            return None

    path = certificate_path(workspace_root)
    payload: dict[str, Any] = {
        "overall": "green",
        "ts_unix": time.time(),
        "target": target,
        "token_fp": token_fingerprint(token),
        "dual_plane": True,
        "proof": "fabric_nt_barsrequest",
    }
    if extra_d:
        # Do not let extra overwrite dual_plane / proof markers with weaker claims.
        for k, v in extra_d.items():
            if k in {"dual_plane", "proof", "overall"}:
                continue
            payload[k] = v
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # Clear halt on successful cert
    clear_halt(workspace_root)
    return path


def read_certificate(workspace_root: Path | None = None) -> dict[str, Any] | None:
    path = certificate_path(workspace_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def invalidate_certificate(workspace_root: Path | None = None, reason: str = "") -> None:
    path = certificate_path(workspace_root)
    try:
        if path.is_file():
            path.unlink()
            logger.info("Fabric certificate invalidated: %s", reason or "unspecified")
    except OSError:
        logger.warning("Could not invalidate fabric certificate", exc_info=True)


# Legacy paper-cert window (proof only — never primary live GREEN by itself).
# Live color comes from fabric_link_health.compute_level / build_fabric_link_health.
DEFAULT_FABRIC_LINK_MAX_AGE_HOURS = 24.0 * 14
# Birth activate: dual-plane proof must be recent; AND live host must be up
# (enforced in fabric_link_health.gate_birth_ok — not cert alone).
BIRTH_FABRIC_LINK_MAX_AGE_HOURS = 2.0
# Operator Vault "Certified" badge freshness (live color is separate).
PROOF_BADGE_MAX_AGE_HOURS = 0.5


def is_fabric_link_green(
    *,
    token: str | None = None,
    workspace_root: Path | None = None,
    max_age_hours: float = DEFAULT_FABRIC_LINK_MAX_AGE_HOURS,
) -> tuple[bool, str]:
    """Return (ok, reason). Token fingerprint must match when token provided."""
    cert = read_certificate(workspace_root)
    if not cert:
        return False, "FABRIC_LINK_NOT_GREEN"
    if str(cert.get("overall", "")).lower() != "green":
        return False, "FABRIC_LINK_NOT_GREEN"
    ts = float(cert.get("ts_unix") or 0)
    if ts > 0 and (time.time() - ts) > max_age_hours * 3600:
        return False, "FABRIC_LINK_STALE"
    if token is not None:
        fp = token_fingerprint(token)
        if fp and cert.get("token_fp") and cert.get("token_fp") != fp:
            return False, "FABRIC_LINK_TOKEN_CHANGED"
    if is_halt_active(workspace_root):
        return False, "FABRIC_HALT"
    return True, "OK"


def is_fabric_link_green_for_birth(
    *,
    token: str | None = None,
    workspace_root: Path | None = None,
    max_age_hours: float = BIRTH_FABRIC_LINK_MAX_AGE_HOURS,
) -> tuple[bool, str]:
    """Birth/Genesis gate: live host up + recent dual-plane proof (never paper alone).

    ``max_age_hours`` is applied inside fabric_link_health via
    ``BIRTH_FABRIC_LINK_MAX_AGE_HOURS`` (proof window). Token fingerprint
    mismatch still fails closed when ``token`` is provided.
    """
    # Prefer SSOT health (host liveness + proof). Lazy import avoids cycles.
    from lumina_launcher.services.fabric_link_health import build_fabric_link_health

    if token is not None:
        ok_fp, reason_fp = is_fabric_link_green(
            token=token,
            workspace_root=workspace_root,
            max_age_hours=max_age_hours,
        )
        if not ok_fp and reason_fp == "FABRIC_LINK_TOKEN_CHANGED":
            return False, reason_fp

    health = build_fabric_link_health(workspace_root=workspace_root, live={})
    if health.get("gate_birth_ok"):
        return True, "OK"
    return False, str(health.get("gate_reason") or "FABRIC_LINK_NOT_GREEN")


def set_halt(
    *,
    reason: str,
    workspace_root: Path | None = None,
    detail: dict[str, Any] | None = None,
) -> Path:
    path = halt_path(workspace_root)
    payload = {
        "active": True,
        "reason": reason,
        "ts_unix": time.time(),
        "detail": detail or {},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    invalidate_certificate(workspace_root, reason=reason)
    return path


def clear_halt(workspace_root: Path | None = None) -> None:
    path = halt_path(workspace_root)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def is_halt_active(workspace_root: Path | None = None) -> bool:
    path = halt_path(workspace_root)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return bool(data.get("active"))
    except (OSError, json.JSONDecodeError):
        return False


def read_halt(workspace_root: Path | None = None) -> dict[str, Any] | None:
    path = halt_path(workspace_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_nt_fingerprint(
    fingerprint: dict[str, Any],
    workspace_root: Path | None = None,
) -> Path:
    path = fingerprint_path(workspace_root)
    path.write_text(json.dumps(fingerprint, indent=2) + "\n", encoding="utf-8")
    return path


def read_nt_fingerprint(workspace_root: Path | None = None) -> dict[str, Any] | None:
    path = fingerprint_path(workspace_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None
