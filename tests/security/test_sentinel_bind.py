"""Sentinel network bind hard veto (ADR-0040)."""

from __future__ import annotations

import pytest

from lumina_core.cyber_sentinel import evaluate_api_bind, is_loopback_host, resolve_api_bind_host


def test_loopback_allowed() -> None:
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("::1")
    assert evaluate_api_bind("127.0.0.1") is None


def test_non_loopback_veto_without_hardening(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "LUMINA_ALLOW_NON_LOOPBACK",
        "LUMINA_MTLS_ENABLED",
        "LUMINA_IP_ALLOWLIST",
        "LUMINA_SENTINEL_ACTIVE",
    ):
        monkeypatch.delenv(key, raising=False)
    veto = evaluate_api_bind("0.0.0.0")
    assert veto is not None
    assert veto.code == "NON_LOOPBACK_FORBIDDEN"
    assert veto.hard is True


def test_non_loopback_allowed_with_full_hardening(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_ALLOW_NON_LOOPBACK", "true")
    monkeypatch.setenv("LUMINA_MTLS_ENABLED", "true")
    monkeypatch.setenv("LUMINA_IP_ALLOWLIST", "10.0.0.0/8")
    monkeypatch.setenv("LUMINA_SENTINEL_ACTIVE", "true")
    assert evaluate_api_bind("0.0.0.0") is None


def test_resolve_api_bind_defaults_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUMINA_API_BIND", raising=False)
    assert resolve_api_bind_host() == "127.0.0.1"


def test_resolve_api_bind_raises_on_naked_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_API_BIND", "0.0.0.0")
    for key in (
        "LUMINA_ALLOW_NON_LOOPBACK",
        "LUMINA_MTLS_ENABLED",
        "LUMINA_IP_ALLOWLIST",
        "LUMINA_SENTINEL_ACTIVE",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="Non-loopback"):
        resolve_api_bind_host()
