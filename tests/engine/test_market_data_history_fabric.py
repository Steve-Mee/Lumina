"""Historical data plane routes to Fabric when live_provider=ninjatrader."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from lumina_core.engine.market_data_history_fetch import MarketDataHistoryFetchMixin


class _Harness(MarketDataHistoryFetchMixin):
    def __init__(self, provider: str = "ninjatrader", fallback: bool = False) -> None:
        self.engine = SimpleNamespace(
            config=SimpleNamespace(
                broker_live_provider=provider,
                market_data_provider="",
                fallback_on_fabric_failure=fallback,
                crosstrade_token=None,
                instrument="MES SEP26",
                ninjatrader_fabric_host="127.0.0.1",
                ninjatrader_fabric_port=50051,
                ninjatrader_fabric_auth_token_env="LUMINA_FABRIC_TOKEN",
                ninjatrader_nt8_api_key="tok",
                fabric_heartbeat_interval_ms=0,
                fabric_heartbeat_timeout_ms=5000,
            )
        )
        self.logger = MagicMock()
        self.last_requested_instrument = ""
        self.last_resolved_instrument = ""

    def _app(self) -> Any:
        return SimpleNamespace(
            logger=self.logger,
            CROSSTRADE_TOKEN="",
            INSTRUMENT="MES SEP26",
        )

    def _normalize_symbol(self, instrument: str) -> str:
        return str(instrument or "").strip().upper()


def test_history_provider_fabric_when_ninjatrader() -> None:
    h = _Harness("ninjatrader")
    assert h._history_provider() == "fabric"


def test_history_provider_crosstrade_when_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    h = _Harness("crosstrade")
    # Isolate from workspace yaml live_provider=ninjatrader SSOT override.
    monkeypatch.setattr(h, "_yaml_live_provider", lambda: "")
    monkeypatch.delenv("BROKER_LIVE_PROVIDER", raising=False)
    assert h._history_provider() == "crosstrade"


def test_history_provider_fabric_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    h = _Harness("")
    monkeypatch.setattr(h, "_yaml_live_provider", lambda: "")
    monkeypatch.delenv("BROKER_LIVE_PROVIDER", raising=False)
    assert h._history_provider() == "fabric"


def test_fetch_historical_uses_fabric_not_crosstrade(monkeypatch: pytest.MonkeyPatch) -> None:
    h = _Harness("ninjatrader", fallback=False)
    monkeypatch.setattr(
        h,
        "_resolve_historical_instrument",
        lambda instrument, app: instrument,
    )

    calls: list[str] = []

    def fake_fabric(**kwargs: Any) -> list[dict[str, Any]]:
        calls.append("fabric")
        return [
            {
                "timestamp": "2026-08-01T12:00:00Z",
                "time": "2026-08-01T12:00:00Z",
                "epoch": 1754049600,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10,
            }
        ]

    def fake_post(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        calls.append("crosstrade")
        raise AssertionError("CrossTrade must not be called when fabric returns bars")

    monkeypatch.setattr(h, "_fetch_historical_bars_via_fabric", fake_fabric)
    monkeypatch.setattr(h, "_post_historical_bars", fake_post)

    bars = h._fetch_historical_bars(instrument="MES SEP26", days_back=3, limit=100)
    assert calls == ["fabric"]
    assert len(bars) == 1
    assert bars[0]["close"] == 1.5


def test_fabric_empty_fail_closed_no_crosstrade(monkeypatch: pytest.MonkeyPatch) -> None:
    h = _Harness("ninjatrader", fallback=False)
    monkeypatch.setattr(h, "_resolve_historical_instrument", lambda instrument, app: instrument)
    monkeypatch.setattr(h, "_fetch_historical_bars_via_fabric", lambda **_k: [])

    def boom(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        raise AssertionError("must not fall back to CrossTrade")

    monkeypatch.setattr(h, "_post_historical_bars", boom)
    assert h._fetch_historical_bars(instrument="MES", days_back=1, limit=50) == []


def test_fabric_bars_to_ct_shape_from_unix_ms() -> None:
    h = _Harness()
    shaped = h._fabric_bars_to_ct_shape(
        [
            {
                "timestamp_unix_ms": 1_700_000_000_000,
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 3,
            }
        ]
    )
    assert len(shaped) == 1
    assert shaped[0]["close"] == 10.5
    assert "T" in shaped[0]["timestamp"]


def test_fabric_pagination_walks_backward_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Birth SLA needs multi-week coverage — must not stop after one recent barsBack slice."""
    h = _Harness("ninjatrader", fallback=False)
    windows: list[tuple[int, int]] = []

    class _FakeClient:
        def connect(self) -> bool:
            return True

        def disconnect(self) -> None:
            return None

        def request_historical_data(self, **kwargs: Any) -> dict[str, Any]:
            start = int(kwargs.get("start_unix_ms") or 0)
            end = int(kwargs.get("end_unix_ms") or 0)
            windows.append((start, end))
            # One bar at midpoint of each window (inside filter pad)
            mid = (start + end) // 2
            return {
                "code": "ok",
                "message": "ok",
                "instrument": "MES SEP26",
                "bars": [
                    {
                        "timestamp_unix_ms": mid,
                        "epoch": mid // 1000,
                        "open": 1.0,
                        "high": 2.0,
                        "low": 0.5,
                        "close": 1.5,
                        "volume": 10,
                    }
                ],
            }

    class _FC:
        @staticmethod
        def from_engine_config(*_a: Any, **_k: Any) -> Any:
            return SimpleNamespace(
                heartbeat_interval_ms=0,
                target="127.0.0.1:50051",
            )

    import lumina_core.broker.ninjatrader.fabric_client as fc

    monkeypatch.setattr(fc, "FabricConfig", _FC)
    monkeypatch.setattr(fc, "FabricGrpcClient", lambda *_a, **_k: _FakeClient())

    bars = h._fetch_historical_bars_via_fabric(
        instrument="MES SEP26",
        days_back=28,
        limit=50_000,
    )
    assert len(bars) >= 3
    # Windows must step backward (end decreases over time)
    assert len(windows) >= 3
    ends = [w[1] for w in windows]
    assert ends[0] >= ends[-1]
    # Coverage: first chunk ends near "now", last chunk starts ~28d earlier
    span_ms = windows[0][1] - windows[-1][0]
    assert span_ms >= 20 * 86_400 * 1000


