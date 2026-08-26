"""Emergency opt-in control plane + Fabric-default factory (ADR-0040)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from lumina_core.broker.broker_bridge.factory import _resolve_live_provider, broker_factory
from lumina_core.broker.emergency_opt_in import (
    assert_crosstrade_plugin_allowed,
    read_emergency_opt_in,
    set_market_data_fallback,
)
from lumina_core.broker.broker_bridge.paper_broker import PaperBroker
from lumina_launcher.core.config_manager import ConfigManager


def test_resolve_live_provider_defaults_to_ninjatrader() -> None:
    assert _resolve_live_provider(SimpleNamespace()) == "ninjatrader"
    assert _resolve_live_provider(SimpleNamespace(broker_live_provider="")) == "ninjatrader"
    assert _resolve_live_provider(SimpleNamespace(broker_live_provider="garbage")) == "ninjatrader"
    assert _resolve_live_provider(SimpleNamespace(broker_live_provider="crosstrade")) == "crosstrade"


def test_broker_factory_paper_no_crosstrade_import() -> None:
    broker = broker_factory(config=SimpleNamespace(broker_backend="paper"), engine=None, logger=None)
    assert isinstance(broker, PaperBroker)


def test_crosstrade_order_path_requires_explicit_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.dump({"broker": {"live_provider": "ninjatrader", "fallback_on_fabric_failure": False}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUMINA_CONFIG", str(cfg_path))
    monkeypatch.delenv("BROKER_LIVE_PROVIDER", raising=False)
    monkeypatch.delenv("BROKER_FALLBACK_ON_FABRIC_FAILURE", raising=False)

    state = read_emergency_opt_in(config_path=cfg_path)
    assert state.live_provider == "ninjatrader"
    assert not state.plugin_loadable

    with pytest.raises(RuntimeError, match="CrossTrade plugin blocked"):
        assert_crosstrade_plugin_allowed(config_path=cfg_path)


def test_crosstrade_plugin_allowed_when_live_provider_crosstrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.dump({"broker": {"live_provider": "crosstrade", "fallback_on_fabric_failure": False}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUMINA_CONFIG", str(cfg_path))
    monkeypatch.delenv("BROKER_LIVE_PROVIDER", raising=False)
    state = assert_crosstrade_plugin_allowed(config_path=cfg_path, purpose="test")
    assert state.order_provider_crosstrade
    assert state.plugin_loadable


def test_set_market_data_fallback_writes_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    cfg_path.write_text(
        yaml.dump({"broker": {"live_provider": "ninjatrader", "fallback_on_fabric_failure": False}}),
        encoding="utf-8",
    )
    env_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("LUMINA_CONFIG", str(cfg_path))
    monkeypatch.delenv("BROKER_FALLBACK_ON_FABRIC_FAILURE", raising=False)
    cm = ConfigManager(env_path=env_path, config_path=cfg_path)
    state = set_market_data_fallback(True, config_manager=cm, source="vault", workspace_root=tmp_path)
    assert state.market_data_fallback is True
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["broker"]["fallback_on_fabric_failure"] is True
    # Orders path still Fabric unless live_provider flipped.
    assert data["broker"]["live_provider"] == "ninjatrader"
    # Restore fail-closed so other tests in the same process are not poisoned.
    set_market_data_fallback(False, config_manager=cm, source="vault", workspace_root=tmp_path)
    monkeypatch.delenv("BROKER_FALLBACK_ON_FABRIC_FAILURE", raising=False)


def test_broker_factory_crosstrade_with_explicit_provider() -> None:
    from lumina_core.broker.broker_bridge.cross_trade_broker import CrossTradeBroker

    cfg = SimpleNamespace(
        broker_backend="live",
        trade_mode="sim",
        broker_live_provider="crosstrade",
        crosstrade_token="test-token",
        crosstrade_account="DEMO5042070",
    )
    broker = broker_factory(config=cfg, engine=None, logger=None)
    assert isinstance(broker, CrossTradeBroker)


def test_zero_crosstrade_import_on_paper_and_fabric_path() -> None:
    """ADR-0040: CrossTrade modules must not *newly* load on paper/Fabric paths."""
    import sys

    from lumina_core.broker.ninjatrader.bridge_service import reset_ninjatrader_bridge_service

    before = {k for k in sys.modules if "cross_trade" in k}
    broker_factory(config=SimpleNamespace(broker_backend="paper"), engine=None, logger=None)
    after_paper = {k for k in sys.modules if "cross_trade" in k}
    assert after_paper == before

    reset_ninjatrader_bridge_service()
    broker_factory(
        config=SimpleNamespace(
            broker_backend="live",
            trade_mode="sim",
            broker_live_provider="ninjatrader",
            ninjatrader_enabled=True,
            ninjatrader_account_name="Sim101",
        ),
        engine=None,
        logger=None,
    )
    after_nt = {k for k in sys.modules if "cross_trade" in k}
    assert after_nt == before
    reset_ninjatrader_bridge_service()
