from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.news_enricher import enrich_ticks_with_news, fetch_economic_events


@pytest.mark.unit
def test_fetch_economic_events_uses_cache_when_apis_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "state" / "birth_news_cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-01-15T13:30:00+00:00",
                    "event_type": "CPI",
                    "impact": "high",
                    "country": "US",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("FINNHUB_API_KEY", "")
    monkeypatch.setenv("FMP_API_KEY", "")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "")

    events = fetch_economic_events(
        from_date="2026-01-01",
        to_date="2026-01-31",
        workspace_root=tmp_path,
        cache_path="state/birth_news_cache.json",
        enable_cache=True,
    )

    assert len(events) == 1
    assert events[0].event_type == "CPI"


@pytest.mark.unit
def test_enrich_ticks_marks_news_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_path = tmp_path / "state" / "birth_news_cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-01-15T13:30:00+00:00",
                    "event_type": "NFP",
                    "impact": "high",
                    "country": "US",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FINNHUB_API_KEY", "")
    monkeypatch.setenv("FMP_API_KEY", "")

    ticks = [
        {
            "timestamp": "2026-01-15T13:29:00Z",
            "last": 5000.0,
        },
        {
            "timestamp": "2026-01-15T13:31:00Z",
            "last": 5001.0,
        },
    ]

    enriched = enrich_ticks_with_news(
        ticks,
        workspace_root=tmp_path,
        pre_minutes=15,
        post_minutes=15,
        enable_cache=True,
    )

    assert enriched[0]["news_window_active"] == 1.0
    assert enriched[1]["news_window_active"] == 1.0
    assert enriched[0].get("news_event_type") == "NFP"
