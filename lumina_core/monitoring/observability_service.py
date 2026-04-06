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
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .metrics_collector import MetricsCollector, NullMetricsCollector

logger = logging.getLogger("lumina.observability")

# ── Prometheus metric name constants ──────────────────────────────────────────
M_LATENCY = "lumina_latency_ms"
M_RISK_KILL_SWITCH = "lumina_risk_kill_switch_active"
M_RISK_DAILY_PNL = "lumina_risk_daily_pnl"
M_RISK_CONSEC_LOSS = "lumina_risk_consecutive_losses"
M_EVOLUTION_PROPOSALS = "lumina_evolution_proposals_total"
M_EVOLUTION_ACCEPTANCES = "lumina_evolution_acceptances_total"
M_EVOLUTION_ACCEPTANCE_RATE = "lumina_evolution_acceptance_rate"
M_EVOLUTION_LAST_CONFIDENCE = "lumina_evolution_last_confidence"
M_PNL_DAILY = "lumina_pnl_daily"
M_PNL_UNREALIZED = "lumina_pnl_unrealized"
M_PNL_TOTAL = "lumina_pnl_total"
M_CHAOS_EVENTS = "lumina_chaos_events_total"
M_WS_CONNECTED = "lumina_websocket_connected"
M_WS_RECONNECTS = "lumina_websocket_reconnects_total"
M_WS_HEARTBEAT_AGE = "lumina_websocket_last_heartbeat_age_s"
M_MODEL_CONFIDENCE = "lumina_model_confidence"
M_MODEL_DRIFT = "lumina_model_confidence_drift"
M_ALERTS_SENT = "lumina_alerts_sent_total"
M_UPTIME = "lumina_uptime_seconds"
M_RESTARTS = "lumina_process_restarts_total"


# ── Configuration sub-objects ──────────────────────────────────────────────────


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


# ── Main service ───────────────────────────────────────────────────────────────


