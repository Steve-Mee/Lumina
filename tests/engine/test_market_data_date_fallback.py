"""Historical API date-format fallback for birth data expansion."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from lumina_core.engine import EngineConfig, MarketDataIngestService
from lumina_core.engine.lumina_engine import LuminaEngine


@pytest.fixture
def market_data_service(tmp_path, monkeypatch: pytest.MonkeyPatch) -> MarketDataIngestService:
    monkeypatch.setattr("lumina_core.engine.rl.ppo_trainer.PPOTrainer", MagicMock())
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
    )
    eng = LuminaEngine(config=cfg)
    app = SimpleNamespace(
        logger=logging.getLogger("lumina-test-date-fallback"),
        INSTRUMENT="MES SEP26",
        CROSSTRADE_TOKEN="test-token",
    )
    eng.bind_app(cast(ModuleType, app))
    return MarketDataIngestService(engine=eng)


@pytest.mark.unit
def test_post_historical_bars_retries_daysback_on_date_format_error(
    market_data_service: MarketDataIngestService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads: list[dict[str, Any]] = []

    def _fake_post(*_args, **kwargs):
        payload = dict(kwargs.get("json") or {})
        payloads.append(payload)
        response = MagicMock()
        if "from" in payload:
            response.status_code = 400
            response.text = '{"error": "Invalid \'from\' date format: 16/02/2025 0:00:00"}'
            return response
        response.status_code = 200
        response.json.return_value = {
            "bars": [
                {
                    "time": "2026-06-01T14:00:00.0000000Z",
                    "open": 5000.0,
                    "high": 5001.0,
                    "low": 4999.0,
                    "close": 5000.5,
                    "volume": 10,
                }
            ]
        }
        return response

    fixed_now = datetime(2026, 6, 27, 14, 0, 0, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("lumina_core.engine.market_data_service.datetime", _FixedDateTime)
    monkeypatch.setattr("lumina_core.engine.market_data_service.requests.post", _fake_post)
    monkeypatch.setattr(
        "lumina_core.engine.market_data_service.is_stale_contract_symbol",
        lambda *_a, **_k: False,
    )

    bars = market_data_service._fetch_historical_bars(
        instrument="MES SEP26",
        days_back=14,
        limit=500,
        prefer_daysback_only=True,
    )

    assert len(bars) == 1
    assert any("daysBack" in p for p in payloads)
