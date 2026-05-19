import { deriveCitadelWalls } from "@/lib/riskCitadelMetrics";
import type { CoreStore, RiskLevel, TradingMode } from "@/store/coreStore";

export type DecisionVerdict = "proceed" | "caution" | "hold";

export interface ReasoningStep {
  id: string;
  title: string;
  body: string;
  confidence: number;
}

export interface DecisionMetrics {
  overallConfidence: number;
  kellyFraction: number;
  riskScore: number;
  regime: string;
}

export interface DecisionBrief {
  headline: string;
  verdict: DecisionVerdict;
  steps: ReasoningStep[];
  metrics: DecisionMetrics;
  proposalHash: string | null;
  lastUpdatedTs: string | null;
}

const RISK_SCORE: Record<RiskLevel, number> = {
  NORMAL: 92,
  ELEVATED: 74,
  HIGH: 52,
  CRITICAL: 28,
  UNKNOWN: 55,
};

function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value));
}

function deriveKellyFraction(state: CoreStore): number {
  const walls = deriveCitadelWalls(state);
  const kellyWall = walls.find((wall) => wall.id === "kelly");
  const raw = (kellyWall?.integrity ?? 72) / 100;
  if (state.operatorMode === "REAL") {
    return Math.min(raw, 0.25);
  }
  return clamp(raw, 0, 0.5);
}

function deriveOverallConfidence(state: CoreStore): number {
  const { liveMetrics } = state;
  const parts: number[] = [];

  if (liveMetrics.regimeConfidence !== null) {
    parts.push(liveMetrics.regimeConfidence);
  }
  if (liveMetrics.winrate !== null) {
    parts.push(liveMetrics.winrate);
  }

  if (parts.length === 0) {
    return 0.68;
  }

  return clamp(parts.reduce((sum, value) => sum + value, 0) / parts.length);
}

function deriveVerdict(
  riskLevel: RiskLevel,
  overallConfidence: number,
): DecisionVerdict {
  if (riskLevel === "CRITICAL" || riskLevel === "UNKNOWN") {
    return "hold";
  }
  if (riskLevel === "HIGH" || overallConfidence < 0.5) {
    return "caution";
  }
  if (
    (riskLevel === "NORMAL" || riskLevel === "ELEVATED") &&
    overallConfidence > 0.65
  ) {
    return "proceed";
  }
  return "caution";
}

function regimeBody(regime: string, confidence: number | null): string {
  const confidencePct =
    confidence !== null ? `${Math.round(confidence * 100)}%` : "standby estimate";
  return `Market classified as ${regime}. Regime detector confidence is ${confidencePct}, gating signal aggression and position sizing before execution.`;
}

function signalBody(winrate: number | null, confidence: number): string {
  if (winrate !== null) {
    return `Recent win-rate ${Math.round(winrate * 100)}% supports the current directional bias. Signal stack confidence aggregates to ${Math.round(confidence * 100)}% after noise filtering.`;
  }
  return `No fresh win-rate window yet — using regime confidence (${Math.round(confidence * 100)}%) as the primary signal quality proxy until more trades complete.`;
}

function kellyBody(kellyFraction: number, mode: TradingMode): string {
  const pct = Math.round(kellyFraction * 100);
  if (mode === "REAL") {
    return `Quarter-Kelly cap enforced in REAL mode. Effective sizing fraction: ${pct}% of theoretical optimum to preserve capital under variance.`;
  }
  return `Dynamic Kelly sizing recommends ${pct}% of theoretical optimum for SIM exploration while staying inside constitution bounds.`;
}

function riskBody(riskLevel: RiskLevel, riskScore: number): string {
  return `Constitutional risk posture: ${riskLevel}. Policy integrity score ${riskScore}/100 — gates order flow before any mutation or live deployment proceeds.`;
}

export function confidenceLabel(confidence: number): string {
  const pct = Math.round(confidence * 100);
  if (pct > 75) {
    return "High";
  }
  if (pct >= 50) {
    return "Moderate";
  }
  return "Low";
}

export function confidenceTone(
  confidence: number,
): "high" | "moderate" | "low" {
  const pct = confidence * 100;
  if (pct > 75) {
    return "high";
  }
  if (pct >= 50) {
    return "moderate";
  }
  return "low";
}

export function verdictLabel(verdict: DecisionVerdict): string {
  switch (verdict) {
    case "proceed":
      return "Proceed";
    case "caution":
      return "Caution";
    case "hold":
      return "Hold";
  }
}

export function verdictTone(verdict: DecisionVerdict): "high" | "moderate" | "low" {
  switch (verdict) {
    case "proceed":
      return "high";
    case "caution":
      return "moderate";
    case "hold":
      return "low";
  }
}

export function deriveDecisionBrief(state: CoreStore): DecisionBrief {
  const { liveMetrics, riskLevel, evolutionState, operatorMode } = state;
  const overallConfidence = deriveOverallConfidence(state);
  const kellyFraction = deriveKellyFraction(state);
  const riskScore = RISK_SCORE[riskLevel];
  const regimeConfidence =
    liveMetrics.regimeConfidence ?? overallConfidence;
  const proposalHash = evolutionState.activeMutations[0]?.hash ?? null;
  const verdict = deriveVerdict(riskLevel, overallConfidence);

  const steps: ReasoningStep[] = [
    {
      id: "regime",
      title: "Regime Analysis",
      body: regimeBody(liveMetrics.regime, liveMetrics.regimeConfidence),
      confidence: clamp(regimeConfidence),
    },
    {
      id: "signal",
      title: "Signal Confidence",
      body: signalBody(liveMetrics.winrate, overallConfidence),
      confidence: clamp(overallConfidence),
    },
    {
      id: "kelly",
      title: "Kelly Sizing",
      body: kellyBody(kellyFraction, operatorMode),
      confidence: clamp(kellyFraction / (operatorMode === "REAL" ? 0.25 : 0.5)),
    },
    {
      id: "risk",
      title: "Risk Calculation",
      body: riskBody(riskLevel, riskScore),
      confidence: clamp(riskScore / 100),
    },
  ];

  const headline =
    proposalHash !== null
      ? "Mutation proposal awaiting operator review"
      : liveMetrics.lastUpdatedTs
        ? "Live decision chain synchronized"
        : "Standby decision theater — awaiting telemetry";

  return {
    headline,
    verdict,
    steps,
    metrics: {
      overallConfidence,
      kellyFraction,
      riskScore,
      regime: liveMetrics.regime,
    },
    proposalHash,
    lastUpdatedTs: liveMetrics.lastUpdatedTs,
  };
}
