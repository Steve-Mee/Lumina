# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from xai_sdk import Client

from lumina_core.engine.agent_contracts import NewsInputSchema, NewsOutputSchema, enforce_contract
from lumina_core.engine.lumina_engine import LuminaEngine


def explain_news_agent_prompt() -> str:
    """Return the high-level contract for Lumina's hybrid NewsAgent behavior."""
    return (
        "Hybrid NewsAgent: combine X sentiment + web/economic news, compute sentiment score and "
        "dynamic risk multiplier, enforce high-impact avoidance windows, and fail safe to neutral."
    )


@dataclass(slots=True)
class NewsAgent:
    """Hybrid xAI-backed news/sentiment agent for Lumina.

    This agent augments the local Ollama/Qwen flow with lightweight external context:
    - X sentiment via x_semantic_search + x_keyword_search
    - High-impact macro/news scan via web_search + browse_page
    - 60-second cache to control latency/cost

    The component is fail-safe by design: on any xAI/tool/API issue it returns
    neutral sentiment, multiplier 1.0, and no forced avoidance unless explicit
    high-impact timing is known from the existing news schedule.
    """

    engine: LuminaEngine
    _last_update_dt: datetime | None = None
    _cached_result: dict[str, Any] = field(default_factory=dict)
    prompt_version: str = "news-agent-v1"

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

    @staticmethod
    def _safe_list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def _update_interval_seconds(self) -> int:
        raw = getattr(self.engine.config, "xai_update_interval_sec", 60)
        try:
            interval = int(raw)
        except (TypeError, ValueError):
            interval = 60
        return max(10, interval)

    def _news_avoidance_minutes(self) -> int:
        # Try new v51 configurable windows first
        pre = getattr(self.engine.config, "news_avoidance_pre_minutes", None)
        if pre is not None:
            try:
                return max(1, int(pre))
            except (TypeError, ValueError):
                pass

        # Fallback to legacy config
        raw = getattr(self.engine.config, "news_avoidance_minutes", 3)
        try:
            minutes = int(raw)
        except (TypeError, ValueError):
            minutes = 3
        return max(1, minutes)

    def _news_avoidance_post_minutes(self) -> int:
        """Post-event avoidance window (default 5 minutes)."""
        post = getattr(self.engine.config, "news_avoidance_post_minutes", 5)
        try:
            return max(1, int(post))
        except (TypeError, ValueError):
            return 5

    def _news_avoidance_high_impact_pre_minutes(self) -> int:
        """Pre-event window for high-impact events (default 15 minutes)."""
        pre = getattr(self.engine.config, "news_avoidance_high_impact_pre_minutes", 15)
        try:
            return max(1, int(pre))
        except (TypeError, ValueError):
            return 15

    def _news_avoidance_high_impact_post_minutes(self) -> int:
        """Post-event window for high-impact events (default 10 minutes)."""
        post = getattr(self.engine.config, "news_avoidance_high_impact_post_minutes", 10)
        try:
            return max(1, int(post))
        except (TypeError, ValueError):
            return 10

    def _xai_client(self) -> Client | None:
        api_key = (
            str(getattr(self.engine.config, "xai_key", "") or "").strip() or str(os.getenv("XAI_API_KEY", "")).strip()
        )
        if not api_key:
            return None
        try:
            return Client(api_key=api_key)
        except Exception:
            return None

    @staticmethod
    def _parse_event_time(event: dict[str, Any]) -> datetime | None:
        date_text = str(event.get("date", "")).strip()
        time_text = str(event.get("time", "")).strip()
        if not date_text:
            return None

        if not time_text or time_text.lower() in {"all day", "tentative", "nan", "none"}:
            time_text = "00:00"

        payload = f"{date_text} {time_text}".strip()
        candidate_formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
        ]
        for fmt in candidate_formats:
            try:
                dt_local = datetime.strptime(payload, fmt)
                return dt_local.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _compute_avoidance_window(self, events: list[dict[str, Any]], now_utc: datetime) -> tuple[bool, float, str]:
        keywords = {"fomc", "cpi", "nfp", "non-farm payroll", "powell", "fed", "pce", "ecb", "rate decision"}

        for event in events:
            if not isinstance(event, dict):
                continue
            event_name = str(event.get("event", "Unknown Event")).strip()
            impact = str(event.get("impact", "")).strip().lower()
            event_name_l = event_name.lower()
            is_high = impact in {"3", "high", "three", "3-star", "3_star"} or any(
                key in event_name_l for key in keywords
            )

            if not is_high:
                continue

            event_dt = self._parse_event_time(event)
            if event_dt is None:
                continue

            # Use different avoidance windows for high-impact vs normal events
            if is_high:
                avoid_pre_minutes = self._news_avoidance_high_impact_pre_minutes()
                avoid_post_minutes = self._news_avoidance_high_impact_post_minutes()
            else:
                avoid_pre_minutes = self._news_avoidance_minutes()
                avoid_post_minutes = self._news_avoidance_post_minutes()

            window_start = event_dt - timedelta(minutes=avoid_pre_minutes)
            window_end = event_dt + timedelta(minutes=avoid_post_minutes)
            if window_start <= now_utc <= window_end:
                return (
                    True,
                    window_end.timestamp(),
                    f"News avoidance window active: {event_name} (impact: {'high' if is_high else 'normal'})",
                )

        return False, 0.0, ""

    @staticmethod
    def _extract_text_from_xai_response(response: Any) -> str:
        if response is None:
            return ""
        for attr in ("output_text", "text", "content"):
            value = getattr(response, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(response, dict):
            for key in ("output_text", "text", "content"):
                value = response.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    def _call_xai(self, prompt: str) -> str:
        client = self._xai_client()
        if client is None:
            return ""

        model = str(getattr(self.engine.config, "xai_model", "grok-4.1-fast") or "grok-4.1-fast")
        tools = [
            {"type": "x_semantic_search"},
            {"type": "x_keyword_search"},
            {"type": "web_search"},
            {"type": "browse_page"},
        ]

        try:
            response_api = getattr(client, "responses", None)
            if response_api is None or not hasattr(response_api, "create"):
                return ""
            response = response_api.create(
                model=model,
                input=prompt,
                tools=tools,
                temperature=0.0,
            )
            return self._extract_text_from_xai_response(response)
        except Exception:
            return ""

    @staticmethod
    def _score_sentiment(signal: str, score: float) -> tuple[str, float]:
        signal_l = str(signal or "neutral").strip().lower()
        value = max(-1.0, min(1.0, float(score)))
        if signal_l not in {"bullish", "bearish", "neutral"}:
            if value > 0.15:
                signal_l = "bullish"
            elif value < -0.15:
                signal_l = "bearish"
            else:
                signal_l = "neutral"
        if signal_l == "bullish" and value < 0.0:
            value = abs(value)
        if signal_l == "bearish" and value > 0.0:
            value = -abs(value)
        if signal_l == "neutral":
            value = 0.0 if abs(value) < 0.15 else value
        return signal_l, round(value, 4)

    @staticmethod
    def _multiplier_from_sentiment(signal: str, score: float, high_impact: bool) -> float:
        intensity = abs(float(score))
        if signal == "bullish":
            base = 1.0 + (0.9 if high_impact else 0.4) * intensity
        elif signal == "bearish":
            base = 1.0 - (0.9 if high_impact else 0.4) * intensity
        else:
            base = 1.0
        return round(max(0.5, min(2.0, base)), 4)

    def _compose_prompt(self, schedule_events: list[dict[str, Any]]) -> str:
        return (
            "Analyze real-time futures macro context for MES/NQ risk. "
            "Use x_semantic_search and x_keyword_search for X sentiment, and web_search plus browse_page "
            "for high-impact headlines and economic calendar. "
            "Return strict JSON with keys: "
            "sentiment_signal (bullish/bearish/neutral), sentiment_score (-1..1), "
            "high_impact (bool), high_impact_events (list of strings), summary (string). "
            f"Known economic schedule events: {json.dumps(schedule_events[:12], ensure_ascii=False)}"
        )

    def _model_hash(self) -> str:
        raw = str(getattr(self.engine.config, "xai_model", "grok-4.1-fast") or "grok-4.1-fast")
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _log_decision(self, raw_input: dict[str, Any], raw_output: dict[str, Any], policy_outcome: str) -> None:
        decision_log = getattr(self.engine, "decision_log", None)
        if decision_log is None or not hasattr(decision_log, "log_decision"):
            return
        try:
            decision_log.log_decision(
                agent_id="NewsAgent",
                raw_input=raw_input,
                raw_output=raw_output,
                confidence=float(raw_output.get("confidence", 0.0) or 0.0),
                policy_outcome=policy_outcome,
                decision_context_id="news_cycle",
                model_version=str(getattr(self.engine.config, "xai_model", "grok-4.1-fast") or "grok-4.1-fast"),
                prompt_hash=hashlib.sha256(
                    json.dumps(raw_input, sort_keys=True, ensure_ascii=True).encode("utf-8")
                ).hexdigest(),
            )
        except Exception:
            return

    def _contract_input_payload(self) -> dict[str, Any]:
        app = self._app()
        news_data = self._safe_dict(app.get_high_impact_news())
        events = [e for e in self._safe_list(news_data.get("events")) if isinstance(e, dict)]
        return {
            "schedule_events_count": len(events),
            "xai_model": str(getattr(self.engine.config, "xai_model", "grok-4.1-fast") or "grok-4.1-fast"),
            "update_interval_seconds": self._update_interval_seconds(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @enforce_contract(
        NewsInputSchema,
        NewsOutputSchema,
        prompt_version="news-agent-v1",
        model_hash_getter=lambda self: self._model_hash(),
        input_builder=lambda self, _args, _kwargs: self._contract_input_payload(),
    )
    def run_news_cycle(self) -> dict[str, Any]:
        app = self._app()
        now_utc = datetime.now(timezone.utc)
        interval = self._update_interval_seconds()

        if self._last_update_dt is not None and self._cached_result:
            age_seconds = (now_utc - self._last_update_dt).total_seconds()
            if age_seconds < interval:
                return dict(self._cached_result)

        news_data = self._safe_dict(app.get_high_impact_news())
        events = [e for e in self._safe_list(news_data.get("events")) if isinstance(e, dict)]

        sentiment_signal = "neutral"
        sentiment_score = 0.0
        high_impact = False
        high_impact_events: list[str] = []
        summary = "xAI unavailable; fallback neutral sentiment"
        fallback_level = 0
        fallback_reason_code = "xai_live"

        cache_ttl_seconds = max(interval * 5, 300)

        prompt = self._compose_prompt(events)
        raw_text = self._call_xai(prompt)
        if raw_text:
            try:
                parsed = json.loads(raw_text)
                sentiment_signal, sentiment_score = self._score_sentiment(
                    str(parsed.get("sentiment_signal", "neutral")),
                    float(parsed.get("sentiment_score", 0.0)),
                )
                high_impact = bool(parsed.get("high_impact", False))
                high_impact_events = [
                    str(item) for item in self._safe_list(parsed.get("high_impact_events")) if str(item).strip()
                ]
                summary = str(parsed.get("summary", "")).strip() or "xAI sentiment cycle"
            except Exception:
                fallback_level = 1
                fallback_reason_code = "xai_parse_failed"
                summary = "xAI response parse failed; fallback neutral sentiment"
        else:
            fallback_level = 1
            fallback_reason_code = "xai_unavailable"

        if fallback_level > 0 and self._last_update_dt is not None and self._cached_result:
            age_seconds = (now_utc - self._last_update_dt).total_seconds()
            if age_seconds <= cache_ttl_seconds:
                cached = dict(self._cached_result)
                cached["last_update"] = now_utc.isoformat()
                cached["fallback_level"] = 2
                cached["fallback_reason_code"] = "cache_reuse_within_ttl"
                cached["cache_age_seconds"] = round(float(age_seconds), 3)
                self._cached_result = dict(cached)
                self._last_update_dt = now_utc
                return cached

        if fallback_level > 0 and events:
            high_tokens = {"fomc", "cpi", "nfp", "powell", "fed", "pce", "rate"}
            for event in events:
                name = str(event.get("event", "")).lower()
                impact = str(event.get("impact", "")).lower()
                if impact in {"3", "high"} or any(token in name for token in high_tokens):
                    high_impact = True
                    high_impact_events.append(str(event.get("event", "High impact event")))
            if high_impact:
                summary = "Fallback to schedule-derived macro risk context"
                fallback_level = 3
                fallback_reason_code = "schedule_heuristic"

        avoid, hold_until_ts, avoid_reason = self._compute_avoidance_window(events, now_utc)
        if high_impact and not avoid and high_impact_events:
            for event_name in high_impact_events:
                if any(token in event_name.lower() for token in ("fomc", "cpi", "nfp", "powell", "fed", "pce")):
                    avoid = True
                    hold_until_ts = (now_utc + timedelta(minutes=self._news_avoidance_minutes())).timestamp()
                    avoid_reason = f"News avoidance window active: {event_name}"
                    break

        multiplier = self._multiplier_from_sentiment(sentiment_signal, sentiment_score, high_impact)
        confidence = min(1.0, max(0.0, abs(float(sentiment_score)) + (0.1 if high_impact else 0.0)))

        result = {
            "news_data": news_data,
            "sentiment_signal": sentiment_signal,
            "sentiment_score": sentiment_score,
            "high_impact": bool(high_impact),
            "high_impact_events": high_impact_events,
            "summary": summary,
            "dynamic_multiplier": multiplier,
            "dynamic_multipliers": dict(getattr(self.engine.config, "news_impact_multipliers", {})),
            "news_avoidance_window": bool(avoid),
            "news_avoidance_hold_until_ts": float(hold_until_ts),
            "news_avoidance_reason": avoid_reason,
            "last_update": now_utc.isoformat(),
            "confidence": round(float(confidence), 4),
            "fallback_level": int(fallback_level),
            "fallback_reason_code": str(fallback_reason_code),
            "cache_ttl_seconds": int(cache_ttl_seconds),
        }

        macro = (
            self._safe_dict(getattr(app, "world_model", {}).get("macro", {}))
            if isinstance(getattr(app, "world_model", {}), dict)
            else {}
        )
        macro["news_sentiment"] = sentiment_signal
        macro["news_sentiment_score"] = sentiment_score
        macro["news_multiplier"] = multiplier
        macro["news_last_update"] = result["last_update"]
        macro["news_summary"] = summary
        if isinstance(getattr(app, "world_model", {}), dict):
            app.world_model.setdefault("macro", {})
            app.world_model["macro"].update(macro)

        app.logger.info(
            "NEWS_CYCLE,"
            f"sentiment={sentiment_signal},"
            f"score={sentiment_score:.3f},"
            f"multiplier={multiplier:.3f},"
            f"avoid={str(bool(avoid)).lower()}"
        )

        self._last_update_dt = now_utc
        self._cached_result = dict(result)
        blackboard = getattr(self.engine, "blackboard", None)
        if blackboard is not None and hasattr(blackboard, "add_proposal"):
            try:
                current_dream = self.engine.get_current_dream_snapshot()
                blackboard.add_proposal(
                    topic="agent.news.proposal",
                    producer="news_agent",
                    payload={
                        "news_impact": float(multiplier),
                        "news_sentiment": sentiment_signal,
                        "news_sentiment_score": float(sentiment_score),
                        "hold_until_ts": float(hold_until_ts) if bool(avoid) else 0.0,
                        "why_no_trade": avoid_reason if bool(avoid) else "",
                        "signal": "HOLD" if bool(avoid) else str(current_dream.get("signal", "")),
                    },
                    confidence=round(float(confidence), 4),
                )
            except Exception:
                pass
        self._log_decision(
            raw_input={"prompt": prompt, "events": events, "news_data": news_data},
            raw_output=result,
            policy_outcome="news_cycle_success",
        )
        return dict(result)

    def run_cycle(self) -> dict[str, Any]:
        """Backward-compatible alias for existing runtime call sites."""
        return self.run_news_cycle()
