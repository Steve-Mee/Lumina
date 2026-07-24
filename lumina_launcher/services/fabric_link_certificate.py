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
    if str(overall).lower() != "green":
        return None
    path = certificate_path(workspace_root)
    payload: dict[str, Any] = {
        "overall": "green",
        "ts_unix": time.time(),
        "target": target,
        "token_fp": token_fingerprint(token),
    }
    if extra:
        payload.update(extra)
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


def is_fabric_link_green(
    *,
    token: str | None = None,
    workspace_root: Path | None = None,
    max_age_hours: float = 24.0 * 14,
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
