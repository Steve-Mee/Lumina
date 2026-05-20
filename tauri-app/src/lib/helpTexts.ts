/** Streamlit help_texts.py parity for Command Deck tooltips. */
export const HELP_TEXTS: Record<string, string> = {
  dashboard_enabled: "Enables dashboard-oriented feedback paths in the engine.",
  runtime_trace: "Writes extra runtime trace events for diagnosis in logs.",
  runtime_trace_interval: "Throttle for repetitive runtime trace lines (seconds).",
  latency_sla: "SLA threshold (ms) for fast-path decisions under high latency.",
  training_trades: "Target number of SIM trades during birth phase training.",
  max_real_days: "Maximum calendar days of real historical data to load.",
  prefer_real_data_only: "Prefer real market data; synthetic only if allowed fallback is on.",
  require_real_simulator_data: "Require NinjaTrader/Crosstrade simulator data before training.",
  pause_live_trading:
    "Stops trading immediately and attempts to flatten/cancel open orders. May realize loss in fast markets.",
};

export function helpFor(key: string): string | undefined {
  return HELP_TEXTS[key];
}
