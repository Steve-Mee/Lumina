/** Streamlit help_texts.py parity + Command Deck / Setup tooltips. */
export const HELP_TEXTS: Record<string, string> = {
  dashboard_enabled: "Enables dashboard-oriented feedback paths in the engine.",
  runtime_trace: "Writes extra runtime trace events for diagnosis in logs.",
  runtime_trace_interval: "Throttle for repetitive runtime trace lines (seconds).",
  latency_sla: "SLA threshold (ms) for fast-path decisions under high latency.",
  training_trades:
    "Global Birth trade budget (ceiling), not a hardware IQ score. Sweet/beast stay at the YAML cap; a faster PC trains the same budget quicker. Stages pass on process-R floors (150/250/400/100/50), not by consuming this cap. Birth exit is five process-R receipts + fitness vector, not a WR exam.",
  max_real_days:
    "Expand ceiling for Birth history (default 365). First load is Foundation 90 calendar days. 180 then 365 only on stall / death-spiral / certificate — not at start. Not linked to the trade budget.",
  prefer_real_data_only: "Certified birth requires real market data (≥95% in certificate).",
  birth_certificate:
    "Proving Ground / certificate pipeline: OOS winrate, Sharpe, drawdown. Not Birth Foundation exit — deck unlocks after Foundation five-of-five + later Playground gates.",
  require_real_simulator_data: "Require NinjaTrader/Crosstrade simulator data before training.",
  allow_minimal_synthetic_fallback:
    "When real data is unavailable, allow a minimal synthetic top-up for practice mode only.",
  genesis_maturity_charter:
    "Genesis is the pre-birth contract: the trade budget is a ceiling, Birth grades process-R, and REAL needs the later ladder (Awakening → Playground first-contact in NT SIM → Apprenticeship → Proving Ground).",
  stage1_winrate_gate:
    "Birth Foundation grades the plant (median loss R, occupancy, first-touch), not a 35–45% WR exam. Profit (WR ≥ geometry BE, mean R ≥ 0) is Playground on NT SIM tape. Certificate OOS 48% is Proving Ground.",
  maturity_ladder:
    "Growth phases from wiring to live capital: Setup → Genesis → Birth → Awakening → Playground → Apprenticeship → Proving Ground → REAL.",
  evolution_proof:
    "Post-birth gate: winrate lift ≥5% vs birth exit or polish OOS ≥45% on ≥500 trades.",
  certificate_oos:
    "Proving Ground wall: OOS WR ≥48%, Sharpe ≥0.35, DD ≤8% on the proving exam tape. Birth certificate JSON is not pass. Human approve-real is REAL.",
  pause_live_trading:
    "Stops trading immediately and attempts to flatten/cancel open orders. May realize loss in fast markets.",

  // ── Configuration / Risk Envelope ──────────────────────────────────────
  config_target_mode:
    "Target operations mode saved to config.yaml. This is your intended post-birth profile — not the live Birth runtime (Birth is always SIM, fail-closed).",
  config_paper:
    "Broker paper / practice account path. No real capital. Useful for broker-side dry runs. Evolution defaults are moderate — safer than full SIM radical exploration.",
  config_sim:
    "Internal simulation (recommended first-boot target). No live orders. Loose risk is fine for learning. Never mirror a loose SIM envelope straight into REAL.",
  config_real:
    "Live capital target. Constitution enforces tighter caps: quarter-Kelly (≤0.25), daily loss hard stop required, low max open risk, radical mutations blocked, operator approval required. Confirm only if you understand capital is at risk after maturity gates pass.",
  config_sim_real_guard:
    "SIM with REAL-like capital guards. Still no live capital — extra brakes for practicing under tighter risk. Good rehearsal before REAL.",
  config_birth_sim_runtime:
    "During Birth Phase the engine runtime is always SIM (fail-closed). Values on this page set your target profile for after Birth — they do not place live orders now.",
  config_envelope_summary:
    "Live snapshot of your sealed profile: mode, Kelly, daily cap, open risk ceiling, mutation depth, and approval gate.",
  kelly_fraction:
    "Share of theoretical Kelly used for position sizing. 1.0 = full Kelly (aggressive growth, faster drawdowns). REAL constitution hard-caps at ≤ 0.25 (quarter-Kelly). Higher Kelly = larger size and steeper loss paths when wrong.",
  daily_loss_cap:
    "Hard stop on realized day PnL (negative USD). None = no daily kill-switch (acceptable in SIM for exploration). REAL requires an active negative cap — without it a bad day can run unchecked until other limits fire.",
  max_total_open_risk:
    "Ceiling on combined open risk across positions (USD). Too high = too much simultaneous exposure. REAL presets drop this sharply so one bad cluster cannot compound.",
  real_capital_safety_threshold:
    "Minimum equity buffer the system treats as a safety floor before REAL capital paths are considered viable. Below this, fail-closed behavior should keep live capital dark.",
  aggressive_evolution:
    "Faster / deeper hyperparameter exploration. Fine in SIM for learning speed. Not recommended for REAL — increases policy instability and surprise behavior.",
  max_mutation_depth:
    "How far DNA mutations may drift. Conservative = small steps. Moderate = balanced. Radical = deep mutations (SIM only). Constitution blocks radical depth in REAL.",
  approval_required:
    "When on, mutations wait for human approve/reject in Decision Theater and Evolution deck. Off = faster auto path (weaker human-in-the-loop). REAL preset forces approval on.",
  config_instrument:
    "CME futures root (MES/MNQ recommended). Birth history uses the liquid front-month (volume roll ~8 days before the 3rd Friday) and stitches prior quarterlies. A YAML listing like MES SEP26 is resolved — Lumina must not train a thin next-quarter book as if it were the liquid tape.",
  cuda_gloss:
    "CUDA is the way an NVIDIA graphics card does heavy math. LUMINA uses it to practise trades.",
  vllm_gloss:
    "vLLM is an optional extra-fast talking server. It is not the thing that learns to trade.",
  ollama_gloss: "Ollama is a small local talking program. Safe to run next to learning.",
  xai_gloss: "Cloud brain. Best for reading live news. Needs a key. Does not learn trades by itself.",
  force_high_tier:
    "Picks a larger local talking model if memory allows. Never unlocks REAL. Never installs vLLM on Windows. May be slow.",
  organs_lungs: "How LUMINA learns trades. Detected, not chosen. No checkbox.",
  organs_voice: "How LUMINA reads and explains. Optional. Not needed to start learning.",
  config_voice_enabled: "Enable TTS and voice input on the operator deck. No capital impact.",
  config_screen_share: "Live chart screen-share path for operator context. No capital impact.",
};

