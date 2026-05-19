import type { PPOActionDistribution } from "@/lib/ppoEvolutionTypes";

export interface ActionDistributionSegment {
  key: "long" | "short" | "hold";
  name: string;
  value: number;
  percent: number;
  fill: string;
}

export const ACTION_DISTRIBUTION_COLORS = {
  long: "#22d3ee",
  short: "#a78bfa",
  hold: "#64748b",
} as const;

const ACTION_LABELS: Record<ActionDistributionSegment["key"], string> = {
  long: "Long",
  short: "Short",
  hold: "Hold",
};

export function mapActionDistributionToChartData(
  distribution: PPOActionDistribution,
): ActionDistributionSegment[] {
  const entries: Array<ActionDistributionSegment["key"]> = ["long", "short", "hold"];

  return entries.map((key) => ({
    key,
    name: ACTION_LABELS[key],
    value: distribution[key],
    percent: Math.round(distribution[key] * 100),
    fill: ACTION_DISTRIBUTION_COLORS[key],
  }));
}

export function dominantActionSegment(
  segments: ActionDistributionSegment[],
): ActionDistributionSegment {
  return segments.reduce((best, current) =>
    current.value > best.value ? current : best,
  );
}
