"""
Security module tests - Authentication bypass, CORS violations, rate limiting.
Run: pytest tests/test_security.py -v
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch

from lumina_core.security import (
    SecurityConfig,
    TokenPayload,
    JWTAuthenticator,
    APIKeyAuthenticator,
    RateLimiter,
    SecurityAuditLog,
    DangerousConfigValidator,
)


class TestSecurityConfig:
    """Test security configuration loading and validation."""

    def test_cors_wildcard_rejected(self):
        """CORS wildcard '*' should be rejected."""
        config_dict = {"cors_allowed_origins": ["*"]}
        with pytest.raises(ValueError, match="CORS wildcard.*not allowed"):
            SecurityConfig(config_dict)

    def test_cors_explicit_origins_accepted(self):
        """Explicit CORS origins should be accepted."""
        config_dict = {
            "cors_allowed_origins": ["http://localhost:3000", "https://example.com"],
            "jwt_secret_key": "x" * 32,
        }
        config = SecurityConfig(config_dict)
        assert config.cors_allowed_origins == [
            "http://localhost:3000",
            "https://example.com",
        ]

    def test_jwt_secret_key_required(self):
        """JWT secret key is required."""
        config_dict = {"cors_allowed_origins": []}
        with pytest.raises(ValueError, match="JWT secret key"):
            SecurityConfig(config_dict)

    def test_jwt_secret_key_minimum_length(self):
        """JWT secret key must be at least 32 characters."""
        config_dict = {
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "short",
        }
        with pytest.raises(ValueError, match="at least 32 characters"):
            SecurityConfig(config_dict)

    def test_valid_configuration(self):
        """Valid configuration should initialize without errors."""
        config_dict = {
            "cors_allowed_origins": ["http://localhost:3000"],
            "jwt_secret_key": "x" * 32,
            "rate_limit_enabled": True,
            "rate_limit_requests_per_minute": 60,
        }
        config = SecurityConfig(config_dict)
        assert config.rate_limit_enabled is True
        assert config.rate_limit_requests_per_minute == 60


class TestTokenPayload:
    """Test JWT token payload."""

    def test_token_payload_serialization(self):
        """Token payload should serialize to dict."""
        payload = TokenPayload(
            user_id="user123",
            username="alice",
            role="admin",
            exp=1234567890,
        )
        data = payload.to_dict()
        assert data["user_id"] == "user123"
        assert data["username"] == "alice"
        assert data["role"] == "admin"
        assert data["exp"] == 1234567890

    def test_token_payload_deserialization(self):
        """Token payload should deserialize from dict."""
        data = {
            "user_id": "user456",
            "username": "bob",
            "role": "user",
            "exp": 9876543210,
        }
        payload = TokenPayload.from_dict(data)
        assert payload.user_id == "user456"
        assert payload.username == "bob"
        assert payload.role == "user"


class TestJWTAuthenticator:
    """Test JWT authentication."""

    @pytest.fixture
    def auth(self):
        config = SecurityConfig({
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "x" * 32,
        })
        return JWTAuthenticator(config)

    def test_create_and_verify_token(self, auth):
        """Creating and verifying a token should work."""
        payload = TokenPayload(
            user_id="user789",
            username="charlie",
            role="admin",
        )
        token = auth.create_token(payload)
        assert isinstance(token, str)
        assert len(token) > 0

        # Verify the token
        verified = auth.verify_token(token)
        assert verified is not None
        assert verified.user_id == "user789"
        assert verified.username == "charlie"
        assert verified.role == "admin"

    def test_invalid_token_verification(self, auth):
        """Invalid tokens should fail verification."""
        result = auth.verify_token("invalid.token.here")
        assert result is None

    def test_tampered_token_verification(self, auth):
        """Tampered tokens should fail verification."""
        payload = TokenPayload(
            user_id="user999",
            username="dave",
            role="user",
        )
        token = auth.create_token(payload)
        # Tamper with the token
        tampered = token[:-10] + "0000000000"
        result = auth.verify_token(tampered)
        assert result is None


class TestAPIKeyAuthenticator:
    """Test API key authentication."""

    @pytest.fixture
    def auth(self):
        config_dict = {
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "x" * 32,
            "api_keys": {
                "sk_valid_key": {
                    "name": "Test API Key",
                    "role": "admin",
                    "enabled": True,
                },
                "sk_disabled_key": {
                    "name": "Disabled Key",
                    "role": "user",
                    "enabled": False,
                },
            },
        }
        config = SecurityConfig(config_dict)
        return APIKeyAuthenticator(config)

    def test_valid_api_key(self, auth):
        """Valid API key should be accepted."""
        result = auth.verify_api_key("sk_valid_key")
        assert result is not None
        assert result["name"] == "Test API Key"
        assert result["role"] == "admin"

    def test_invalid_api_key(self, auth):
        """Invalid API key should be rejected."""
        result = auth.verify_api_key("sk_invalid_key")
        assert result is None

    def test_disabled_api_key(self, auth):
        """Disabled API key should be rejected."""
        result = auth.verify_api_key("sk_disabled_key")
        assert result is None

    def test_generate_api_key(self, auth):
        """Generating API key should produce valid format."""
        key = auth.generate_api_key("test_key", "user")
        assert key.startswith("sk_")
        assert len(key) > 10


class TestRateLimiter:
    """Test rate limiting."""

    @pytest.fixture
    def rate_limiter(self):
        config = SecurityConfig({
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "x" * 32,
            "rate_limit_enabled": True,
            "rate_limit_requests_per_minute": 60,
            "rate_limit_burst_size": 10,
        })
        return RateLimiter(config)

    def test_rate_limiting_disabled(self):
        """Disabled rate limiting should always allow."""
        config = SecurityConfig({
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "x" * 32,
            "rate_limit_enabled": False,
        })
        limiter = RateLimiter(config)
        for _ in range(100):
            assert limiter.is_allowed("client1") is True

    def test_rate_limiting_allows_within_burst(self, rate_limiter):
        """Requests within burst size should be allowed."""
        client_id = "test_client"
        for _ in range(10):
            assert rate_limiter.is_allowed(client_id) is True

    def test_rate_limiting_enforces_burst(self, rate_limiter):
        """Requests exceeding burst should be denied."""
        client_id = "test_client"
        # Use up burst
        for _ in range(10):
            rate_limiter.is_allowed(client_id)
        # Next request should fail
        assert rate_limiter.is_allowed(client_id) is False

    def test_rate_limiting_per_client(self, rate_limiter):
        """Rate limiting should track per client."""
        # Client 1 uses burst
        for _ in range(10):
            rate_limiter.is_allowed("client_a")
        # Client 1 is rate-limited
        assert rate_limiter.is_allowed("client_a") is False
        # Client 2 should still be allowed
        assert rate_limiter.is_allowed("client_b") is True


class TestSecurityAuditLog:
    """Test security audit logging."""

    @pytest.fixture
    def audit_log(self, tmp_path):
        config = SecurityConfig({
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "x" * 32,
            "audit_log_enabled": True,
            "audit_log_path": str(tmp_path / "audit.jsonl"),
        })
        return SecurityAuditLog(config)

    def test_audit_log_action(self, audit_log, tmp_path):
        """Audit log should record actions."""
        audit_log.log_action(
            action="test_action",
            user_id="user123",
            username="alice",
            resource="test_resource",
            status="success",
            details={"test": "data"},
        )

        # Read the log file
        log_file = tmp_path / "audit.jsonl"
        assert log_file.exists()
        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["action"] == "test_action"
        assert entry["user_id"] == "user123"
        assert entry["username"] == "alice"
        assert entry["status"] == "success"

    def test_audit_log_auth_attempt(self, audit_log, tmp_path):
        """Audit log should record auth attempts."""
        audit_log.log_auth_attempt("bob", True, "api_key")

        log_file = tmp_path / "audit.jsonl"
        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["action"] == "auth_attempt"
        assert entry["username"] == "bob"
        assert entry["status"] == "success"
        assert entry["details"]["method"] == "api_key"


class TestDangerousConfigValidator:
    """Test dangerous configuration detection."""

    def test_detects_cors_wildcard(self):
        """Validator should detect CORS wildcard."""
        config = SecurityConfig({
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "x" * 32,
            "dangerous_configs": {
                "cors_allowed_origins": ["*"],
            },
        })
        validator = DangerousConfigValidator(config)
        violations = validator.validate({"cors_allowed_origins": ["*"]})
        assert len(violations) > 0
        assert any("CORS" in v for v in violations)

    def test_detects_weak_jwt_secret(self):
        """Validator should detect weak JWT secret."""
        config = SecurityConfig({
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "x" * 32,
            "dangerous_configs": {
                "jwt_secret_key": ["default", "secret", "12345678"],
            },
        })
        validator = DangerousConfigValidator(config)
        violations = validator.validate({"jwt_secret_key": "default"})
        assert len(violations) > 0
        assert any("JWT" in v for v in violations)

    def test_accepts_safe_config(self):
        """Validator should accept safe configuration."""
        config = SecurityConfig({
            "cors_allowed_origins": ["http://localhost"],
            "jwt_secret_key": "x" * 32,
            "dangerous_configs": {
                "cors_allowed_origins": ["*"],
            },
        })
        validator = DangerousConfigValidator(config)
        violations = validator.validate({
            "cors_allowed_origins": ["http://localhost:3000"],
            "jwt_secret_key": "y" * 32,
        })
        assert len(violations) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
