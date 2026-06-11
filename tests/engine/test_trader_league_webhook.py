"""Tests for TraderLeagueWebhook (D2 sub-slice 14)."""

from types import SimpleNamespace

import pytest

from lumina_core.engine.trader_league_webhook import TraderLeagueWebhook


@pytest.mark.unit
def test_trader_league_webhook_posts(monkeypatch):
    posted: list[dict] = []

    class Resp:
        def raise_for_status(self):
            return None

    def fake_post(url, json=None, timeout=5):
        posted.append({"url": url, "json": json})
        return Resp()

    monkeypatch.setattr("lumina_core.engine.trader_league_webhook.requests.post", fake_post)
    app = SimpleNamespace(
        config=SimpleNamespace(participant_id="TEST"),
        logger=SimpleNamespace(warning=lambda *a, **k: None),
    )
    TraderLeagueWebhook(app=app, webhook_url="http://test/webhook").push(
        mode="paper",
        symbol="MES",
        signal="BUY",
        entry_price=100.0,
        exit_price=101.0,
        qty=1,
        pnl_dollars=5.0,
    )
    assert len(posted) == 1
    assert posted[0]["json"]["symbol"] == "MES"
    print("MANUAL_SMOKE_SUB14_WEBHOOK_SUCCESS")
