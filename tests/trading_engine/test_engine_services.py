from __future__ import annotations

import pytest

from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.trading_engine.engine_services import EngineServices


@pytest.mark.unit
def test_engine_services_dataclass_defaults_none() -> None:
    # gegeven
    services = EngineServices()

    # wanneer / dan
    assert services.local_engine is None
    assert services.event_bus is None
    assert services.portfolio_var_allocator is None


@pytest.mark.unit
def test_lumina_engine_syncs_service_registry(tmp_path) -> None:
    # gegeven
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
    )
    engine = LuminaEngine(config=cfg)
    fake_bus = object()
    fake_reasoning = object()

    # wanneer
    engine.event_bus = fake_bus
    engine.reasoning_service = fake_reasoning
    engine._sync_services_registry()

    # dan
    assert engine.services.event_bus is fake_bus
    assert engine.services.reasoning_service is fake_reasoning
