"""Historical bar fetch strategy for CrossTrade market data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from lumina_core.engine import EngineConfig, MarketDataIngestService
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.order_gatekeeper import is_stale_contract_symbol, roll_stale_contract_symbol


@pytest.mark.unit
def test_roll_stale_contract_symbol_advances_quarterly_contract() -> None:
    now = datetime(2026, 6, 27, tzinfo=timezone.utc)
    assert is_stale_contract_symbol("MES JUN26", now_utc=now) is True
    assert roll_stale_contract_symbol("MES JUN26", now_utc=now) == "MES SEP26"


@pytest.mark.unit
def test_roll_stale_contract_symbol_keeps_active_contract() -> None:
    now = datetime(2026, 4, 15, tzinfo=timezone.utc)
    assert roll_stale_contract_symbol("MES JUN26", now_utc=now) == "MES JUN26"


@pytest.fixture
def market_data_service(tmp_path, monkeypatch: pytest.MonkeyPatch) -> MarketDataIngestService:
    """Force Crosstrade history path so pagination/daysBack expectations hold.

    Workspace yaml defaults to live_provider=ninjatrader (Fabric). These unit
    tests assert CrossTrade HTTP payload shape — isolate from Fabric SSOT.
    """
    monkeypatch.setattr("lumina_core.engine.rl.ppo_trainer.PPOTrainer", MagicMock())
    monkeypatch.setenv("BROKER_LIVE_PROVIDER", "crosstrade")
    cfg = EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
        broker_live_provider="crosstrade",
    )
    eng = LuminaEngine(config=cfg)
    app = SimpleNamespace(
        logger=logging.getLogger("lumina-test-hist"),
        INSTRUMENT="MES JUN26",
        CROSSTRADE_TOKEN="test-token",
    )
    eng.bind_app(cast(ModuleType, app))
    svc = MarketDataIngestService(engine=eng)
    # Isolate from workspace yaml live_provider=ninjatrader SSOT override.
    monkeypatch.setattr(svc, "_yaml_live_provider", lambda: "crosstrade")
    return svc


@pytest.mark.unit
def test_fetch_historical_bars_uses_daysback_first_for_preflight(
    market_data_service: MarketDataIngestService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads: list[dict[str, Any]] = []

    def _fake_post(*_args, **kwargs):
        payloads.append(dict(kwargs.get("json") or {}))
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "bars": [
                {
                    "time": "2026-06-27T14:00:00.0000000Z",
                    "open": 5000.0,
                    "high": 5001.0,
                    "low": 4999.0,
                    "close": 5000.5,
                    "volume": 10,
                }
            ]
        }
        return response

    monkeypatch.setattr("lumina_core.engine.market_data_service.requests.post", _fake_post)
    monkeypatch.setattr(
        "lumina_core.engine.market_data_service.is_stale_contract_symbol",
        lambda *_a, **_k: False,
    )

    bars = market_data_service._fetch_historical_bars(
        instrument="MES SEP26",
        days_back=3,
        limit=500,
    )

    assert len(bars) == 1
    assert payloads
    assert "daysBack" in payloads[0]
    assert "from" not in payloads[0]


@pytest.mark.unit
def test_fetch_historical_bars_rolls_stale_instrument(
    market_data_service: MarketDataIngestService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads: list[dict[str, Any]] = []

    def _fake_post(*_args, **kwargs):
        payloads.append(dict(kwargs.get("json") or {}))
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"bars": []}
        return response

    monkeypatch.setattr("lumina_core.engine.market_data_service.requests.post", _fake_post)
    monkeypatch.setattr(
        "lumina_core.engine.market_data_service.roll_stale_contract_symbol",
        lambda symbol, **_k: "MES SEP26" if symbol == "MES JUN26" else symbol,
    )

    market_data_service._fetch_historical_bars(
        instrument="MES JUN26",
        days_back=56,
        limit=None,
    )

    assert payloads
    assert payloads[0]["instrument"] == "MES SEP26"


@pytest.mark.unit
def test_fetch_historical_bars_pagination_uses_midnight_boundaries(
    market_data_service: MarketDataIngestService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads: list[dict[str, Any]] = []

    def _fake_post(*_args, **kwargs):
        payload = dict(kwargs.get("json") or {})
        payloads.append(payload)
        response = MagicMock()
        response.status_code = 200
        if payload.get("daysBack"):
            response.json.return_value = {"bars": []}
        else:
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

    fixed_now = datetime(2026, 6, 27, 14, 32, 12, tzinfo=timezone.utc)

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

    market_data_service._fetch_historical_bars(
        instrument="MES SEP26",
        days_back=56,
        limit=None,
    )

    ranged = [p for p in payloads if "from" in p]
    assert ranged, "expected day-aligned from/to pagination after empty daysBack"
    assert all(str(p["from"]).endswith("T00:00:00Z") for p in ranged)
    assert all(str(p["to"]).endswith("T00:00:00Z") for p in ranged)
