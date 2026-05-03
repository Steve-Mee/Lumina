from __future__ import annotations

import pytest

from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine


@pytest.mark.unit
def test_engine_snapshot_serialization_is_deterministic(tmp_path) -> None:
    # gegeven
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
    )
    engine = LuminaEngine(config=cfg)
    engine.sim_position_qty = 1
    engine.live_position_qty = 3
    engine.last_entry_price = 5012.25
    engine.account_equity = 51000.0
    engine.realized_pnl_today = 123.4
    engine.open_pnl = -12.3
    engine.set_current_dream_fields({"regime": "VOLATILE", "confidence": 0.66, "chosen_strategy": "fade-breakout"})

    # wanneer
    first = engine.serialize_state_snapshot()
    second = engine.serialize_state_snapshot()

    # dan
    assert first == second
    assert first["position"]["live_position_qty"] == 3
    assert first["agent"]["regime"] == "VOLATILE"
