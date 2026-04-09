from __future__ import annotations

import logging
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import pandas as pd
import pytest

from lumina_core.engine import EngineConfig, MarketDataService
from lumina_core.engine.lumina_engine import LuminaEngine


class _NoOpPPOTrainer:
    """Test double to avoid hard dependency on stable-baselines3 during unit tests."""

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def train(self, *_args, **_kwargs) -> None:
        return None

    def predict_action(self, *_args, **_kwargs) -> dict[str, float]:
        return {"signal": 0, "qty_pct": 0.0, "stop_mult": 0.0, "target_mult": 0.0}


@pytest.fixture
def runtime_app() -> SimpleNamespace:
    """Minimal app surface required by engine/service methods under test."""
    return SimpleNamespace(
        logger=logging.getLogger("lumina-test"),
        INSTRUMENT=os.getenv("INSTRUMENT", "MES JUN26"),
        CROSSTRADE_TOKEN=os.getenv("CROSSTRADE_TOKEN", ""),
    )


@pytest.fixture
def engine(tmp_path: Path, runtime_app: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> LuminaEngine:
    monkeypatch.setattr("lumina_core.engine.rl.ppo_trainer.PPOTrainer", _NoOpPPOTrainer)
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
    )
    eng = LuminaEngine(config=cfg)
    eng.bind_app(cast(ModuleType, runtime_app))
    return eng


@pytest.fixture
def market_data_service(engine: LuminaEngine) -> MarketDataService:
    return MarketDataService(engine=engine)


@pytest.fixture(scope="session")
def real_mes_ohlc(tmp_path_factory: pytest.TempPathFactory) -> pd.DataFrame:
    """Load 3 days of real MES 1-min bars via the OOP MarketDataService path."""
    temp_dir = tmp_path_factory.mktemp("mes_real_data")
    cfg = EngineConfig(
        state_file=temp_dir / "state.json",
        thought_log=temp_dir / "thought_log.jsonl",
        bible_file=temp_dir / "bible.json",
        live_jsonl=temp_dir / "live_stream.jsonl",
    )
    import lumina_core.engine.rl.ppo_trainer as ppo_trainer_mod

    ppo_trainer_mod.PPOTrainer = _NoOpPPOTrainer
    eng = LuminaEngine(config=cfg)
    app = SimpleNamespace(
        logger=logging.getLogger("lumina-test-real"),
        INSTRUMENT=os.getenv("INSTRUMENT", "MES JUN26"),
        CROSSTRADE_TOKEN=os.getenv("CROSSTRADE_TOKEN", ""),
    )
    eng.bind_app(cast(ModuleType, app))
    service = MarketDataService(engine=eng)

    loaded = service.load_historical_ohlc(days_back=3, limit=5000)
    if not loaded or eng.ohlc_1min.empty:
        pytest.skip("Real MES 1-min data unavailable via load_historical_ohlc (token/network/API required).")

    return eng.ohlc_1min.copy()
