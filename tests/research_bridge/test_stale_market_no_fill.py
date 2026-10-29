"""Fail-closed: stale data or lost connection means no new signals or intents."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.research_bridge.jsonl import append_shadow_record
from lumina_core.research_bridge.market_health import (
    LOST_CONNECTION,
    STALE_OR_MISSING,
    MarketHealth,
    healthy_closed_bar,
    unhealthy_market,
)
from tests.research_bridge.helpers import make_runtime, sealed_candidate


@pytest.mark.unit
def test_default_market_is_unhealthy() -> None:
    market = unhealthy_market()
    allowed, reason = market.allow_new_intents()
    assert allowed is False
    assert reason == LOST_CONNECTION
    assert market.reference_price() is None


@pytest.mark.unit
def test_forming_only_refuses_intent_and_observe(tmp_path: Path) -> None:
    _bus, authority, runtime, alerts, observe = make_runtime(tmp_path, healthy=True)
    runtime.replace_market(
        MarketHealth(
            connection_alive=True,
            forming_only=True,
            last_closed_close=5000.0,
            last_closed_age_sec=1.0,
        )
    )
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is None
    assert runtime.issued_intents() == ()
    assert runtime.issued_fills() == ()
    assert observe.calls == []
    assert any(STALE_OR_MISSING in str(item["code"]) for item in alerts.records)
    assert any("stale or missing market" in str(item["message"]) for item in alerts.records)
    jsonl = (tmp_path / "research_shadow.jsonl").read_text(encoding="utf-8")
    assert "hypothetical_fill" not in jsonl
    assert '"fill": "refused"' in jsonl


@pytest.mark.unit
def test_lost_connection_refuses_intent(tmp_path: Path) -> None:
    _bus, authority, runtime, alerts, observe = make_runtime(tmp_path, healthy=True)
    runtime.replace_market(
        MarketHealth(
            connection_alive=False,
            forming_only=False,
            last_closed_close=5000.0,
            last_closed_age_sec=1.0,
        )
    )
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is None
    assert runtime.issued_fills() == ()
    assert observe.calls == []
    assert any(LOST_CONNECTION in str(item["code"]) for item in alerts.records)
    assert any("lost connection" in str(item["message"]) for item in alerts.records)


@pytest.mark.unit
def test_stale_age_and_missing_close_refuse() -> None:
    stale = MarketHealth(
        connection_alive=True,
        forming_only=False,
        last_closed_close=5000.0,
        last_closed_age_sec=121.0,
    )
    missing = MarketHealth(
        connection_alive=True,
        forming_only=False,
        last_closed_close=None,
        last_closed_age_sec=1.0,
    )
    zero = MarketHealth(
        connection_alive=True,
        forming_only=False,
        last_closed_close=0.0,
        last_closed_age_sec=1.0,
    )
    missing_age = MarketHealth(
        connection_alive=True,
        forming_only=False,
        last_closed_close=5000.0,
        last_closed_age_sec=None,
    )
    for market in (stale, missing, zero, missing_age):
        allowed, reason = market.allow_new_intents()
        assert allowed is False
        assert reason == STALE_OR_MISSING
    ok = healthy_closed_bar(close=5000.0, age_sec=1.0)
    allowed, reason = ok.allow_new_intents()
    assert allowed is True
    assert reason == "ok"
    assert ok.reference_price() == pytest.approx(5000.0)


@pytest.mark.unit
def test_nan_close_or_age_is_stale() -> None:
    nan_close = MarketHealth(
        connection_alive=True,
        forming_only=False,
        last_closed_close=float("nan"),
        last_closed_age_sec=1.0,
    )
    nan_age = MarketHealth(
        connection_alive=True,
        forming_only=False,
        last_closed_close=5000.0,
        last_closed_age_sec=float("nan"),
    )
    negative_age = MarketHealth(
        connection_alive=True,
        forming_only=False,
        last_closed_close=5000.0,
        last_closed_age_sec=-1.0,
    )
    for market in (nan_close, nan_age, negative_age):
        allowed, reason = market.allow_new_intents()
        assert allowed is False
        assert reason == STALE_OR_MISSING
        assert market.reference_price() is None


@pytest.mark.unit
def test_jsonl_write_failure_does_not_raise(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x", encoding="utf-8")
    append_shadow_record(blocker / "shadow.jsonl", {"event": "refused"})
    append_shadow_record(tmp_path / "ok.jsonl", {"event": "signal_intent", "fill": "pending", "ts_utc": "2026-10-28T12:00:00Z"})
    written = (tmp_path / "ok.jsonl").read_text(encoding="utf-8")
    assert "signal_intent" in written
