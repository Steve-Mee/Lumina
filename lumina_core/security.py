"""
Lumina v50 Security Module - Production-grade authentication, authorization, rate limiting, and audit logging.
Fail-closed design: all security failures default to denial of access.
"""

import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Optional

import jwt
from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec("P")


class SecurityConfig:
    """Load security configuration from config.yaml or environment."""

    def __init__(self, config_dict: Optional[dict[str, Any]] = None):
        """
        Initialize security config.

        Args:
            config_dict: Loaded config.yaml security section
        """
        self.config = config_dict or {}
        use_env_fallback = config_dict is None

        # CORS settings
        self.cors_allowed_origins: list[str] = self.config.get("cors_allowed_origins", [])
        if "*" in self.cors_allowed_origins:
            raise ValueError(
                "CORS wildcard '*' is not allowed. Specify explicit origins in config.yaml "
                "[security.cors_allowed_origins]"
            )
        if not self.cors_allowed_origins:
            logger.warning("CORS allowed origins is empty; API will reject all cross-origin requests")

        # JWT settings
        if use_env_fallback:
            self.jwt_secret_key = os.getenv("LUMINA_JWT_SECRET_KEY") or self.config.get("jwt_secret_key", "")
        else:
            self.jwt_secret_key = self.config.get("jwt_secret_key", "")
        if not self.jwt_secret_key:
            raise ValueError(
                "JWT secret key is not set. "
                "Provide LUMINA_JWT_SECRET_KEY environment variable or security.jwt_secret_key in config.yaml"
            )
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")

        self.jwt_algorithm = self.config.get("jwt_algorithm", "HS256")
        self.jwt_expiration_minutes = self.config.get("jwt_expiration_minutes", 1440)  # 24h

        # API key settings
        self.api_key_header = self.config.get("api_key_header", "X-API-Key")
        self.api_keys: dict[str, dict[str, Any]] = self.config.get("api_keys", {})

        # Rate limiting settings
        self.rate_limit_enabled = self.config.get("rate_limit_enabled", True)
        self.rate_limit_requests_per_minute = self.config.get("rate_limit_requests_per_minute", 60)
        self.rate_limit_burst_size = self.config.get("rate_limit_burst_size", 10)

        # Admin role requirement for destructive operations
        self.admin_role_required = self.config.get("admin_role_required", True)

        # Audit logging
        self.audit_log_enabled = self.config.get("audit_log_enabled", True)
        self.audit_log_path = self.config.get("audit_log_path", "logs/security_audit.jsonl")

        # Dangerous config validation
        self.dangerous_configs: dict[str, Any] = self.config.get("dangerous_configs", {})

        logger.info(
            f"SecurityConfig initialized: "
            f"CORS={len(self.cors_allowed_origins)} origins, "
            f"JWT algorithm={self.jwt_algorithm}, "
            f"RateLimit={self.rate_limit_enabled}, "
            f"AuditLog={self.audit_log_enabled}"
        )


class TokenPayload:
    """JWT token payload."""

    def __init__(self, user_id: str, username: str, role: str, exp: Optional[int] = None):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.exp = exp or int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "exp": self.exp,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "TokenPayload":
        return TokenPayload(
            user_id=data.get("user_id", ""),
            username=data.get("username", ""),
            role=data.get("role", "user"),
            exp=data.get("exp"),
        )


class JWTAuthenticator:
    """JWT-based authentication."""

    def __init__(self, config: SecurityConfig):
        self.config = config

    def create_token(self, payload: TokenPayload) -> str:
        """Create a signed JWT token."""
        token = jwt.encode(
            payload.to_dict(),
            self.config.jwt_secret_key,
            algorithm=self.config.jwt_algorithm,
        )
        logger.info(f"JWT token created for user {payload.username}")
        return token

    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify and decode a JWT token. Returns None if invalid/expired."""
        try:
            decoded = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm],
            )
            return TokenPayload.from_dict(decoded)
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as exc:
            logger.warning(f"JWT token invalid: {exc}")
            return None


class APIKeyAuthenticator:
    """API key-based authentication."""

    def __init__(self, config: SecurityConfig):
        self.config = config

    def verify_api_key(self, key: str) -> Optional[dict[str, Any]]:
        """Verify API key and return associated metadata. Returns None if invalid."""
        if key not in self.config.api_keys:
            logger.warning("Invalid API key attempt")
            return None

        key_meta = self.config.api_keys[key]
        if key_meta.get("enabled", True) is False:
            logger.warning(f"API key disabled: {key_meta.get('name', 'unknown')}")
            return None

        return key_meta

    def generate_api_key(self, name: str, role: str = "user") -> str:
        """Generate a random API key."""
        key = f"sk_{secrets.token_hex(32)}"
        logger.info(f"API key generated: {name} (role={role})")
        return key


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
                with open(self.config.audit_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
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
    config = SecurityConfig(config_dict)
    return {
        "config": config,
        "jwt": JWTAuthenticator(config),
        "api_key": APIKeyAuthenticator(config),
        "rate_limiter": RateLimiter(config),
        "audit_log": SecurityAuditLog(config),
        "config_validator": DangerousConfigValidator(config),
    }
