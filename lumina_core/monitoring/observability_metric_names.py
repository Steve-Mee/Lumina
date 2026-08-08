"""Prometheus metric name constants for observability (M5)."""
from __future__ import annotations

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

__all__ = [
    "M_LATENCY",
    "M_RISK_KILL_SWITCH",
    "M_RISK_DAILY_PNL",
    "M_RISK_CONSEC_LOSS",
    "M_PORTFOLIO_VAR_USD",
    "M_PORTFOLIO_VAR_LIMIT_USD",
    "M_PORTFOLIO_TOTAL_OPEN_RISK_USD",
    "M_EVOLUTION_PROPOSALS",
    "M_EVOLUTION_ACCEPTANCES",
    "M_EVOLUTION_ACCEPTANCE_RATE",
    "M_EVOLUTION_LAST_CONFIDENCE",
    "M_PNL_DAILY",
    "M_PNL_UNREALIZED",
    "M_PNL_TOTAL",
    "M_CHAOS_EVENTS",
    "M_WS_CONNECTED",
    "M_WS_RECONNECTS",
    "M_WS_HEARTBEAT_AGE",
    "M_MODEL_CONFIDENCE",
    "M_MODEL_DRIFT",
    "M_MODEL_ABSTENTIONS",
    "M_MODEL_DECISIONS",
    "M_MODEL_ABSTENTION_RATE",
    "M_REGIME_CURRENT",
    "M_REGIME_CONFIDENCE",
    "M_REGIME_HIGH_RISK_OVERRIDES",
    "M_REGIME_WINRATE",
    "M_REGIME_MEAN_PNL",
    "M_ALERTS_SENT",
    "M_UPTIME",
    "M_RESTARTS",
    "M_MODE_GUARD_BLOCK_TOTAL",
    "M_MODE_EOD_FORCE_CLOSE_TOTAL",
    "M_MODE_PARITY_DRIFT_TOTAL",
    "M_BLACKBOARD_PUBLISH_LATENCY",
    "M_BLACKBOARD_REJECT_TOTAL",
    "M_BLACKBOARD_DROP_TOTAL",
    "M_BLACKBOARD_SUBSCRIPTION_ERROR_TOTAL",
]
