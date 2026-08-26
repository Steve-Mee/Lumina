"""Sentinel operator endpoints — status / clear containment (admin, no trade path)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.app_auth import verify_admin_role, verify_api_key

router = APIRouter(prefix="/api/sentinel", tags=["sentinel"])


def _workspace() -> Path:
    return Path(os.getenv("LUMINA_WORKSPACE") or Path(__file__).resolve().parents[2])


@router.get("/status")
async def sentinel_status(
    _auth: dict[str, Any] = Depends(verify_api_key),
) -> dict[str, Any]:
    """Sentinel windows + containment (no secrets)."""
    from lumina_core.cyber_sentinel import status_snapshot
    from lumina_core.sentinel_agent import get_sentinel_agent

    root = _workspace()
    agent = get_sentinel_agent(workspace_root=root)
    snap = status_snapshot(root)
    snap["agent"] = agent.last_status or agent.tick()
    return snap


class ClearContainmentBody(BaseModel):
    reason: str = Field(default="operator_clear", max_length=200)
    confirm: bool = False


@router.post("/containment/clear")
async def clear_sentinel_containment(
    body: ClearContainmentBody,
    _admin: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    """Admin-only clear of network/token containment. Never auto-cleared by Twin."""
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm=true required to clear containment",
        )
    from lumina_core.cyber_sentinel import clear_containment, is_containment_active, read_containment

    root = _workspace()
    before = read_containment(root)
    clear_containment(reason=body.reason, workspace_root=root)
    return {
        "ok": True,
        "was_active": before.active,
        "previous_code": before.code,
        "active": is_containment_active(root),
    }


@router.get("/health")
async def sentinel_health(
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    """Lightweight health: loopback free shape via status without secrets."""
    from lumina_core.cyber_sentinel import is_containment_active, is_sentinel_active

    return {
        "sentinel_env_flag": is_sentinel_active(),
        "containment_active": is_containment_active(_workspace()),
        "domain": "network_token_only",
    }


class RotateKeyBody(BaseModel):
    grace_hours: float = Field(default=24.0, ge=1.0, le=168.0)
    confirm: bool = False


@router.post("/rotate-admin-key")
async def rotate_admin_api_key(
    body: RotateKeyBody,
    _admin: dict[str, Any] = Depends(verify_admin_role),
) -> dict[str, Any]:
    """Admin-only API key rotation with dual-key grace (ADR-0042).

    Returns the new key once — store immediately. Previous key remains valid
    until grace expires or PREVIOUS is cleared from env.
    """
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")
    from lumina_core.api_key_rotation import rotate_admin_api_key as do_rotate
    from lumina_launcher.core.config_manager import ConfigManager

    root = _workspace()
    env_path = root / ".env"
    cm = ConfigManager(env_path=env_path, config_path=root / "config.yaml")
    result = do_rotate(
        config_manager=cm,
        grace_hours=float(body.grace_hours),
        workspace_root=root,
    )
    # Hot-reload process SECURITY map so new key works without restart.
    try:
        from backend.app_auth import _sec

        sec = _sec()
        cfg = sec.get("config")
        if cfg is not None and hasattr(cfg, "api_keys"):
            cfg.api_keys[result.new_key] = {
                "name": "rotated_admin_api_key",
                "role": "admin",
                "enabled": True,
            }
            if result.previous_key:
                cfg.api_keys.setdefault(
                    result.previous_key,
                    {
                        "name": "previous_admin_api_key",
                        "role": "admin",
                        "enabled": True,
                        "grace": True,
                    },
                )
    except Exception:
        pass
    return {
        "ok": True,
        "new_key": result.new_key,
        "grace_until_unix": result.grace_until_unix,
        "previous_retained": bool(result.previous_key),
        "env_path": result.env_path,
        "note": "Store new_key now; previous key valid during grace only",
    }