@dataclass(slots=True)
class ObservabilityService:
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

    # ── Factory ───────────────────────────────────────────────────────────────

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
        db_path = Path(db_path_str) if db_path_str else None
        collector: MetricsCollector | NullMetricsCollector = MetricsCollector(db_path=db_path)

        raw_thresh = monitoring.get("alert_thresholds", {})
        thresholds = AlertThresholds(
            latency_ms=float(raw_thresh.get("latency_ms", 500.0)),
            daily_loss_usd=float(raw_thresh.get("daily_loss_usd", -800.0)),
            websocket_heartbeat_stale_s=float(
                raw_thresh.get("websocket_heartbeat_stale_s", 60.0)
            ),
            model_confidence_drift=float(
                raw_thresh.get("model_confidence_drift", 0.25)
            ),
            consecutive_losses=int(raw_thresh.get("consecutive_losses", 3)),
        )

        raw_webhook = monitoring.get("webhook", {})
        webhook = WebhookConfig(
            url=str(
                raw_webhook.get("url", os.getenv("LUMINA_ALERT_WEBHOOK_URL", ""))
            ),
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
        logger.info(
            "ObservabilityService started (flush_interval=%ss)", self.flush_interval_s
        )

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

    # ── Recording API ──────────────────────────────────────────────────────────

    def record_latency(self, source: str, elapsed_ms: float) -> None:
        """Record per-layer latency; alert if SLA threshold exceeded."""
        self.collector.observe(
            M_LATENCY,
            elapsed_ms,
            labels={"source": source},
            help_="Agent layer latency in milliseconds",
        )
        if elapsed_ms > self.thresholds.latency_ms:
            self._fire_alert(
                alert_type=f"latency_{source}",
                title=f"High Latency: {source}",
                message=(
                    f"{source} latency = {elapsed_ms:.1f} ms "
                    f"(threshold: {self.thresholds.latency_ms:.0f} ms)"
                ),
                severity="warning",
                data={"source": source, "elapsed_ms": elapsed_ms},
            )

    def record_risk_status(
        self,
        *,
        daily_pnl: float,
        kill_switch: bool,
        consecutive_losses: int,
    ) -> None:
        """Record risk-controller state; alert on kill-switch and loss thresholds."""
        self.collector.set(M_RISK_DAILY_PNL, daily_pnl, help_="Current daily PnL (USD)")
        self.collector.set(
            M_RISK_KILL_SWITCH,
            float(kill_switch),
            help_="Kill-switch active: 1 = yes, 0 = no",
        )
        self.collector.set(
            M_RISK_CONSEC_LOSS,
            float(consecutive_losses),
            help_="Consecutive losing trades",
        )

        if kill_switch:
            self._fire_alert(
                alert_type="kill_switch",
                title="KILL SWITCH ENGAGED",
                message=f"Risk controller kill-switch is ACTIVE. Daily PnL: ${daily_pnl:.2f}",
                severity="critical",
                data={"daily_pnl": daily_pnl, "consecutive_losses": consecutive_losses},
            )
        elif daily_pnl < self.thresholds.daily_loss_usd:
            self._fire_alert(
                alert_type="daily_loss",
                title="Daily Loss Threshold Breached",
                message=(
                    f"Daily PnL ${daily_pnl:.2f} below "
                    f"threshold ${self.thresholds.daily_loss_usd:.2f}"
                ),
                severity="warning",
                data={"daily_pnl": daily_pnl},
            )

        if consecutive_losses >= self.thresholds.consecutive_losses:
            self._fire_alert(
                alert_type="consecutive_losses",
                title=f"Loss Streak: {consecutive_losses} consecutive losses",
                message=f"Risk controller: {consecutive_losses} consecutive losing trades",
                severity="warning",
                data={"consecutive_losses": consecutive_losses},
            )

    def record_evolution_proposal(
        self,
        *,
        status: str,
        confidence: float,
        best_candidate: str | None = None,
    ) -> None:
        """Record a nightly self-evolution proposal to metrics."""
        self.collector.inc(
            M_EVOLUTION_PROPOSALS, help_="Total self-evolution proposals generated"
        )
        self.collector.set(
            M_EVOLUTION_LAST_CONFIDENCE,
            confidence,
            help_="Last evolution proposal confidence score",
        )
        if status in ("applied", "auto_applied"):
            self.collector.inc(
                M_EVOLUTION_ACCEPTANCES,
                help_="Total self-evolution proposals accepted/applied",
            )

        total_proposals = self.collector.get(M_EVOLUTION_PROPOSALS)
        total_acceptances = self.collector.get(M_EVOLUTION_ACCEPTANCES)
        acceptance_rate = (
            float(total_acceptances / total_proposals) if total_proposals > 0 else 0.0
        )
        self.collector.set(
            M_EVOLUTION_ACCEPTANCE_RATE,
            acceptance_rate,
            help_="Self-evolution proposal acceptance rate (0–1)",
        )

        logger.info(
            "Evolution proposal recorded: status=%s confidence=%.1f "
            "candidate=%s acceptance_rate=%.2f",
            status,
            confidence,
            best_candidate or "none",
            acceptance_rate,
        )

    def record_pnl(
        self,
        *,
        daily: float,
        unrealized: float = 0.0,
        total: float = 0.0,
    ) -> None:
        """Record real-time PnL gauges."""
        self.collector.set(M_PNL_DAILY, daily, help_="Daily realized PnL (USD)")
        self.collector.set(M_PNL_UNREALIZED, unrealized, help_="Unrealized PnL (USD)")
        self.collector.set(M_PNL_TOTAL, total, help_="Cumulative total PnL (USD)")

    def record_chaos_event(self, event_type: str) -> None:
        """Increment chaos-event counter for a given event type."""
        self.collector.inc(
            M_CHAOS_EVENTS,
            labels={"type": event_type},
            help_="Total chaos events observed",
        )
        logger.warning("Chaos event recorded: %s", event_type)

    def record_websocket_status(
        self,
        *,
        connected: bool,
        reconnects: int = 0,
    ) -> None:
        """Record WebSocket connection health."""
        self.collector.set(
            M_WS_CONNECTED, float(connected), help_="WebSocket connected: 1=yes 0=no"
        )
        if reconnects > 0:
            self.collector.inc(
                M_WS_RECONNECTS,
                amount=float(reconnects),
                help_="Total WebSocket reconnection attempts",
            )
        if not connected:
            self._fire_alert(
                alert_type="websocket_down",
                title="WebSocket Disconnected",
                message="Market data WebSocket is disconnected",
                severity="critical",
                data={"reconnects": reconnects},
            )

    def record_websocket_heartbeat_age(self, age_s: float) -> None:
        """Record seconds since the last WebSocket heartbeat."""
        self.collector.set(
            M_WS_HEARTBEAT_AGE,
            age_s,
            help_="Seconds since last WebSocket heartbeat",
        )
        if age_s > self.thresholds.websocket_heartbeat_stale_s:
            self._fire_alert(
                alert_type="websocket_stale",
                title="WebSocket Heartbeat Stale",
                message=(
                    f"No WebSocket heartbeat for {age_s:.0f} s "
                    f"(threshold: {self.thresholds.websocket_heartbeat_stale_s:.0f} s)"
                ),
                severity="warning",
                data={"heartbeat_age_s": age_s},
            )

    def record_model_confidence(self, agent: str, confidence: float) -> None:
        """Track model confidence per agent; fire alert on significant drift."""
        self.collector.observe(
            M_MODEL_CONFIDENCE,
            confidence,
            labels={"agent": agent},
            help_="Model confidence score per agent (0–1)",
        )
        mean_conf = self.collector.get(M_MODEL_CONFIDENCE, labels={"agent": agent})
        if mean_conf > 0:
            drift = abs(confidence - mean_conf) / max(mean_conf, 0.01)
            self.collector.set(
                M_MODEL_DRIFT,
                drift,
                labels={"agent": agent},
                help_="Model confidence drift relative to running mean",
            )
            if drift > self.thresholds.model_confidence_drift:
                self._fire_alert(
                    alert_type=f"confidence_drift_{agent}",
                    title=f"Model Confidence Drift: {agent}",
                    message=(
                        f"{agent} drift={drift:.3f} "
                        f"(threshold: {self.thresholds.model_confidence_drift:.2f}), "
                        f"current={confidence:.3f}"
                    ),
                    severity="warning",
                    data={"agent": agent, "confidence": confidence, "drift": drift},
                )

    def record_process_restart(self) -> None:
        """Increment the process-restart counter (used by watchdog)."""
        self.collector.inc(
            M_RESTARTS, help_="Total supervised process restarts by watchdog"
        )

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

        if not self.webhook.enabled or not self.webhook.url:
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
            with urllib.request.urlopen(req, timeout=self.webhook.timeout_s) as resp:
                if resp.status >= 400:
                    logger.error("Webhook delivery failed: HTTP %d", resp.status)
        except Exception as exc:
            logger.error("Webhook delivery error: %s", exc)

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
                    "fields": [
                        {"name": str(k), "value": str(v), "inline": True}
                        for k, v in data.items()
                    ],
                    "footer": {"text": "Lumina v50 Observability"},
                }
            ]
        }
