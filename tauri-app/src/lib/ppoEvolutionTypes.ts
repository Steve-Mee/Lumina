export interface PPOActionDistribution {
  long: number;
  short: number;
  hold: number;
}

export interface PPOEvolutionMetric {
  timestamp: string;
  step: number;
  mean_reward: number;
  policy_loss: number;
  value_loss: number;
  entropy: number;
  explained_variance: number;
  winrate_rolling_5k: number;
  sharpe_rolling_5k: number;
  action_distribution: PPOActionDistribution;
  avg_stop_pct: number;
  avg_target_pct: number;
}

export type PPOEvolutionConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export const PPO_EVOLUTION_MAX_POINTS = 200;
