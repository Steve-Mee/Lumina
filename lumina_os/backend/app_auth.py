"""API key / admin / rate-limit FastAPI dependencies."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, Header, HTTPException

_SECURITY: dict[str, Any] | None = None


def configure_app_security(security: dict[str, Any]) -> None:
    global _SECURITY
    _SECURITY = security


def _sec() -> dict[str, Any]:
    if _SECURITY is None:
        raise RuntimeError("app_auth.configure_app_security not called")
    return _SECURITY


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> dict[str, Any]:
    """Dependency to verify API key authentication."""
    security = _sec()
    if not x_api_key:
        security["audit_log"].log_auth_attempt("unknown", False, "api_key")
        try:
            from lumina_core.cyber_sentinel import observe_auth_failure

            observe_auth_failure(principal="unknown", reason="missing_api_key")
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="API key required")

    key_meta = security["api_key"].verify_api_key(x_api_key)
    if not key_meta:
        security["audit_log"].log_auth_attempt("unknown", False, "api_key")
        try:
            from lumina_core.cyber_sentinel import observe_auth_failure

            observe_auth_failure(principal="unknown", reason="invalid_api_key")
        except Exception:
            pass
        raise HTTPException(status_code=401, detail="Invalid API key")

    security["audit_log"].log_auth_attempt(key_meta.get("name", "api_key"), True, "api_key")
    return {"api_key": x_api_key, "metadata": key_meta}


async def verify_admin_role(auth: dict[str, Any] = Depends(verify_api_key)) -> dict[str, Any]:
    """Dependency to verify admin role for destructive operations."""
    security = _sec()
    if not security["config"].admin_role_required:
        return auth

    role = auth["metadata"].get("role", "user")
    if role != "admin":
        security["audit_log"].log_unauthorized_access(
            auth["metadata"].get("name", "unknown"),
            "admin_operation",
            f"insufficient_role_{role}",
        )
        raise HTTPException(status_code=403, detail="Admin role required")

    return auth


async def check_rate_limit(x_api_key: Optional[str] = Header(None)) -> None:
    """Dependency to check rate limiting."""
    security = _sec()
    client_id = x_api_key or "anonymous"
    if not security["rate_limiter"].is_allowed(client_id):
        try:
            from lumina_core.cyber_sentinel import observe_rate_limit

            observe_rate_limit(client_id=str(client_id)[:64])
        except Exception:
            pass
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
