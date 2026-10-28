"""Historical economic news enrichment for Birth Phase (BRO)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.news_enricher")


@dataclass(slots=True)
class NewsEvent:
    timestamp: datetime
    event_type: str
    impact: str
    country: str = ""


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _tick_ts(tick: dict[str, Any]) -> datetime | None:
    return _parse_ts(tick.get("timestamp") or tick.get("time"))


def _fetch_finnhub(from_date: str, to_date: str, api_key: str) -> list[NewsEvent]:
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/calendar/economic",
            params={"from": from_date, "to": to_date, "token": api_key},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        payload = resp.json()
        rows = payload.get("economicCalendar") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        out: list[NewsEvent] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ts = _parse_ts(row.get("time") or row.get("date"))
            if ts is None:
                continue
            impact_raw = str(row.get("impact", "") or "").lower()
            impact = "high" if impact_raw in {"3", "high"} else impact_raw or "medium"
            out.append(
                NewsEvent(
                    timestamp=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
                    event_type=str(row.get("event", "economic") or "economic"),
                    impact=impact,
                    country=str(row.get("country", "") or ""),
                )
            )
        return out
    except requests.RequestException as exc:
        logger.warning("birth.news.finnhub_failed detail=%s", exc)
        return []


def _fetch_fmp(from_date: str, to_date: str, api_key: str) -> list[NewsEvent]:
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://financialmodelingprep.com/api/v3/economic_calendar",
            params={"from": from_date, "to": to_date, "apikey": api_key},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        rows = resp.json()
        if not isinstance(rows, list):
            return []
        out: list[NewsEvent] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ts = _parse_ts(row.get("date"))
            if ts is None:
                continue
            out.append(
                NewsEvent(
                    timestamp=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
                    event_type=str(row.get("event", "economic") or "economic"),
                    impact=str(row.get("impact", "medium") or "medium").lower(),
                    country=str(row.get("country", "") or ""),
                )
            )
        return out
    except requests.RequestException as exc:
        logger.warning("birth.news.fmp_failed detail=%s", exc)
        return []


def _load_cache(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_cache(path: Path, events: list[NewsEvent]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "impact": e.impact,
                "country": e.country,
            }
            for e in events
        ]
        path.write_text(json.dumps(encoded, ensure_ascii=True, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("birth.news.cache_write_failed detail=%s", exc)


def _fetch_alpha_vantage(from_date: str, to_date: str, api_key: str) -> list[NewsEvent]:
    if not api_key:
        return []
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "topics": "economy_macro,financial_markets",
                "time_from": from_date.replace("-", "") + "T0000",
                "time_to": to_date.replace("-", "") + "T2359",
                "limit": 200,
                "apikey": api_key,
            },
            timeout=25,
        )
        if resp.status_code != 200:
            return []
        payload = resp.json()
        feed = payload.get("feed") if isinstance(payload, dict) else None
        if not isinstance(feed, list):
            return []
        out: list[NewsEvent] = []
        for row in feed:
            if not isinstance(row, dict):
                continue
            ts_raw = row.get("time_published")
            if not ts_raw:
                continue
            text = str(ts_raw).strip()
            if len(text) >= 15 and text[8] == "T":
                text = f"{text[:4]}-{text[4:6]}-{text[6:8]}T{text[9:11]}:{text[11:13]}:{text[13:15]}"
            ts = _parse_ts(text)
            if ts is None:
                continue
            topics = row.get("topics") or []
            event_type = "economic"
            if isinstance(topics, list) and topics:
                first = topics[0]
                if isinstance(first, dict):
                    event_type = str(first.get("topic", event_type))
            out.append(
                NewsEvent(
                    timestamp=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
                    event_type=event_type,
                    impact="medium",
                    country=str(row.get("source", "") or ""),
                )
            )
        return out
    except requests.RequestException as exc:
        logger.warning("birth.news.alpha_vantage_failed detail=%s", exc)
        return []


def fetch_economic_events(
    *,
    from_date: str,
    to_date: str,
    workspace_root: Path | str | None = None,
    primary: str = "finnhub",
    cache_path: str = "state/birth_news_cache.json",
    enable_cache: bool = True,
    finnhub_key: str | None = None,
    fmp_key: str | None = None,
    alpha_vantage_key: str | None = None,
) -> list[NewsEvent]:
    """Chain: Finnhub -> FMP -> Alpha Vantage -> cache -> empty."""
    root = Path(workspace_root or Path.cwd())
    cache_file = root / cache_path
    fh_key = finnhub_key or os.getenv("FINNHUB_API_KEY", "")
    fmp = fmp_key or os.getenv("FMP_API_KEY", "")
    av_key = alpha_vantage_key or os.getenv("ALPHA_VANTAGE_API_KEY", "")

    events: list[NewsEvent] = []
    if primary == "finnhub":
        events = _fetch_finnhub(from_date, to_date, fh_key)
    if not events:
        events = _fetch_fmp(from_date, to_date, fmp)
    if not events:
        events = _fetch_alpha_vantage(from_date, to_date, av_key)
    if not events and enable_cache:
        cached = _load_cache(cache_file)
        for row in cached:
            if not isinstance(row, dict):
                continue
            ts = _parse_ts(row.get("timestamp"))
            if ts is None:
                continue
            events.append(
                NewsEvent(
                    timestamp=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
                    event_type=str(row.get("event_type", "economic")),
                    impact=str(row.get("impact", "medium")),
                    country=str(row.get("country", "")),
                )
            )
    if events and enable_cache:
        _save_cache(cache_file, events)
    return events


def enrich_ticks_with_news(
    ticks: list[dict[str, Any]],
    *,
    workspace_root: Path | str | None = None,
    pre_minutes: int = 10,
    post_minutes: int = 5,
    primary: str = "finnhub",
    enable_cache: bool = True,
    cache_path: str = "state/birth_news_cache.json",
) -> list[dict[str, Any]]:
    """Attach news_window_active / news_event_type / news_impact to tick rows."""
    if not ticks:
        return ticks

    timestamps = [_tick_ts(t) for t in ticks]
    valid = [t for t in timestamps if t is not None]
    if not valid:
        return ticks

    start = min(valid)
    end = max(valid)
    events = fetch_economic_events(
        from_date=start.date().isoformat(),
        to_date=(end + timedelta(days=1)).date().isoformat(),
        workspace_root=workspace_root,
        primary=primary,
        enable_cache=enable_cache,
        cache_path=cache_path,
    )
    if not events:
        return ticks

    pre = timedelta(minutes=max(0, pre_minutes))
    post = timedelta(minutes=max(0, post_minutes))
    enriched: list[dict[str, Any]] = []
    for tick in ticks:
        row = dict(tick)
        ts = _tick_ts(row)
        if ts is None:
            enriched.append(row)
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        active = False
        matched_type = ""
        matched_impact = ""
        for ev in events:
            ev_ts = ev.timestamp if ev.timestamp.tzinfo else ev.timestamp.replace(tzinfo=timezone.utc)
            if (ev_ts - pre) <= ts <= (ev_ts + post):
                active = True
                matched_type = ev.event_type
                matched_impact = ev.impact
                break
        row["news_window_active"] = 1.0 if active else 0.0
        if active:
            row["news_event_type"] = matched_type
            row["news_impact"] = matched_impact
        enriched.append(row)
    return enriched