export function helpFor(key: string): string | undefined {
  return HELP_TEXTS[key];
}

/** One-line consequence hints for risk envelope controls (UI, not tooltips). */
export const CONSEQUENCE_HINTS: Record<string, string> = {
  kelly_high: "High Kelly → larger size and deeper drawdowns when the edge is wrong.",
  kelly_real_safe: "Within REAL quarter-Kelly envelope (≤0.25).",
  kelly_real_hot: "Above REAL constitution cap (0.25) — will be blocked or unsafe live.",
  daily_none: "No daily kill-switch — a bad day can run until other limits fire.",
  daily_on: "Daily hard stop armed — trading halts when the day PnL hits this floor.",
  open_risk_high: "High open risk — simultaneous positions can stack losses fast.",
  open_risk_tight: "Tight open-risk ceiling — limits clustered exposure.",
  capital_floor: "Equity buffer floor for REAL readiness. Under it, stay fail-closed.",
  radical_sim: "Deep mutations allowed — SIM learning only; never for live capital.",
  radical_blocked: "Radical depth blocked in REAL by constitution.",
  approval_off: "Mutations may apply without human gate — faster, less operator control.",
  approval_on: "Human gate on — you approve mutations before they stick.",
  birth_sim: "Birth runtime stays SIM regardless of this target.",
  real_target:
    "REAL target: capital at risk only after maturity gates — envelope is deliberately tight.",
  sim_loose: "Loose SIM envelope — excellent for learning; do not copy into REAL.",
  paper_path: "Paper path — no real capital; still treat size and risk as practice discipline.",
};
