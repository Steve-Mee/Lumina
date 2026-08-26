"""Admin API key rotation with dual-key grace window (v51 / ADR-0042).

Machine truth:
- Current: ``LUMINA_ADMIN_API_KEY``
- Previous (grace): ``LUMINA_ADMIN_API_KEY_PREVIOUS``
- Grace until unix: ``LUMINA_API_KEY_GRACE_UNTIL`` (optional; default 24h from rotate)

``APIKeyAuthenticator.verify_api_key`` accepts previous key while grace active.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_GRACE_HOURS = 24.0


@dataclass(frozen=True)
class RotationResult:
    new_key: str
    previous_key: str
    grace_until_unix: float
    env_path: str


def grace_active(*, now: float | None = None) -> bool:
    """Return True only while dual-key grace is valid.

    Requires ``LUMINA_API_KEY_GRACE_UNTIL`` (unix). If missing, grace is OFF
    even when PREVIOUS is set — fail-closed (prevents eternal previous keys).
    """
    raw = str(os.getenv("LUMINA_API_KEY_GRACE_UNTIL", "") or "").strip()
    if not raw:
        return False
    try:
        until = float(raw)
    except ValueError:
        return False
    t = now if now is not None else time.time()
    # Hard ceiling: never honor more than 7 days from now (misconfigured far-future).
    max_window = 7.0 * 24.0 * 3600.0
    effective_until = min(float(until), t + max_window)
    return t < effective_until


def previous_key_meta() -> dict[str, Any] | None:
    prev = str(os.getenv("LUMINA_ADMIN_API_KEY_PREVIOUS", "") or "").strip()
    if not prev or not grace_active():
        return None
    return {
        "name": "previous_admin_api_key",
        "role": "admin",
        "enabled": True,
        "grace": True,
    }


def verify_with_grace(key: str, primary_lookup: Any) -> dict[str, Any] | None:
    """Try primary verifier, then previous key during grace."""
    meta = primary_lookup(key)
    if meta is not None:
        return meta
    prev = str(os.getenv("LUMINA_ADMIN_API_KEY_PREVIOUS", "") or "").strip()
    if prev and key == prev and grace_active():
        return previous_key_meta()
    return None


def rotate_admin_api_key(
    *,
    config_manager: Any | None = None,
    env_path: Path | None = None,
    grace_hours: float = DEFAULT_GRACE_HOURS,
    workspace_root: Path | None = None,
) -> RotationResult:
    """Generate new admin key, demote current to PREVIOUS, set grace window.

    Writes .env when config_manager or env_path provided. Updates process env immediately.
    """
    old = str(os.getenv("LUMINA_ADMIN_API_KEY", "") or "").strip()
    new_key = f"sk_{secrets.token_hex(32)}"
    grace_until = time.time() + max(1.0, float(grace_hours)) * 3600.0

    os.environ["LUMINA_ADMIN_API_KEY"] = new_key
    if old:
        os.environ["LUMINA_ADMIN_API_KEY_PREVIOUS"] = old
    os.environ["LUMINA_API_KEY_GRACE_UNTIL"] = str(int(grace_until))

    updates = {
        "LUMINA_ADMIN_API_KEY": new_key,
        "LUMINA_API_KEY_GRACE_UNTIL": str(int(grace_until)),
    }
    if old:
        updates["LUMINA_ADMIN_API_KEY_PREVIOUS"] = old

    written = ""
    if config_manager is not None:
        config_manager.write_env_file(updates)
        written = str(getattr(config_manager, "env_path", "") or "")
    elif env_path is not None:
        # Minimal merge write
        existing: dict[str, str] = {}
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()
        existing.update(updates)
        content = "\n".join(f"{k}={v}" for k, v in sorted(existing.items())) + "\n"
        env_path.write_text(content, encoding="utf-8")
        written = str(env_path)

    # Audit
    try:
        from lumina_core.cyber_sentinel import _append_audit

        _append_audit(
            workspace_root,
            {
                "kind": "api_key_rotation",
                "grace_until_unix": grace_until,
                "had_previous": bool(old),
            },
        )
    except Exception:
        pass

    logger.warning(
        "admin API key rotated grace_until=%s previous_retained=%s",
        int(grace_until),
        bool(old),
    )
    return RotationResult(
        new_key=new_key,
        previous_key=old,
        grace_until_unix=grace_until,
        env_path=written,
    )
