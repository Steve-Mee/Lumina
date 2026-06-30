/** Streamlit help_texts.py parity for Command Deck tooltips. */
export const HELP_TEXTS: Record<string, string> = {
  dashboard_enabled: "Enables dashboard-oriented feedback paths in the engine.",
  runtime_trace: "Writes extra runtime trace events for diagnosis in logs.",
  runtime_trace_interval: "Throttle for repetitive runtime trace lines (seconds).",
  latency_sla: "SLA threshold (ms) for fast-path decisions under high latency.",
  training_trades: "Curriculum trade budget cap (progress display); completion requires Birth Certificate v2 OOS metrics.",
  max_real_days:
    "Maximum calendar days of real historical data to load. Auto-linked to training trades (~450 trades/day heuristic; backend max 3650 days).",
  prefer_real_data_only: "Certified birth requires real market data (≥95% in certificate).",
  birth_certificate: "OOS winrate, Sharpe, drawdown and zero constitution violations required for deck access.",
  require_real_simulator_data: "Require NinjaTrader/Crosstrade simulator data before training.",
  allow_minimal_synthetic_fallback:
    "When real data is unavailable, allow a minimal synthetic top-up for practice mode only.",
  genesis_maturity_charter:
    "Genesis is the pre-birth contract: set birth training goals and see what REAL maturity requires later.",
  stage1_winrate_gate:
    "Stage 1 pipeline pass threshold (35–45%). Lower values validate the pipeline; REAL still needs certificate OOS ≥48% + Evolution Proof.",
  maturity_ladder:
    "Six growth phases from genesis contract to REAL capital: Birth → Awakening → Playground → Apprenticeship → Proving Ground → REAL.",
  evolution_proof:
    "Post-birth gate: winrate lift ≥5% vs birth exit or polish OOS ≥45% on ≥500 trades.",
  certificate_oos: "Birth Certificate v2 holdout winrate must be ≥48% for deck and REAL eligibility.",
  pause_live_trading:
    "Stops trading immediately and attempts to flatten/cancel open orders. May realize loss in fast markets.",
};

export function helpFor(key: string): string | undefined {
  return HELP_TEXTS[key];
}
