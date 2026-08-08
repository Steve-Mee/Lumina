/** Lumina metrics types/constants (store/HUD residual). */

/** Canonical dashboard fields (normalized from `/api/monitoring/metrics/json`). */
export interface LuminaMetrics {
  trades_completed: number;
  training_completed_trades: number;
  training_target_trades: number;
  first_boot_stage: string;
  ppo_steps: number;
  ppo_timesteps_total: number;
  ppo_progress_pct: number;
  approval_twin_reward: number;
  cpu: number;
  gpu: number;
  ram: number;
  velocity: number;
  phase: string;
  historical_days: number;
  synthetic_percent: number;
  /** `null` when ETA is unknown/unavailable */
  eta_minutes: number | null;
  session_kind: string;
  session_active: boolean;
  training_target_applicable: boolean;
  last_activity_ts: string | null;
  activity_stale: boolean;
}

/** 1.8 seconden — interval voor automatische polling */
export const DEFAULT_POLLING_INTERVAL_MS = 1800;

export const DEFAULT_METRICS_ENDPOINT = "/api/monitoring/metrics/json";

/** Key used when reading `localStorage.getItem(...)`. Caller may set via UI or devtools */
export const DEFAULT_LUMINA_API_KEY_LS_KEY = "lumina_api_key";

export class LuminaMetricsFetchError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "LuminaMetricsFetchError";
    this.status = status;
  }
}

export const EMPTY_METRICS: LuminaMetrics = {
  trades_completed: 0,
  training_completed_trades: 0,
  training_target_trades: 0,
  first_boot_stage: "",
  ppo_steps: 0,
  ppo_timesteps_total: 0,
  ppo_progress_pct: 0,
  approval_twin_reward: 0,
  cpu: 0,
  gpu: 0,
  ram: 0,
  velocity: 0,
  phase: "",
  historical_days: 0,
  synthetic_percent: 0,
  eta_minutes: null,
  session_kind: "idle",
  session_active: false,
  training_target_applicable: false,
  last_activity_ts: null,
  activity_stale: true,
};
