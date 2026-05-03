from __future__ import annotations

import pytest

from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine


@pytest.mark.unit
def test_lumina_engine_missing_attr_raises_attribute_error(tmp_path) -> None:
    # gegeven
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
    )
    engine = LuminaEngine(config=cfg)

    # wanneer / dan
    with pytest.raises(AttributeError):
        _ = engine.legacy_runtime_only_field
