"""EngineConfig instrument SSOT from trading.instrument yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.engine import engine_config as eng_cfg
from lumina_core.engine.engine_config import EngineConfig


@pytest.mark.unit
def test_engine_config_instantiates_with_path_fields() -> None:
    """Regression: missing Path/os imports made Pydantic report class-not-fully-defined.

    Birth historical preflight builds ApplicationContainer → EngineConfig() and failed with:
    `EngineConfig` is not fully defined; you should define `Path`, then call model_rebuild().
    """
    cfg = EngineConfig()
    assert isinstance(cfg.state_file, Path)
    assert isinstance(cfg.journal_dir, Path)
    assert cfg.trade_mode in {"paper", "sim", "sim_real_guard", "real"}


@pytest.mark.unit
def test_default_trading_instrument_prefers_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    eng_cfg._load_yaml_config.cache_clear()
    monkeypatch.delenv("INSTRUMENT", raising=False)
    monkeypatch.setattr(
        eng_cfg,
        "_load_yaml_config",
        lambda: {"trading": {"instrument": "MES SEP26"}},
    )
    from lumina_core.order_gatekeeper.contract_symbols import live_listing

    assert eng_cfg._default_trading_instrument() == live_listing("MES SEP26")


@pytest.mark.unit
def test_default_trading_instrument_env_overrides_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    eng_cfg._load_yaml_config.cache_clear()
    monkeypatch.setenv("INSTRUMENT", "MNQ SEP26")
    monkeypatch.setattr(
        eng_cfg,
        "_load_yaml_config",
        lambda: {"trading": {"instrument": "MES SEP26"}},
    )
    from lumina_core.order_gatekeeper.contract_symbols import live_listing

    assert eng_cfg._default_trading_instrument() == live_listing("MNQ SEP26")


@pytest.mark.unit
def test_default_trading_instrument_calendar_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.engine import engine_config_helpers as helpers
    from lumina_core.order_gatekeeper.contract_symbols import live_listing

    monkeypatch.delenv("INSTRUMENT", raising=False)
    monkeypatch.setattr(helpers, "_load_yaml_config", lambda: {})
    got = helpers._default_trading_instrument()
    assert got == live_listing("MES")
    assert got != "MES SEP26"


@pytest.mark.unit
def test_parse_swarm_symbols_defaults_to_primary_instrument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eng_cfg._load_yaml_config.cache_clear()
    monkeypatch.delenv("SWARM_SYMBOLS", raising=False)
    monkeypatch.delenv("INSTRUMENT", raising=False)
    monkeypatch.setattr(
        eng_cfg,
        "_load_yaml_config",
        lambda: {"trading": {"instrument": "MES SEP26"}},
    )
    from lumina_core.order_gatekeeper.contract_symbols import live_listing

    assert eng_cfg._parse_swarm_symbols() == [live_listing("MES SEP26")]
