from __future__ import annotations

import pytest

from lumina_core.config_loader import ConfigLoader


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "unit-test-xai-key")
    monkeypatch.setenv("LUMINA_JWT_SECRET_KEY", "unit-test-jwt-secret")


def test_validate_startup_rejects_paper_with_live_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setattr(ConfigLoader, "get", classmethod(lambda cls: {"mode": "paper", "broker": {"backend": "live"}}))

    with pytest.raises(RuntimeError, match="trade_mode=paper requires broker_backend=paper"):
        ConfigLoader.validate_startup(raise_on_error=True)


def test_validate_startup_rejects_sim_with_paper_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setattr(ConfigLoader, "get", classmethod(lambda cls: {"mode": "sim", "broker": {"backend": "paper"}}))

    with pytest.raises(RuntimeError, match="trade_mode=sim requires broker_backend=live"):
        ConfigLoader.validate_startup(raise_on_error=True)


def test_validate_startup_accepts_real_with_live_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("CROSSTRADE_TOKEN", "unit-test-token")
    monkeypatch.setattr(ConfigLoader, "get", classmethod(lambda cls: {"mode": "real", "broker": {"backend": "live"}}))

    assert ConfigLoader.validate_startup(raise_on_error=True) is True


def test_validate_startup_warns_placeholder_api_key_in_sim(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("CROSSTRADE_TOKEN", "unit-test-token")
    cfg = {
        "mode": "sim",
        "broker": {"backend": "live"},
        "security": {
            "api_keys": {
                "sk_example_admin_key_replace_me": {
                    "enabled": True,
                    "role": "admin",
                }
            }
        },
    }
    monkeypatch.setattr(ConfigLoader, "get", classmethod(lambda cls: cfg))

    assert ConfigLoader.validate_startup(raise_on_error=True) is True
    assert "Placeholder/default API key active" in caplog.text


def test_validate_startup_fails_placeholder_api_key_in_real(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("CROSSTRADE_TOKEN", "unit-test-token")
    cfg = {
        "mode": "real",
        "broker": {"backend": "live"},
        "security": {
            "api_keys": {
                "sk_example_admin_key_replace_me": {
                    "enabled": True,
                    "role": "admin",
                }
            }
        },
    }
    monkeypatch.setattr(ConfigLoader, "get", classmethod(lambda cls: cfg))

    with pytest.raises(RuntimeError, match="Placeholder/default API key active"):
        ConfigLoader.validate_startup(raise_on_error=True)
