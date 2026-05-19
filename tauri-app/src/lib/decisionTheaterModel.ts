import { deriveCitadelWalls } from "@/lib/riskCitadelMetrics";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
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
  const { liveMetrics, tradingLive } = state;
  const parts: number[] = [];

  if (tradingLive?.active_signal.confidence) {
    parts.push(tradingLive.active_signal.confidence);
  }
  if (liveMetrics.regimeConfidence !== null) {
    parts.push(liveMetrics.regimeConfidence);
  }
  if (liveMetrics.winrate !== null) {
    parts.push(liveMetrics.winrate);
  }

  if (parts.length === 0) return 0;
  return clamp(parts.reduce((sum, value) => sum + value, 0) / parts.length);
}

function deriveVerdict(riskLevel: RiskLevel, overallConfidence: number): DecisionVerdict {
  if (riskLevel === "CRITICAL" || riskLevel === "UNKNOWN") return "hold";
  if (riskLevel === "HIGH" || overallConfidence < 0.5) return "caution";
  if ((riskLevel === "NORMAL" || riskLevel === "ELEVATED") && overallConfidence > 0.65) {
    return "proceed";
  }
  return "caution";
}

export function buildReasoningSteps(
  tradingLive: LiveTradingSnapshot | null,
  regime: string,
  riskLevel: RiskLevel,
  operatorMode: TradingMode,
  kellyFraction: number,
): ReasoningStep[] {
  if (!tradingLive) {
    return [
      {
        id: "standby",
        title: "Awaiting live trading telemetry",
        body: "Connect to core live stream to see regime, signal, and risk reasoning.",
        confidence: 0,
      },
    ];
  }

  const signal = tradingLive.active_signal;
  const position = tradingLive.position;
  const regimeConf = tradingLive.regime_confidence;
  const riskScore = RISK_SCORE[riskLevel];

  const steps: ReasoningStep[] = [
    {
      id: "regime",
      title: "Regime Analysis",
      body: `Market classified as ${regime}. Regime detector confidence ${Math.round(regimeConf * 100)}% gates signal aggression before execution.`,
      confidence: clamp(regimeConf),
    },
    {
      id: "signal",
      title: "Signal Decision",
      body:
        signal.reason ||
        `Active signal ${signal.signal} with ${Math.round(signal.confidence * 100)}% model confidence.`,
      confidence: clamp(signal.confidence),
    },
    {
      id: "confluence",
      title: "Confluence & Levels",
      body: `Confluence ${Math.round(signal.confluence * 100)}% · Strategy ${signal.strategy || "unknown"} · Entry ${position.entry_price.toFixed(2)} · Stop ${signal.stop.toFixed(2)} · Target ${signal.target.toFixed(2)}`,
      confidence: clamp(signal.confluence),
    },
    {
      id: "risk",
      title: "Risk Posture",
      body: `Daily PnL ${position.daily_pnl.toFixed(2)} · Open PnL ${position.open_pnl.toFixed(2)} · Consecutive losses ${tradingLive.consecutive_losses} · Constitutional risk ${riskLevel} (${riskScore}/100).`,
      confidence: clamp(riskScore / 100),
    },
  ];

  const policyBody =
    signal.signal === "HOLD" && signal.why_no_trade
      ? signal.why_no_trade
      : tradingLive.latest_decision?.policy_outcome
        ? `${tradingLive.latest_decision.policy_outcome}${tradingLive.latest_decision.output_summary ? ` — ${tradingLive.latest_decision.output_summary}` : ""}`
        : `Kelly sizing ${Math.round(kellyFraction * 100)}% (${operatorMode} mode cap applied).`;

  steps.push({
    id: "policy",
    title: "Policy Outcome",
    body: policyBody,
    confidence: clamp(tradingLive.latest_decision?.confidence ?? signal.confidence),
  });

  return steps;
}

export function buildDecisionHeadline(
  tradingLive: LiveTradingSnapshot | null,
  proposalHash: string | null,
  lastUpdatedTs: string | null,
): string {
  if (proposalHash) return "Mutation proposal awaiting operator review";
  if (!tradingLive) {
    return lastUpdatedTs ? "Live decision chain synchronized" : "Standby — awaiting telemetry";
  }
  const qty = tradingLive.position.live_qty;
  const signal = tradingLive.active_signal.signal;
  if (qty !== 0) {
    return `Open position ${qty > 0 ? "LONG" : "SHORT"} ${Math.abs(qty)} · signal ${signal}`;
  }
  if (signal !== "HOLD") {
    return `Flat · evaluating ${signal} entry`;
  }
  return "Flat · monitoring for next setup";
}

export function confidenceLabel(confidence: number): string {
  const pct = Math.round(confidence * 100);
  if (pct > 75) return "High";
  if (pct >= 50) return "Moderate";
  return "Low";
}

export function confidenceTone(confidence: number): "high" | "moderate" | "low" {
  const pct = confidence * 100;
  if (pct > 75) return "high";
  if (pct >= 50) return "moderate";
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
  const { liveMetrics, riskLevel, evolutionState, operatorMode, tradingLive } = state;
  const overallConfidence = deriveOverallConfidence(state);
  const kellyFraction = deriveKellyFraction(state);
  const riskScore = RISK_SCORE[riskLevel];
  const proposalHash = evolutionState.activeMutations[0]?.hash ?? null;
  const verdict = deriveVerdict(riskLevel, overallConfidence);

  return {
    headline: buildDecisionHeadline(tradingLive, proposalHash, liveMetrics.lastUpdatedTs),
    verdict,
    steps: buildReasoningSteps(
      tradingLive,
      liveMetrics.regime,
      riskLevel,
      operatorMode,
      kellyFraction,
    ),
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
