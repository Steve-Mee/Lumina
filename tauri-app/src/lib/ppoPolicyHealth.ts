import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

export type PolicyHealthStatus = "healthy" | "watch" | "critical";

export interface PolicyHealthMetric {
  value: number;
  status: PolicyHealthStatus;
}

export interface PolicyHealthSnapshot {
  policyLoss: PolicyHealthMetric;
  valueLoss: PolicyHealthMetric;
  explainedVariance: PolicyHealthMetric;
}

function evaluateLoss(value: number, healthyMax: number, watchMax: number): PolicyHealthStatus {
  if (value < healthyMax) return "healthy";
  if (value < watchMax) return "watch";
  return "critical";
}

function evaluateExplainedVariance(value: number): PolicyHealthStatus {
  if (value >= 0.7) return "healthy";
  if (value >= 0.4) return "watch";
  return "critical";
}

export function evaluatePolicyHealth(metric: PPOEvolutionMetric): PolicyHealthSnapshot {
  return {
    policyLoss: {
      value: metric.policy_loss,
      status: evaluateLoss(metric.policy_loss, 0.05, 0.15),
    },
    valueLoss: {
      value: metric.value_loss,
      status: evaluateLoss(metric.value_loss, 0.1, 0.3),
    },
    explainedVariance: {
      value: metric.explained_variance,
      status: evaluateExplainedVariance(metric.explained_variance),
    },
  };
}

export const POLICY_HEALTH_STATUS_LABEL: Record<PolicyHealthStatus, string> = {
  healthy: "Healthy",
  watch: "Watch",
  critical: "Critical",
};
