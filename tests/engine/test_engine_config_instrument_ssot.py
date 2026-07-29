"""EngineConfig instrument SSOT from trading.instrument yaml."""

from __future__ import annotations

import pytest

from lumina_core.engine import engine_config as eng_cfg


@pytest.mark.unit
def test_default_trading_instrument_prefers_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    eng_cfg._load_yaml_config.cache_clear()
    monkeypatch.delenv("INSTRUMENT", raising=False)
    monkeypatch.setattr(
        eng_cfg,
        "_load_yaml_config",
        lambda: {"trading": {"instrument": "MES SEP26"}},
    )
    assert eng_cfg._default_trading_instrument() == "MES SEP26"


@pytest.mark.unit
def test_default_trading_instrument_env_overrides_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    eng_cfg._load_yaml_config.cache_clear()
    monkeypatch.setenv("INSTRUMENT", "MNQ SEP26")
    monkeypatch.setattr(
        eng_cfg,
        "_load_yaml_config",
        lambda: {"trading": {"instrument": "MES SEP26"}},
    )
    assert eng_cfg._default_trading_instrument() == "MNQ SEP26"


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
    assert eng_cfg._parse_swarm_symbols() == ["MES SEP26"]
