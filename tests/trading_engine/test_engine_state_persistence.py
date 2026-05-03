from __future__ import annotations

import pytest

from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine


@pytest.mark.unit
def test_engine_state_persistence_roundtrip(tmp_path) -> None:
    # gegeven
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
    )
    engine = LuminaEngine(config=cfg)
    engine.sim_position_qty = 2
    engine.live_trade_signal = "BUY"
    engine.memory_buffer.append({"note": "persist-me"})
    engine.set_current_dream_fields({"regime": "TRENDING", "confidence": 0.91})

    # wanneer
    engine.save_state()
    loaded = LuminaEngine(config=cfg)
    loaded.load_state()

    # dan
    assert loaded.sim_position_qty == 2
    assert loaded.live_trade_signal == "BUY"
    assert list(loaded.memory_buffer)[-1] == {"note": "persist-me"}
    assert loaded.get_current_dream_snapshot().get("regime") == "TRENDING"
