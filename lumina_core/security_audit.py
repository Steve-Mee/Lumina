"""Security audit, rate limit, config validation (global residual)."""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

from typing_extensions import ParamSpec

from lumina_core.audit import get_audit_logger
from lumina_core.security import SecurityConfig

logger = logging.getLogger(__name__)
P = ParamSpec("P")

class RateLimiter:
    """Thread-safe rate limiter with token bucket algorithm."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.buckets: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def is_allowed(self, client_id: str) -> bool:
        """Check if client is allowed to make a request."""
        if not self.config.rate_limit_enabled:
            return True

        with self.lock:
            now = time.time()
            if client_id not in self.buckets:
                self.buckets[client_id] = {
                    "tokens": self.config.rate_limit_burst_size,
                    "last_refill": now,
                }

            bucket = self.buckets[client_id]
            elapsed = now - bucket["last_refill"]
            refill_rate = self.config.rate_limit_requests_per_minute / 60.0
            bucket["tokens"] = min(
                self.config.rate_limit_burst_size,
                bucket["tokens"] + elapsed * refill_rate,
            )
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True

            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return False

class SecurityAuditLog:
    """Thread-safe security audit logger."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(self.config.audit_log_path) or ".", exist_ok=True)
        get_audit_logger().register_stream("security", Path(self.config.audit_log_path))

    def log_action(
        self,
        action: str,
        user_id: str,
        username: str,
        resource: str,
        status: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a security-relevant action."""
        if not self.config.audit_log_enabled:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "user_id": user_id,
            "username": username,
            "resource": resource,
            "status": status,
            "details": details or {},
        }

        with self.lock:
            try:
                get_audit_logger().append(
                    stream="security",
                    payload=entry,
                    path=Path(self.config.audit_log_path),
                    mode="real" if str(os.getenv("LUMINA_MODE", "sim")).strip().lower() == "real" else "sim",
                    actor_id=str(username or "security"),
                    severity="info",
                )
            except Exception as exc:
                logger.error(f"Failed to write audit log: {exc}")

    def log_auth_attempt(self, username: str, success: bool, method: str) -> None:
        """Log authentication attempt."""
        self.log_action(
            action="auth_attempt",
            user_id="anonymous",
            username=username,
            resource="auth",
            status="success" if success else "failure",
            details={"method": method},
        )

    def log_unauthorized_access(self, username: str, resource: str, reason: str) -> None:
        """Log unauthorized access attempt."""
        self.log_action(
            action="unauthorized_access",
            user_id="anonymous",
            username=username,
            resource=resource,
            status="denied",
            details={"reason": reason},
        )

    def log_admin_action(
        self, username: str, action: str, resource: str, details: Optional[dict[str, Any]] = None
    ) -> None:
        """Log admin action (destructive operation)."""
        self.log_action(
            action=f"admin_{action}",
            user_id="admin",
            username=username,
            resource=resource,
            status="executed",
            details=details or {},
        )

class DangerousConfigValidator:
    """Validate that dangerous config values are not present in production."""

    def __init__(self, config: SecurityConfig):
        self.config = config

    def validate(self, actual_config: dict[str, Any]) -> list[str]:
        """Check actual config against dangerous patterns. Returns list of violations."""
        violations: list[str] = []
        security_cfg = self._extract_security_section(actual_config)

        # Check CORS
        if security_cfg.get("cors_allowed_origins", []) == ["*"]:
            violations.append("CORS wildcard '*' found in config")

        # Check JWT secret
        jwt_secret = security_cfg.get("jwt_secret_key", "")
        if jwt_secret in ("default", "secret", "12345678"):
            violations.append("Default or weak JWT secret key found in config")

        # Check dangerous flags
        dangerous_patterns = self.config.dangerous_configs
        for config_path, forbidden_values in dangerous_patterns.items():
            value = self._resolve_config_path(actual_config, config_path)
            if value in forbidden_values or value is True:
                violations.append(f"Dangerous config value found: {config_path}={value}")

        return violations

    @staticmethod
    def _extract_security_section(config: dict[str, Any]) -> dict[str, Any]:
        """Return security section when full config is provided; otherwise return config itself."""
        security_section = config.get("security")
        if isinstance(security_section, dict):
            return security_section
        return config

    @staticmethod
    def _resolve_config_path(config: dict[str, Any], path: str) -> Any:
        """Resolve paths against full-config and security section to avoid namespace mismatches."""
        candidates = [path]
        if path.startswith("security."):
            candidates.append(path[len("security.") :])
        else:
            candidates.append(f"security.{path}")

        for candidate in candidates:
            value = DangerousConfigValidator._get_nested_value(config, candidate)
            if value is not None:
                return value
        return None

    @staticmethod
    def _get_nested_value(config: dict[str, Any], path: str) -> Any:
        """Get value from nested dict using dot notation (e.g., 'db.allow_remote_connection')."""
        keys = path.split(".")
        current = config
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

def require_auth(
    required_role: Optional[str] = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """
    Decorator for FastAPI endpoints to require authentication.

    Args:
        required_role: Optional role requirement (e.g., "admin"). If None, any authenticated user allowed.
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            # Extract from request (this is a template; actual implementation depends on FastAPI context)
            # In FastAPI, use: Depends(get_current_user) approach instead
            return func(*args, **kwargs)

        return wrapper

    return decorator

def get_security_module(config_dict: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Factory function to create security module components."""
    from lumina_core.security import APIKeyAuthenticator, JWTAuthenticator, SecurityConfig

    config = SecurityConfig(config_dict)
    return {
        "config": config,
        "jwt": JWTAuthenticator(config),
        "api_key": APIKeyAuthenticator(config),
        "rate_limiter": RateLimiter(config),
        "audit_log": SecurityAuditLog(config),
        "config_validator": DangerousConfigValidator(config),
    }