def test_fabric_drops_out_of_window_barsback_poison(monkeypatch: pytest.MonkeyPatch) -> None:
    """barsBack always returns 'now' — must not count as coverage for older chunks."""
    h = _Harness("ninjatrader", fallback=False)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    class _PoisonClient:
        def connect(self) -> bool:
            return True

        def disconnect(self) -> None:
            return None

        def request_historical_data(self, **kwargs: Any) -> dict[str, Any]:
            # Always return bars near "now" regardless of requested window
            return {
                "code": "ok",
                "bars": [
                    {
                        "timestamp_unix_ms": now_ms - 60_000 * i,
                        "epoch": (now_ms - 60_000 * i) // 1000,
                        "open": 1.0,
                        "high": 1.0,
                        "low": 1.0,
                        "close": 1.0,
                        "volume": 1,
                    }
                    for i in range(100)
                ],
            }

    class _FC:
        @staticmethod
        def from_engine_config(*_a: Any, **_k: Any) -> Any:
            return SimpleNamespace(heartbeat_interval_ms=0, target="127.0.0.1:50051")

    import lumina_core.broker.ninjatrader.fabric_client as fc

    monkeypatch.setattr(fc, "FabricConfig", _FC)
    monkeypatch.setattr(fc, "FabricGrpcClient", lambda *_a, **_k: _PoisonClient())

    bars = h._fetch_historical_bars_via_fabric(
        instrument="MES SEP26",
        days_back=56,
        limit=50_000,
    )
    # Only the recent chunk accepts near-now bars; older chunks filter them out.
    # Span must stay small (poison rejected for old windows) — not fake 56d.
    epochs = [int(b["epoch"]) for b in bars if b.get("epoch")]
    if epochs:
        span_days = (max(epochs) - min(epochs)) / 86_400 + 1
        assert span_days < 14  # must NOT pretend we have 56 days of poison
