# CANONICAL IMPLEMENTATION – v50 Living Organism
"""Observability service for Lumina v50 – real-time metrics + webhook alerts.

Tracks every critical trading-system metric:
  • Latency per agent layer (inference, market_data, reasoning, meta_reasoning)
  • Risk Controller status (kill-switch, daily PnL, consecutive losses)
  • Self-Evolution proposals + acceptance rate
  • PnL real-time vs valuation engine
  • Chaos events (websocket drops, API errors, latency breaches)
  • WebSocket health (connected, reconnects, heartbeat age)
  • Model confidence drift per agent

Alerts are dispatched via webhook (Discord / Slack / Telegram) with a
per-alert-type cooldown so paging storms are impossible.

Integration:
    obs = ObservabilityService.from_config(yaml_config_dict)
    obs.start()                               # launches background flush thread
    obs.record_latency("inference", 45.2)
    obs.record_risk_status(daily_pnl=-150.0, kill_switch=False, consecutive_losses=1)
    obs.stop()                                # flushes remaining SQLite rows

Zero-overhead when disabled:
    If monitoring.enabled = false, from_config() returns a service backed by
    NullMetricsCollector; all record_* calls are pure no-ops.

Recording helpers: ``observability_recorders``. This module keeps lifecycle + alerts.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .metrics_collector import MetricsCollector, NullMetricsCollector
from .observability_recorders import (  # noqa: F401 — public metric name re-exports
    M_ALERTS_SENT,
    M_BLACKBOARD_DROP_TOTAL,
    M_BLACKBOARD_PUBLISH_LATENCY,
    M_BLACKBOARD_REJECT_TOTAL,
    M_BLACKBOARD_SUBSCRIPTION_ERROR_TOTAL,
    M_CHAOS_EVENTS,
    M_EVOLUTION_ACCEPTANCE_RATE,
    M_EVOLUTION_ACCEPTANCES,
    M_EVOLUTION_LAST_CONFIDENCE,
    M_EVOLUTION_PROPOSALS,
    M_LATENCY,
    M_MODE_EOD_FORCE_CLOSE_TOTAL,
    M_MODE_GUARD_BLOCK_TOTAL,
    M_MODE_PARITY_DRIFT_TOTAL,
    M_MODEL_ABSTENTION_RATE,
    M_MODEL_ABSTENTIONS,
    M_MODEL_CONFIDENCE,
    M_MODEL_DECISIONS,
    M_MODEL_DRIFT,
    M_PNL_DAILY,
    M_PNL_TOTAL,
    M_PNL_UNREALIZED,
    M_PORTFOLIO_TOTAL_OPEN_RISK_USD,
    M_PORTFOLIO_VAR_LIMIT_USD,
    M_PORTFOLIO_VAR_USD,
    M_REGIME_CONFIDENCE,
    M_REGIME_CURRENT,
    M_REGIME_HIGH_RISK_OVERRIDES,
    M_REGIME_MEAN_PNL,
    M_REGIME_WINRATE,
    M_RESTARTS,
    M_RISK_CONSEC_LOSS,
    M_RISK_DAILY_PNL,
    M_RISK_KILL_SWITCH,
    M_UPTIME,
    M_WS_CONNECTED,
    M_WS_HEARTBEAT_AGE,
    M_WS_RECONNECTS,
    ObservabilityRecordersMixin,
)

logger = logging.getLogger("lumina.observability")


def _resolve_metrics_db_path(db_path_str: str) -> Path:
    """Resolve monitoring.db_path against LUMINA_STATE_DIR (absolute, cwd-independent).

    Relative ``state/...`` paths must not depend on process cwd (backend often
    starts in ``lumina_os/``), otherwise init and flush can hit different files.
    """
    rel = Path(db_path_str)
    if rel.is_absolute():
        return rel.resolve()
    env = os.getenv("LUMINA_STATE_DIR", "").strip()
    if env:
        parts = rel.parts
        if parts and parts[0] == "state":
            rest = Path(*parts[1:]) if len(parts) > 1 else Path()
            return (Path(env) / rest).resolve()
        return (Path(env) / rel).resolve()
    return (Path.cwd() / rel).resolve()


@dataclass
class AlertThresholds:
    latency_ms: float = 500.0
    daily_loss_usd: float = -800.0
    websocket_heartbeat_stale_s: float = 60.0
    model_confidence_drift: float = 0.25
    consecutive_losses: int = 3


@dataclass
class WebhookConfig:
    url: str = ""
    platform: str = "discord"  # "discord" | "slack" | "telegram"
    telegram_chat_id: str = ""
    enabled: bool = True
    timeout_s: float = 5.0


@dataclass(slots=True)
class ObservabilityService(ObservabilityRecordersMixin):
    """Central observability hub – metrics, alerts, Prometheus export."""

    collector: MetricsCollector | NullMetricsCollector
    thresholds: AlertThresholds
    webhook: WebhookConfig
    flush_interval_s: float = 30.0
    _started_at: float = field(default_factory=time.time)
    _bg_thread: threading.Thread | None = field(default=None)
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _alert_cooldown: dict[str, float] = field(default_factory=dict)
    _alert_cooldown_s: float = 120.0  # minimum gap between identical alerts
    _last_regime_labels: dict[str, str] | None = field(default=None)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ObservabilityService":
        """Construct from a parsed config.yaml dict.

        Returns a fully-configured service when monitoring.enabled = true,
        or a zero-overhead null-collector instance when disabled.
        """
        monitoring = config.get("monitoring", {})
        enabled = bool(monitoring.get("enabled", False))

        if not enabled:
            return cls(
                collector=NullMetricsCollector(),
                thresholds=AlertThresholds(),
                webhook=WebhookConfig(enabled=False),
            )

        db_path_str = monitoring.get("db_path", "state/metrics.db")
        db_path = _resolve_metrics_db_path(str(db_path_str)) if db_path_str else None
        collector: MetricsCollector | NullMetricsCollector = MetricsCollector(db_path=db_path)

        raw_thresh = monitoring.get("alert_thresholds", {})
        thresholds = AlertThresholds(
            latency_ms=float(raw_thresh.get("latency_ms", 500.0)),
            daily_loss_usd=float(raw_thresh.get("daily_loss_usd", -800.0)),
            websocket_heartbeat_stale_s=float(raw_thresh.get("websocket_heartbeat_stale_s", 60.0)),
            model_confidence_drift=float(raw_thresh.get("model_confidence_drift", 0.25)),
            consecutive_losses=int(raw_thresh.get("consecutive_losses", 3)),
        )

        raw_webhook = monitoring.get("webhook", {})
        webhook = WebhookConfig(
            url=str(raw_webhook.get("url", os.getenv("LUMINA_ALERT_WEBHOOK_URL", ""))),
            platform=str(raw_webhook.get("platform", "discord")),
            telegram_chat_id=str(raw_webhook.get("telegram_chat_id", "")),
            enabled=bool(raw_webhook.get("enabled", True)),
            timeout_s=float(raw_webhook.get("timeout_s", 5.0)),
        )

        flush_interval_s = float(monitoring.get("flush_interval_s", 30.0))
        return cls(
            collector=collector,
            thresholds=thresholds,
            webhook=webhook,
            flush_interval_s=flush_interval_s,
        )

    @classmethod
    def from_config_file(cls, path: str | Path = "config.yaml") -> "ObservabilityService":
        """Load config.yaml from disk and construct service."""
        with open(path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        return cls.from_config(cfg if isinstance(cfg, dict) else {})

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Launch the background flush + uptime-gauge thread (idempotent)."""
        if self._bg_thread is not None and self._bg_thread.is_alive():
            return
        self._stop_event.clear()
        self._bg_thread = threading.Thread(
            target=self._background_loop,
            daemon=True,
            name="lumina-obs",
        )
        self._bg_thread.start()
        logger.info("ObservabilityService started (flush_interval=%ss)", self.flush_interval_s)

    def stop(self) -> None:
        """Stop the background thread and flush remaining data to SQLite."""
        self._stop_event.set()
        if self._bg_thread is not None:
            self._bg_thread.join(timeout=5.0)
        self.collector.flush_to_sqlite()
        logger.info("ObservabilityService stopped")

    def _background_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.flush_interval_s)
            self.collector.set(
                M_UPTIME,
                time.time() - self._started_at,
                help_="Lumina process uptime in seconds",
            )
            self.collector.flush_to_sqlite()

    # ── Snapshot / export ─────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a full JSON-serialisable metrics snapshot."""
        data = self.collector.snapshot()
        data["_meta"] = {
            "uptime_s": round(time.time() - self._started_at, 1),
            "generated_at": time.time(),
        }
        return data

    def prometheus_text(self) -> str:
        """Return Prometheus text exposition format string."""
        return self.collector.prometheus_text()

    # ── Public alert API ──────────────────────────────────────────────────────

    def send_alert(
        self,
        *,
        title: str,
        message: str,
        severity: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Send a one-shot custom alert via webhook, bypassing per-type cooldown.

        Use this for human-triggered events (e.g. dashboard approve/reject)
        where every occurrence should always produce an alert.
        """
        # Unique key per call so the cooldown never suppresses these events
        alert_type = f"custom_{int(time.time() * 1000)}"
        self._fire_alert(
            alert_type=alert_type,
            title=title,
            message=message,
            severity=severity,
            data=data or {},
        )

    # ── Alerting internals ─────────────────────────────────────────────────────

    def _fire_alert(
        self,
        *,
        alert_type: str,
        title: str,
        message: str,
        severity: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch an alert via webhook with per-type cooldown enforcement."""
        now = time.time()
        last_sent = self._alert_cooldown.get(alert_type, 0.0)
        if now - last_sent < self._alert_cooldown_s:
            return  # within cooldown window – suppress duplicate

        self._alert_cooldown[alert_type] = now
        self.collector.inc(
            M_ALERTS_SENT,
            labels={"type": alert_type},
            help_="Total monitoring alerts dispatched",
        )

        logger.warning("[ALERT][%s] %s – %s", severity.upper(), title, message)

        self._maybe_attention_telegram(alert_type=alert_type, title=title, message=message, severity=severity)

        if not self.webhook.enabled or not self.webhook.url:
            return

        parsed = urllib.parse.urlparse(self.webhook.url)
        if parsed.scheme not in {"http", "https"}:
            logger.error("Webhook delivery blocked: unsupported URL scheme '%s'", parsed.scheme)
            return

        try:
            payload = self._build_webhook_payload(
                title=title,
                message=message,
                severity=severity,
                data=data or {},
            )
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook.url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.webhook.timeout_s) as resp:  # nosec B310
                if resp.status >= 400:
                    logger.error("Webhook delivery failed: HTTP %d", resp.status)
        except Exception as exc:
            logger.error("Webhook delivery error: %s", exc)

    def _maybe_attention_telegram(
        self,
        *,
        alert_type: str,
        title: str,
        message: str,
        severity: str,
    ) -> None:
        """Mirror critical observability alerts to Telegram attention channel."""
        try:
            from lumina_core.notifications.attention_events import (
                real_daily_loss_event,
                real_kill_switch_event,
                real_websocket_down_event,
            )
            from lumina_core.notifications.attention_notifier import notify_attention

            key = str(alert_type or "").strip().lower()
            event = None
            if "kill_switch" in key:
                event = real_kill_switch_event(detail=message)
            elif "daily_loss" in key:
                event = real_daily_loss_event(detail=message)
            elif "websocket" in key:
                event = real_websocket_down_event(detail=message)
            if event is None:
                return
            notify_attention(event)
        except Exception as exc:
            logger.debug("observability.attention_telegram_skipped: %s", exc)

    def _build_webhook_payload(
        self,
        *,
        title: str,
        message: str,
        severity: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a platform-specific webhook payload."""
        # Colour codes: red=critical, yellow=warning, blue=info
        colour_map = {"critical": 15158332, "warning": 16776960, "info": 3447003}
        colour = colour_map.get(severity, 8421504)

        if self.webhook.platform == "slack":
            return {
                "text": f"*{title}*",
                "attachments": [
                    {
                        "color": "danger" if severity == "critical" else "warning",
                        "text": message,
                        "footer": "Lumina v50 Observability",
                    }
                ],
            }

        if self.webhook.platform == "telegram":
            text = f"<b>{title}</b>\n{message}"
            if data:
                details = "\n".join(f"  {k}: {v}" for k, v in data.items())
                text += f"\n{details}"
            return {
                "chat_id": self.webhook.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
            }

        # Default: Discord embed format
        return {
            "embeds": [
                {
                    "title": title,
                    "description": message,
                    "color": colour,
                    "fields": [{"name": str(k), "value": str(v), "inline": True} for k, v in data.items()],
                    "footer": {"text": "Lumina v50 Observability"},
                }
            ]
        }
