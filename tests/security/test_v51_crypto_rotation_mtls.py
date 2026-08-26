"""v51 foundations: crypto-at-rest, API key rotation grace, mTLS config."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest


def test_crypto_roundtrip_with_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from lumina_core.crypto_at_rest import (
        decrypt_text,
        encrypt_text,
        generate_key,
        read_json_secure,
        write_json_secure,
    )

    key = generate_key()
    monkeypatch.setenv("LUMINA_STATE_ENCRYPTION_KEY", key)
    cipher = encrypt_text("hello-secret")
    assert cipher.startswith("LUMINA1:")
    assert decrypt_text(cipher) == "hello-secret"
    path = tmp_path / "blob.json"
    write_json_secure(path, {"a": 1, "b": "x"})
    raw = path.read_text(encoding="utf-8")
    assert raw.startswith("LUMINA1:")
    assert read_json_secure(path) == {"a": 1, "b": "x"}


def test_crypto_plaintext_without_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from lumina_core.crypto_at_rest import encrypt_text, write_json_secure, read_json_secure

    monkeypatch.delenv("LUMINA_STATE_ENCRYPTION_KEY", raising=False)
    assert encrypt_text("plain") == "plain"
    path = tmp_path / "p.json"
    write_json_secure(path, {"ok": True})
    assert "ok" in path.read_text(encoding="utf-8")
    assert read_json_secure(path) == {"ok": True}


def test_api_key_rotation_grace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from lumina_core.api_key_rotation import grace_active, rotate_admin_api_key, verify_with_grace
    from lumina_core.security import APIKeyAuthenticator, SecurityConfig

    env = tmp_path / ".env"
    env.write_text("LUMINA_ADMIN_API_KEY=sk_oldkey\n", encoding="utf-8")
    monkeypatch.setenv("LUMINA_ADMIN_API_KEY", "sk_oldkey")
    monkeypatch.delenv("LUMINA_ADMIN_API_KEY_PREVIOUS", raising=False)
    monkeypatch.delenv("LUMINA_API_KEY_GRACE_UNTIL", raising=False)

    result = rotate_admin_api_key(env_path=env, grace_hours=2.0, workspace_root=tmp_path)
    assert result.new_key.startswith("sk_")
    assert result.previous_key == "sk_oldkey"
    assert grace_active()
    assert os.getenv("LUMINA_ADMIN_API_KEY") == result.new_key
    assert os.getenv("LUMINA_ADMIN_API_KEY_PREVIOUS") == "sk_oldkey"

    # Authenticator accepts previous during grace.
    monkeypatch.setenv("LUMINA_JWT_SECRET_KEY", "x" * 40)
    cfg = SecurityConfig({"jwt_secret_key": "x" * 40, "api_keys": {}, "cors_allowed_origins": []})
    cfg.api_keys[result.new_key] = {"name": "admin", "role": "admin", "enabled": True}
    # Hot-reload style previous entry must still respect grace flag.
    cfg.api_keys["sk_oldkey"] = {
        "name": "previous_admin_api_key",
        "role": "admin",
        "enabled": True,
        "grace": True,
    }
    auth = APIKeyAuthenticator(cfg)
    assert auth.verify_api_key(result.new_key) is not None
    assert auth.verify_api_key("sk_oldkey") is not None
    assert auth.verify_api_key("sk_wrong") is None

    # Expired grace → previous rejected even if still in api_keys map.
    monkeypatch.setenv("LUMINA_API_KEY_GRACE_UNTIL", str(int(time.time()) - 10))
    assert not grace_active()
    assert auth.verify_api_key("sk_oldkey") is None

    def primary(k: str):
        return {"name": "p"} if k == result.new_key else None

    monkeypatch.setenv("LUMINA_API_KEY_GRACE_UNTIL", str(int(time.time()) + 3600))
    assert verify_with_grace("sk_oldkey", primary) is not None


def test_mtls_not_configured() -> None:
    from lumina_core.mtls_config import fabric_tls_configured, load_fabric_tls_material

    # Default env: no CA
    if not fabric_tls_configured():
        assert load_fabric_tls_material() is None


def test_mtls_requires_ca_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from lumina_core.mtls_config import load_fabric_tls_material

    monkeypatch.setenv("LUMINA_FABRIC_TLS_CA", str(tmp_path / "missing.pem"))
    with pytest.raises(RuntimeError, match="not found"):
        load_fabric_tls_material()


def test_mtls_loads_ca_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from lumina_core.mtls_config import load_fabric_tls_material

    ca = tmp_path / "ca.pem"
    ca.write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n", encoding="utf-8")
    monkeypatch.setenv("LUMINA_FABRIC_TLS_CA", str(ca))
    monkeypatch.delenv("LUMINA_FABRIC_TLS_CERT", raising=False)
    monkeypatch.delenv("LUMINA_FABRIC_TLS_KEY", raising=False)
    mat = load_fabric_tls_material()
    assert mat is not None
    assert mat.mutual is False
    assert mat.ca_cert_path == ca


def test_containment_encrypted_when_key_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from lumina_core.crypto_at_rest import generate_key
    from lumina_core.cyber_sentinel import (
        activate_containment,
        clear_containment,
        is_containment_active,
        read_containment,
    )

    key = generate_key()
    monkeypatch.setenv("LUMINA_STATE_ENCRYPTION_KEY", key)
    monkeypatch.setenv("LUMINA_WORKSPACE", str(tmp_path))
    clear_containment(workspace_root=tmp_path)
    activate_containment(reason="enc-test", code="ENC", workspace_root=tmp_path)
    path = tmp_path / "state" / "sentinel_containment.json"
    assert path.is_file()
    assert path.read_text(encoding="utf-8").startswith("LUMINA1:")
    assert is_containment_active(tmp_path)
    assert read_containment(tmp_path).code == "ENC"
    clear_containment(workspace_root=tmp_path)


def test_grace_off_without_until(monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.api_key_rotation import grace_active

    monkeypatch.setenv("LUMINA_ADMIN_API_KEY_PREVIOUS", "sk_x")
    monkeypatch.delenv("LUMINA_API_KEY_GRACE_UNTIL", raising=False)
    assert grace_active() is False


def test_resolve_request_client_host_xff_requires_trust() -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from lumina_os.backend.sentinel_middleware import resolve_request_client_host

    req = MagicMock()
    req.client = SimpleNamespace(host="127.0.0.1")
    req.headers = {"x-forwarded-for": "203.0.113.9"}
    # Without trust: ignore XFF
    os.environ.pop("LUMINA_TRUST_PROXY", None)
    assert resolve_request_client_host(req) == "127.0.0.1"
    os.environ["LUMINA_TRUST_PROXY"] = "true"
    assert resolve_request_client_host(req) == "203.0.113.9"
    os.environ.pop("LUMINA_TRUST_PROXY", None)
