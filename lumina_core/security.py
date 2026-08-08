"""
Lumina v50 Security Module - Production-grade authentication, authorization, rate limiting, and audit logging.
Fail-closed design: all security failures default to denial of access.
"""

import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

import jwt
from typing_extensions import ParamSpec
from lumina_core.audit import get_audit_logger

logger = logging.getLogger(__name__)

P = ParamSpec("P")

_ENV_PLACEHOLDER = re.compile(r"^\$\{([^}]+)\}$")


def _expand_env_placeholder(value: Any) -> str:
    """If value is ``${VAR_NAME}``, return ``os.environ[VAR_NAME]`` (or '')."""
    if value is None:
        return ""
    s = str(value).strip()
    m = _ENV_PLACEHOLDER.match(s)
    if m:
        return os.getenv(m.group(1).strip(), "")
    return s


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

        # JWT settings (config may use ${VAR} — yaml does not expand env vars)
        key_from_yaml = _expand_env_placeholder(self.config.get("jwt_secret_key"))
        if use_env_fallback:
            self.jwt_secret_key = os.getenv("LUMINA_JWT_SECRET_KEY") or key_from_yaml
        else:
            self.jwt_secret_key = key_from_yaml or os.getenv("LUMINA_JWT_SECRET_KEY", "")
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
        raw_api_keys = self.config.get("api_keys", {})
        if not isinstance(raw_api_keys, dict):
            raw_api_keys = {}
        self.api_keys: dict[str, dict[str, Any]] = {}
        for key, meta in raw_api_keys.items():
            resolved_key = _expand_env_placeholder(key)
            if not resolved_key:
                continue
            self.api_keys[str(resolved_key)] = dict(meta) if isinstance(meta, dict) else {}

        env_admin_key = str(os.getenv("LUMINA_ADMIN_API_KEY", "")).strip()
        if env_admin_key:
            self.api_keys.setdefault(
                env_admin_key,
                {
                    "name": "env_admin_api_key",
                    "role": "admin",
                    "enabled": True,
                },
            )

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
            f"AuditLog={self.audit_log_enabled}, "
            f"APIKeys={len(self.api_keys)}"
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

from lumina_core.security_audit import (  # noqa: F401
    DangerousConfigValidator,
    RateLimiter,
    SecurityAuditLog,
    get_security_module,
    require_auth,
)
