"""Observability metric recording helpers (Wave B2 PR-C0).

Canonical surface: ``ObservabilityService`` in ``observability_service``.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("lumina.observability")

# ── Prometheus metric name constants ──────────────────────────────────────────
M_LATENCY = "lumina_latency_ms"
M_RISK_KILL_SWITCH = "lumina_risk_kill_switch_active"
M_RISK_DAILY_PNL = "lumina_risk_daily_pnl"
M_RISK_CONSEC_LOSS = "lumina_risk_consecutive_losses"
M_PORTFOLIO_VAR_USD = "lumina_portfolio_var_usd"
M_PORTFOLIO_VAR_LIMIT_USD = "lumina_portfolio_var_limit_usd"
M_PORTFOLIO_TOTAL_OPEN_RISK_USD = "lumina_portfolio_total_open_risk_usd"
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
M_MODEL_ABSTENTIONS = "lumina_model_abstentions_total"
M_MODEL_DECISIONS = "lumina_model_decisions_total"
M_MODEL_ABSTENTION_RATE = "lumina_model_abstention_rate"
M_REGIME_CURRENT = "lumina_regime_current"
M_REGIME_CONFIDENCE = "lumina_regime_confidence"
M_REGIME_HIGH_RISK_OVERRIDES = "lumina_regime_high_risk_overrides_total"
M_REGIME_WINRATE = "lumina_regime_winrate"
M_REGIME_MEAN_PNL = "lumina_regime_mean_pnl"
M_ALERTS_SENT = "lumina_alerts_sent_total"
M_UPTIME = "lumina_uptime_seconds"
M_RESTARTS = "lumina_process_restarts_total"
M_MODE_GUARD_BLOCK_TOTAL = "lumina_mode_guard_block_total"
M_MODE_EOD_FORCE_CLOSE_TOTAL = "lumina_mode_eod_force_close_total"
M_MODE_PARITY_DRIFT_TOTAL = "lumina_mode_parity_drift_total"
M_BLACKBOARD_PUBLISH_LATENCY = "lumina_blackboard_publish_latency_ms"
M_BLACKBOARD_REJECT_TOTAL = "lumina_blackboard_reject_total"
M_BLACKBOARD_DROP_TOTAL = "lumina_blackboard_drop_total"
M_BLACKBOARD_SUBSCRIPTION_ERROR_TOTAL = "lumina_blackboard_subscription_error_total"


class ObservabilityRecordersMixin:
    """record_* API for ``ObservabilityService``."""

    __slots__ = ()

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
                message=(f"{source} latency = {elapsed_ms:.1f} ms (threshold: {self.thresholds.latency_ms:.0f} ms)"),
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
                message=(f"Daily PnL ${daily_pnl:.2f} below threshold ${self.thresholds.daily_loss_usd:.2f}"),
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
        self.collector.inc(M_EVOLUTION_PROPOSALS, help_="Total self-evolution proposals generated")
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
        acceptance_rate = float(total_acceptances / total_proposals) if total_proposals > 0 else 0.0
        self.collector.set(
            M_EVOLUTION_ACCEPTANCE_RATE,
            acceptance_rate,
            help_="Self-evolution proposal acceptance rate (0–1)",
        )

        logger.info(
            "Evolution proposal recorded: status=%s confidence=%.1f candidate=%s acceptance_rate=%.2f",
            status,
            confidence,
            best_candidate or "none",
            acceptance_rate,
        )

    def record_portfolio_var(
        self,
        *,
        var_usd: float,
        max_var_usd: float,
        total_open_risk: float,
        breached: bool,
        method: str,
        confidence: float,
        symbols: list[str],
    ) -> None:
        labels = {
            "method": str(method).lower(),
            "confidence": f"{float(confidence):.2f}",
        }
        if symbols:
            labels["symbols"] = ",".join(sorted(str(s).upper() for s in symbols))

        self.collector.set(
            M_PORTFOLIO_VAR_USD,
            float(var_usd),
            labels=labels,
            help_="Portfolio one-day VaR estimate in USD",
        )
        self.collector.set(
            M_PORTFOLIO_VAR_LIMIT_USD,
            float(max_var_usd),
            labels=labels,
            help_="Configured maximum allowed portfolio VaR in USD",
        )
        self.collector.set(
            M_PORTFOLIO_TOTAL_OPEN_RISK_USD,
            float(total_open_risk),
            labels=labels,
            help_="Current total open risk across instruments in USD",
        )

        if bool(breached):
            self._fire_alert(
                alert_type="portfolio_var_breach",
                title="Portfolio VaR Breach",
                message=(f"Portfolio VaR ${float(var_usd):.2f} exceeds limit ${float(max_var_usd):.2f}"),
                severity="critical",
                data={
                    "var_usd": round(float(var_usd), 2),
                    "max_var_usd": round(float(max_var_usd), 2),
                    "total_open_risk": round(float(total_open_risk), 2),
                    "method": str(method).lower(),
                    "confidence": round(float(confidence), 2),
                },
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
        self.collector.set(M_WS_CONNECTED, float(connected), help_="WebSocket connected: 1=yes 0=no")
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

    def record_model_decision(self, *, agent: str, abstained: bool) -> None:
        labels = {"agent": str(agent)}
        self.collector.inc(
            M_MODEL_DECISIONS,
            labels=labels,
            help_="Total model decisions per agent",
        )
        if bool(abstained):
            self.collector.inc(
                M_MODEL_ABSTENTIONS,
                labels=labels,
                help_="Total model abstentions per agent",
            )

        decisions = float(self.collector.get(M_MODEL_DECISIONS, labels=labels))
        abstentions = float(self.collector.get(M_MODEL_ABSTENTIONS, labels=labels))
        rate = abstentions / decisions if decisions > 0 else 0.0
        self.collector.set(
            M_MODEL_ABSTENTION_RATE,
            rate,
            labels=labels,
            help_="Model abstention rate per agent",
        )

    def record_regime_performance(self, *, regime: str, pnl: float, won: bool) -> None:
        regime_key = str(regime or "NEUTRAL").upper()
        labels = {"regime": regime_key}
        self.collector.observe(
            M_REGIME_MEAN_PNL,
            float(pnl),
            labels=labels,
            help_="Average realized pnl per closed trade by regime",
        )
        self.collector.observe(
            M_REGIME_WINRATE,
            1.0 if bool(won) else 0.0,
            labels=labels,
            help_="Winrate proxy per regime (running mean of wins)",
        )

    def record_regime_state(
        self,
        *,
        regime: str,
        confidence: float,
        risk_state: str = "NORMAL",
        fast_path_weight: float | None = None,
        high_risk_override: bool = False,
    ) -> None:
        """Track the currently active regime and any high-risk override activations."""
        normalized_regime = str(regime or "NEUTRAL").upper()
        normalized_risk_state = str(risk_state or "NORMAL").upper()
        labels = {"regime": normalized_regime, "risk_state": normalized_risk_state}

        if self._last_regime_labels and self._last_regime_labels != labels:
            self.collector.set(
                M_REGIME_CURRENT,
                0.0,
                labels=self._last_regime_labels,
                help_="Current active regime state (1=active, 0=inactive)",
            )

        self.collector.set(
            M_REGIME_CURRENT,
            1.0,
            labels=labels,
            help_="Current active regime state (1=active, 0=inactive)",
        )
        self.collector.set(
            M_REGIME_CONFIDENCE,
            confidence,
            labels={"regime": normalized_regime},
            help_="Confidence score for the currently detected regime",
        )
        if fast_path_weight is not None:
            self.collector.set(
                "lumina_regime_fast_path_weight",
                float(fast_path_weight),
                labels={"regime": normalized_regime},
                help_="Adaptive fast-path weight for the detected regime",
            )
        if high_risk_override:
            self.collector.inc(
                M_REGIME_HIGH_RISK_OVERRIDES,
                labels={"regime": normalized_regime},
                help_="Total high-risk regime overrides applied to the risk controller",
            )
        self._last_regime_labels = labels

    def record_process_restart(self) -> None:
        """Increment the process-restart counter (used by watchdog)."""
        self.collector.inc(M_RESTARTS, help_="Total supervised process restarts by watchdog")

    def record_mode_guard_block(self, *, mode: str, reason: str) -> None:
        self.collector.inc(
            M_MODE_GUARD_BLOCK_TOTAL,
            labels={"mode": str(mode).lower(), "reason": str(reason).lower()},
            help_="Total pre-trade guard rejections by mode and reason",
        )

    def record_mode_eod_force_close(self, *, mode: str) -> None:
        self.collector.inc(
            M_MODE_EOD_FORCE_CLOSE_TOTAL,
            labels={"mode": str(mode).lower()},
            help_="Total EOD force-close activations by mode",
        )

    def record_mode_parity_drift(self, *, baseline: str, candidate: str, delta: float) -> None:
        self.collector.inc(
            M_MODE_PARITY_DRIFT_TOTAL,
            amount=float(abs(delta)),
            labels={"baseline": str(baseline).lower(), "candidate": str(candidate).lower()},
            help_="Accumulated mode parity drift (absolute delta)",
        )

    def record_blackboard_publish(self, *, topic: str, producer: str, elapsed_ms: float) -> None:
        self.collector.observe(
            M_BLACKBOARD_PUBLISH_LATENCY,
            float(elapsed_ms),
            labels={"topic": str(topic).lower(), "producer": str(producer).lower()},
            help_="Blackboard publish latency in milliseconds",
        )

    def record_blackboard_reject(self, *, topic: str, producer: str, reason: str) -> None:
        self.collector.inc(
            M_BLACKBOARD_REJECT_TOTAL,
            labels={"topic": str(topic).lower(), "producer": str(producer).lower(), "reason": str(reason).lower()},
            help_="Total rejected blackboard events",
        )

    def record_blackboard_drop(self, *, topic: str, producer: str, reason: str, critical: bool) -> None:
        self.collector.inc(
            M_BLACKBOARD_DROP_TOTAL,
            labels={
                "topic": str(topic).lower(),
                "producer": str(producer).lower(),
                "reason": str(reason).lower(),
                "critical": str(bool(critical)).lower(),
            },
            help_="Total dropped blackboard events due to backpressure",
        )

    def record_blackboard_subscription_error(self, *, topic: str, producer: str) -> None:
        self.collector.inc(
            M_BLACKBOARD_SUBSCRIPTION_ERROR_TOTAL,
            labels={"topic": str(topic).lower(), "producer": str(producer).lower()},
            help_="Total blackboard subscriber callback errors",
        )
