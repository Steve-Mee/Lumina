"""Yaml SSOT cache must not poison broker_live_provider to crosstrade."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.engine import engine_config_helpers as helpers
from lumina_core.engine.market_data_history_fetch import MarketDataHistoryFetchMixin


@pytest.mark.unit
def test_yaml_cache_survives_wrong_cwd_then_correct_path(tmp_path: Path) -> None:
    """First load from empty cwd must not permanently force crosstrade."""
    helpers.clear_yaml_config_cache()
    workspace = Path.cwd()
    cfg_src = workspace / "config.yaml"
    if not cfg_src.is_file():
        pytest.skip("workspace config.yaml missing")

    old = os.getcwd()
    try:
        os.chdir(tempfile.gettempdir())
        os.environ.pop("LUMINA_CONFIG", None)
        helpers.clear_yaml_config_cache()
        # Wrong cwd: no config → empty
        assert helpers._load_yaml_config() == {} or "broker" not in helpers._load_yaml_config()
        # Point at real config via LUMINA_CONFIG
        os.environ["LUMINA_CONFIG"] = str(cfg_src.resolve())
        helpers.clear_yaml_config_cache()
        data = helpers._load_yaml_config()
        assert isinstance(data.get("broker"), dict)
        assert str(data["broker"].get("live_provider", "")).lower() == "ninjatrader"
        assert helpers._config_yaml_nested("crosstrade", "broker", "live_provider") == "ninjatrader"
    finally:
        os.chdir(old)
        os.environ.pop("LUMINA_CONFIG", None)
        helpers.clear_yaml_config_cache()


@pytest.mark.unit
def test_history_provider_prefers_yaml_ninjatrader_over_poisoned_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _H(MarketDataHistoryFetchMixin):
        def __init__(self) -> None:
            self.engine = SimpleNamespace(
                config=SimpleNamespace(
                    broker_live_provider="crosstrade",  # poisoned
                    market_data_provider="",
                    fallback_on_fabric_failure=False,
                )
            )

    h = _H()
    monkeypatch.setattr(h, "_yaml_live_provider", lambda: "ninjatrader")
    assert h._history_provider() == "fabric"
