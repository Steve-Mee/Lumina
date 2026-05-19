import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

export interface WhatIfControls {
  entropyLevel: number;
  riskAversion: number;
}

export interface WhatIfPrediction {
  expectedReward: number;
  expectedSharpe: number;
  confidence: number;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

export function predictWhatIf(
  baseline: PPOEvolutionMetric,
  controls: WhatIfControls,
): WhatIfPrediction {
  const entropyFactor = (controls.entropyLevel - 50) / 100;
  const riskFactor = (controls.riskAversion - 50) / 100;

  const expectedReward =
    baseline.mean_reward * (1 + 0.18 * entropyFactor) * (1 - 0.12 * riskFactor);
  const expectedSharpe =
    baseline.sharpe_rolling_5k * (1 + 0.1 * entropyFactor) * (1 - 0.15 * riskFactor);

  return {
    expectedReward,
    expectedSharpe,
    confidence: clamp01(baseline.explained_variance),
  };
}
