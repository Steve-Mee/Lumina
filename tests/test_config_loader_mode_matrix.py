from __future__ import annotations

import pytest

from lumina_core.config_loader import ConfigLoader


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "unit-test-xai-key")
    monkeypatch.setenv("LUMINA_JWT_SECRET_KEY", "unit-test-jwt-secret")
    # Ensure ambient shell vars do not override test-provided config unless explicit in test.
    monkeypatch.delenv("LUMINA_ENFORCE_ENV_RUNTIME_MODE", raising=False)
    monkeypatch.delenv("TRADE_MODE", raising=False)
    monkeypatch.delenv("LUMINA_MODE", raising=False)
    monkeypatch.delenv("BROKER_BACKEND", raising=False)


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


def test_validate_startup_accepts_sim_real_guard_with_live_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("CROSSTRADE_TOKEN", "unit-test-token")
    monkeypatch.setenv("ENABLE_SIM_REAL_GUARD", "true")
    monkeypatch.setattr(
        ConfigLoader,
        "get",
        classmethod(lambda cls: {"mode": "sim_real_guard", "broker": {"backend": "live"}}),
    )

    assert ConfigLoader.validate_startup(raise_on_error=True) is True


def test_validate_startup_rejects_sim_real_guard_with_paper_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ENABLE_SIM_REAL_GUARD", "true")
    monkeypatch.setattr(
        ConfigLoader,
        "get",
        classmethod(lambda cls: {"mode": "sim_real_guard", "broker": {"backend": "paper"}}),
    )

    with pytest.raises(RuntimeError, match="trade_mode=sim_real_guard requires broker_backend=live"):
        ConfigLoader.validate_startup(raise_on_error=True)


def test_validate_startup_rejects_sim_real_guard_when_feature_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("CROSSTRADE_TOKEN", "unit-test-token")
    monkeypatch.delenv("ENABLE_SIM_REAL_GUARD", raising=False)
    monkeypatch.setattr(
        ConfigLoader,
        "get",
        classmethod(lambda cls: {"mode": "sim_real_guard", "broker": {"backend": "live"}}),
    )

    with pytest.raises(RuntimeError, match="sim_real_guard is disabled by feature flag"):
        ConfigLoader.validate_startup(raise_on_error=True)


def test_validate_startup_warns_placeholder_api_key_in_sim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import patch

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

    # Patch the module-level logger directly so we're ordering-agnostic.
    with patch("lumina_core.config_loader._LOG") as mock_log:
        assert ConfigLoader.validate_startup(raise_on_error=True) is True
        warning_calls = [str(c) for c in mock_log.warning.call_args_list]
        assert any("Placeholder/default API key active" in c for c in warning_calls), (
            f"Expected placeholder warning, got: {warning_calls}"
        )


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


def test_validate_startup_prefers_env_mode_and_broker_over_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LUMINA_ENFORCE_ENV_RUNTIME_MODE", "true")
    monkeypatch.setenv("TRADE_MODE", "paper")
    monkeypatch.setenv("BROKER_BACKEND", "paper")
    monkeypatch.setattr(
        ConfigLoader,
        "get",
        classmethod(lambda cls: {"mode": "sim", "broker": {"backend": "paper"}}),
    )

    assert ConfigLoader.validate_startup(raise_on_error=True) is True
