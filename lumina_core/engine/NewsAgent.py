from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class NewsAgent:
    """Builds a news/sentiment layer for the world model and risk gating."""

    engine: LuminaEngine

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("NewsAgent requires a LuminaEngine")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    @staticmethod
    def _safe_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _try_tool_call(self, tool_name: str, query: str) -> Any:
        app = self._app()
        fn = getattr(app, tool_name, None)
        if not callable(fn):
            return None
        try:
            return fn(query)
        except TypeError:
            # Some wrappers may accept keyword payloads.
            try:
                return fn({"query": query})
            except Exception:
                return None
        except Exception:
            return None

    def _parse_event_time(self, event: dict[str, Any]) -> datetime | None:
        date_text = str(event.get("date", "")).strip()
        time_text = str(event.get("time", "")).strip()
        if not date_text:
            return None

        if not time_text or time_text.lower() in {"all day", "tentative", "nan", "none"}:
            time_text = "00:00"

        candidate_formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
        ]
        payload = f"{date_text} {time_text}".strip()
        for fmt in candidate_formats:
            try:
                return datetime.strptime(payload, fmt)
            except ValueError:
                continue
        return None

    def _compute_news_avoidance_window(self, news_data: dict[str, Any], now: datetime) -> tuple[bool, float, str]:
        events = news_data.get("events", []) if isinstance(news_data, dict) else []
        if not isinstance(events, list):
            return False, 0.0, ""

        for event in events:
            if not isinstance(event, dict):
                continue
            impact = str(event.get("impact", "")).strip().lower()
            event_name = str(event.get("event", "Unknown Event")).strip()
            is_three_star = impact in {"3", "high", "three", "3-star", "3_star"}
            if not is_three_star:
                continue

            event_dt = self._parse_event_time(event)
            if event_dt is None:
                continue

            window_start = event_dt - timedelta(minutes=3)
            window_end = event_dt + timedelta(minutes=3)
            if window_start <= now <= window_end:
                return True, window_end.timestamp(), f"3-star news window active: {event_name}"

        return False, 0.0, ""

    def _dynamic_multipliers(self, news_data: dict[str, Any], sentiment_signal: str) -> dict[str, float]:
        base = dict(self.engine.config.news_impact_multipliers)
        impact = str(news_data.get("impact", "medium")).lower()
        sentiment = str(news_data.get("overall_sentiment", sentiment_signal or "neutral")).lower()

        if impact == "high":
            if sentiment == "bullish":
                base["high_bullish"] = min(1.6, base.get("high_bullish", 1.3) + 0.1)
                base["high_bearish"] = max(0.5, base.get("high_bearish", 0.6) - 0.05)
            elif sentiment == "bearish":
                base["high_bearish"] = max(0.45, base.get("high_bearish", 0.6) - 0.1)
                base["high_bullish"] = max(1.0, base.get("high_bullish", 1.3) - 0.05)
            else:
                base["high_neutral"] = max(0.8, min(1.0, base.get("high_neutral", 0.9)))
        else:
            # Keep medium settings close to baseline with small adaptive drift.
            if sentiment == "bullish":
                base["medium_bullish"] = min(1.25, base.get("medium_bullish", 1.1) + 0.03)
            elif sentiment == "bearish":
                base["medium_bearish"] = max(0.8, base.get("medium_bearish", 0.9) - 0.03)

        return base

    def run_cycle(self) -> dict[str, Any]:
        """Run one news/sentiment cycle.

        Uses x_semantic_search + web_search + browse_page if runtime exposes them,
        then updates multipliers and returns avoidance-window metadata.
        """
        app = self._app()
        now = datetime.now()

        # Existing feed remains authoritative for event schedule.
        news_data = self._safe_dict(app.get_high_impact_news())

        semantic = self._try_tool_call(
            "x_semantic_search",
            "MES futures macro catalysts sentiment risk events next 2 hours",
        )
        web = self._try_tool_call(
            "web_search",
            "high impact economic calendar today FOMC CPI NFP risk-on risk-off",
        )

        # Try to browse one discovered URL if present.
        browse = None
        if isinstance(web, dict):
            urls = web.get("urls") or web.get("links") or []
            if isinstance(urls, list) and urls:
                browse = self._try_tool_call("browse_page", str(urls[0]))

        sentiment_signal = str(news_data.get("overall_sentiment", "neutral"))
        if isinstance(semantic, dict):
            sentiment_signal = str(semantic.get("overall_sentiment", sentiment_signal))

        dynamic = self._dynamic_multipliers(news_data, sentiment_signal)
        avoid, hold_until_ts, reason = self._compute_news_avoidance_window(news_data, now)

        return {
            "news_data": news_data,
            "semantic": semantic,
            "web": web,
            "browse": browse,
            "dynamic_multipliers": dynamic,
            "news_avoidance_window": avoid,
            "news_avoidance_hold_until_ts": hold_until_ts,
            "news_avoidance_reason": reason,
            "last_update": now.isoformat(),
        }
