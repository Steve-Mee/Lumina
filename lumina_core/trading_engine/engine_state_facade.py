from __future__ import annotations

from typing import Any


STATE_PROXY_MAP: dict[str, tuple[str, str, bool]] = {
    "regime_history": ("memory_state", "regime_history", True),
    "narrative_memory": ("memory_state", "narrative_memory", True),
    "memory_buffer": ("memory_state", "memory_buffer", True),
    "trade_reflection_history": ("memory_state", "trade_reflection_history", True),
    "pnl_history": ("performance_state", "pnl_history", True),
    "equity_curve": ("performance_state", "equity_curve", True),
    "trade_log": ("performance_state", "trade_log", True),
    "performance_log": ("performance_state", "performance_log", True),
    "sim_position_qty": ("position_state", "sim_position_qty", True),
    "sim_entry_price": ("position_state", "sim_entry_price", True),
    "sim_unrealized": ("position_state", "sim_unrealized", True),
    "sim_peak": ("position_state", "sim_peak", True),
    "live_position_qty": ("position_state", "live_position_qty", True),
    "last_entry_price": ("position_state", "last_entry_price", True),
    "last_realized_pnl_snapshot": ("position_state", "last_realized_pnl_snapshot", True),
    "live_trade_signal": ("position_state", "live_trade_signal", True),
    "pending_trade_reconciliations": ("position_state", "pending_trade_reconciliations", True),
    "account_balance": ("account_state", "account_balance", True),
    "account_equity": ("account_state", "account_equity", True),
    "realized_pnl_today": ("account_state", "realized_pnl_today", True),
    "open_pnl": ("account_state", "open_pnl", True),
    "available_margin": ("account_state", "available_margin", True),
    "positions_margin_used": ("account_state", "positions_margin_used", True),
    "equity_snapshot_ok": ("account_state", "equity_snapshot_ok", True),
    "equity_snapshot_reason": ("account_state", "equity_snapshot_reason", True),
    "admission_chain_final_arbitration_approved": ("account_state", "admission_chain_final_arbitration_approved", True),
    "ohlc_1min": ("market_data", "ohlc_1min", True),
    "live_quotes": ("market_data", "live_quotes", True),
    "live_data_lock": ("market_data", "live_data_lock", False),
    "current_candle": ("market_data", "current_candle", True),
    "candle_start_ts": ("market_data", "candle_start_ts", True),
    "prev_volume_cum": ("market_data", "prev_volume_cum", True),
    "cost_tracker": ("runtime_counters", "cost_tracker", True),
    "rate_limit_backoff_seconds": ("runtime_counters", "rate_limit_backoff_seconds", True),
    "restart_count": ("runtime_counters", "restart_count", True),
    "dashboard_last_chart_ts": ("runtime_counters", "dashboard_last_chart_ts", True),
    "dashboard_last_has_image": ("runtime_counters", "dashboard_last_has_image", True),
}

SERVICE_PROXY_FIELDS: tuple[str, ...] = (
    "local_engine",
    "fast_path",
    "backtester",
    "advanced_backtester",
    "rl_env",
    "ppo_trainer",
    "risk_controller",
    "risk_policy",
    "final_arbitration",
    "equity_snapshot_provider",
    "infinite_simulator",
    "emotional_twin",
    "emotional_twin_agent",
    "swarm",
    "validator",
    "observability_service",
    "session_guard",
    "portfolio_var_allocator",
    "decision_log",
    "audit_log_service",
    "reasoning_service",
    "blackboard",
    "event_bus",
    "meta_agent_orchestrator",
    "market_data_service",
    "memory_service",
    "operations_service",
    "analysis_service",
    "dashboard_service",
    "visualization_service",
    "reporting_service",
    "trade_reconciler",
    "dynamic_kelly_estimator",
    "regime_detector",
)


def _build_nested_proxy(owner: str, nested: str, writable: bool) -> property:
    def getter(self):
        return getattr(getattr(self, owner), nested)

    if not writable:
        return property(getter)

    def setter(self, value):
        setattr(getattr(self, owner), nested, value)

    return property(getter, setter)


def _build_service_proxy(name: str) -> property:
    def getter(self):
        return getattr(self.services, name)

    def setter(self, value):
        setattr(self.services, name, value)

    return property(getter, setter)


def install_lumina_engine_state_facade(engine_cls: type[Any]) -> None:
    for public_name, (owner, nested, writable) in STATE_PROXY_MAP.items():
        setattr(engine_cls, public_name, _build_nested_proxy(owner, nested, writable))
    for field_name in SERVICE_PROXY_FIELDS:
        setattr(engine_cls, field_name, _build_service_proxy(field_name))
