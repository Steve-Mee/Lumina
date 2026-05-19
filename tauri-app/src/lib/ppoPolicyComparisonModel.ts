import type { PPOActionDistribution, PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

const BIRTH_SNAPSHOT_SIZE = 5;

export interface PolicySnapshot {
  label: string;
  meanReward: number;
  entropy: number;
  winrate: number;
  sharpe: number;
  policyLoss: number;
  valueLoss: number;
  explainedVariance: number;
  actionDistribution: PPOActionDistribution;
}

export type PolicyComparisonMetricKey =
  | "meanReward"
  | "entropy"
  | "winrate"
  | "sharpe"
  | "policyLoss"
  | "valueLoss"
  | "explainedVariance";

export interface PolicyComparisonResult {
  birth: PolicySnapshot;
  current: PolicySnapshot;
  deltas: Record<PolicyComparisonMetricKey, number>;
}

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function averageActionDistribution(
  metrics: PPOEvolutionMetric[],
): PPOActionDistribution {
  if (metrics.length === 0) {
    return { long: 0, short: 0, hold: 0 };
  }

  const totals = metrics.reduce(
    (acc, metric) => ({
      long: acc.long + metric.action_distribution.long,
      short: acc.short + metric.action_distribution.short,
      hold: acc.hold + metric.action_distribution.hold,
    }),
    { long: 0, short: 0, hold: 0 },
  );

  const count = metrics.length;
  return {
    long: totals.long / count,
    short: totals.short / count,
    hold: totals.hold / count,
  };
}

function toSnapshot(label: string, metrics: PPOEvolutionMetric[]): PolicySnapshot {
  const latest = metrics[metrics.length - 1]!;

  if (metrics.length === 1) {
    return {
      label,
      meanReward: latest.mean_reward,
      entropy: latest.entropy,
      winrate: latest.winrate_rolling_5k,
      sharpe: latest.sharpe_rolling_5k,
      policyLoss: latest.policy_loss,
      valueLoss: latest.value_loss,
      explainedVariance: latest.explained_variance,
      actionDistribution: latest.action_distribution,
    };
  }

  return {
    label,
    meanReward: average(metrics.map((metric) => metric.mean_reward)),
    entropy: average(metrics.map((metric) => metric.entropy)),
    winrate: average(metrics.map((metric) => metric.winrate_rolling_5k)),
    sharpe: average(metrics.map((metric) => metric.sharpe_rolling_5k)),
    policyLoss: average(metrics.map((metric) => metric.policy_loss)),
    valueLoss: average(metrics.map((metric) => metric.value_loss)),
    explainedVariance: average(metrics.map((metric) => metric.explained_variance)),
    actionDistribution: averageActionDistribution(metrics),
  };
}

export function buildPolicyComparison(
  logs: PPOEvolutionMetric[],
): PolicyComparisonResult | null {
  if (logs.length < 2) return null;

  const birthMetrics = logs.slice(0, Math.min(BIRTH_SNAPSHOT_SIZE, logs.length));
  const birth = toSnapshot("Birth Policy", birthMetrics);
  const current = toSnapshot("Current Policy", [logs[logs.length - 1]!]);

  return {
    birth,
    current,
    deltas: {
      meanReward: current.meanReward - birth.meanReward,
      entropy: current.entropy - birth.entropy,
      winrate: current.winrate - birth.winrate,
      sharpe: current.sharpe - birth.sharpe,
      policyLoss: current.policyLoss - birth.policyLoss,
      valueLoss: current.valueLoss - birth.valueLoss,
      explainedVariance: current.explainedVariance - birth.explainedVariance,
    },
  };
}
