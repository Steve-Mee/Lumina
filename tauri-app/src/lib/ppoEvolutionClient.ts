import type { PPOActionDistribution, PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

export const PPO_EVOLUTION_WS_URL = "ws://localhost:8000/ws/ppo-evolution";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseActionDistribution(value: unknown): PPOActionDistribution | null {
  if (!isRecord(value)) return null;
  const long = value.long;
  const short = value.short;
  const hold = value.hold;
  if (
    typeof long !== "number" ||
    typeof short !== "number" ||
    typeof hold !== "number"
  ) {
    return null;
  }
  return { long, short, hold };
}

export function resolvePpoEvolutionWsUrl(override?: string): string {
  if (override) {
    const wsBase = override.replace(/^http/, "ws").replace(/\/$/, "");
    if (wsBase.endsWith("/ws/ppo-evolution")) return wsBase;
    return `${wsBase}/ws/ppo-evolution`;
  }
  const envWs = import.meta.env.VITE_LUMINA_BACKEND_WS_URL;
  if (envWs) {
    const ws = envWs.replace(/\/ws\/core\/live\/?$/, "/ws/ppo-evolution");
    if (ws.endsWith("/ws/ppo-evolution")) return ws;
    return `${ws.replace(/\/$/, "")}/ws/ppo-evolution`;
  }
  const httpBase = import.meta.env.VITE_LUMINA_BACKEND_URL;
  if (httpBase) {
    return (
      httpBase.replace(/^http/, "ws").replace(/\/$/, "") + "/ws/ppo-evolution"
    );
  }
  return PPO_EVOLUTION_WS_URL;
}

export function parsePpoEvolutionLine(text: string): PPOEvolutionMetric | null {
  const trimmed = text.trim();
  if (!trimmed || trimmed === "pong") return null;

  let raw: unknown;
  try {
    raw = JSON.parse(trimmed);
  } catch {
    return null;
  }
  if (!isRecord(raw)) return null;

  const action_distribution = parseActionDistribution(raw.action_distribution);
  if (!action_distribution) return null;

  const requiredNumbers: Array<keyof PPOEvolutionMetric> = [
    "step",
    "mean_reward",
    "policy_loss",
    "value_loss",
    "entropy",
    "explained_variance",
    "winrate_rolling_5k",
    "sharpe_rolling_5k",
    "avg_stop_pct",
    "avg_target_pct",
  ];

  for (const key of requiredNumbers) {
    if (typeof raw[key] !== "number") return null;
  }
  if (typeof raw.timestamp !== "string") return null;

  return {
    timestamp: raw.timestamp,
    step: raw.step as number,
    mean_reward: raw.mean_reward as number,
    policy_loss: raw.policy_loss as number,
    value_loss: raw.value_loss as number,
    entropy: raw.entropy as number,
    explained_variance: raw.explained_variance as number,
    winrate_rolling_5k: raw.winrate_rolling_5k as number,
    sharpe_rolling_5k: raw.sharpe_rolling_5k as number,
    action_distribution,
    avg_stop_pct: raw.avg_stop_pct as number,
    avg_target_pct: raw.avg_target_pct as number,
  };
}
