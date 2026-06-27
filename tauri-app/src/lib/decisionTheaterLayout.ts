import type { HudSignalGlow } from "@/components/cockpit/HudSignal";
import type { DecisionBrief } from "@/lib/decisionTheaterModel";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import { calmMode } from "@/lib/evolutionArenaTheme";
import { formatUsd } from "@/lib/tradingPerformanceModel";
import type { RiskLevel, TradingMode } from "@/store/coreStore";

export const DECISION_STAGE_HERO_MAX = 2;

export interface StageHeroSignal {
  label: string;
  value: string;
  glow: HudSignalGlow;
  intensity?: number;
}

export interface StageOverflowSignal {
  id: string;
  label: string;
  value: string;
  glow: HudSignalGlow;
  intensity?: number;
}

export interface DecisionStageHeroLayout {
  primary: StageHeroSignal;
  secondary: StageHeroSignal | null;
  overflow: StageOverflowSignal[];
}

function riskIsHighOrAbove(riskLevel: RiskLevel): boolean {
  return riskLevel === "HIGH" || riskLevel === "CRITICAL";
}

export function formatKellyLabel(mode: TradingMode, fraction: number): string {
  const pct = `${Math.round(fraction * 100)}%`;
  return mode === "REAL" ? `${pct} · Quarter-Kelly` : `${pct} · SIM cap`;
}

export function riskHudGlow(riskLevel: RiskLevel): HudSignalGlow {
  switch (riskLevel) {
    case "NORMAL":
    case "ELEVATED":
      return "emerald";
    case "HIGH":
      return "amber";
    case "CRITICAL":
    case "UNKNOWN":
      return "amber";
    default:
      return "neutral";
  }
}

export function hasDebugPayload(trading: LiveTradingSnapshot | null): boolean {
  if (!trading) {
    return false;
  }
  return trading.current_dream != null || trading.runtime_state != null;
}

export function formatPositionSide(trading: LiveTradingSnapshot | null): string {
  const position = trading?.position;
  const qty = position?.live_qty ?? 0;
  if (qty > 0) {
    return "LONG";
  }
  if (qty < 0) {
    return "SHORT";
  }
  return position?.side_signal?.toUpperCase() || "FLAT";
}

export function formatPositionQty(trading: LiveTradingSnapshot | null): string {
  const qty = trading?.position?.live_qty ?? 0;
  if (qty === 0) {
    return "Flat";
  }
  return `${Math.abs(qty)} ct`;
}

export function signalChipClass(signal: string): string {
  const normalized = signal.toUpperCase();
  if (normalized === "BUY" || normalized === "LONG") {
    return "decision-signal-buy";
  }
  if (normalized === "SELL" || normalized === "SHORT") {
    return "decision-signal-sell";
  }
  return "decision-signal-hold";
}

export function verdictToneClass(tone: "high" | "moderate" | "low"): string {
  switch (tone) {
    case "high":
      return "border-emerald-400/30 bg-emerald-500/10 text-emerald-300";
    case "moderate":
      return "border-amber-400/30 bg-amber-500/10 text-amber-300";
    case "low":
      return "border-red-400/30 bg-red-500/10 text-red-300";
  }
}

export function resolveDecisionStageHero(
  mode: TradingMode,
  brief: DecisionBrief,
  trading: LiveTradingSnapshot | null,
  riskLevel: RiskLevel,
  killSwitchActive: boolean,
): DecisionStageHeroLayout {
  const position = trading?.position;
  const isCalm = calmMode(mode);

  const confidenceSignal: StageHeroSignal = {
    label: "Confidence",
    value: `${Math.round(brief.metrics.overallConfidence * 100)}%`,
    glow: "violet",
    intensity: brief.metrics.overallConfidence,
  };

  const riskSignal: StageHeroSignal = {
    label: "Risk",
    value: `${brief.metrics.riskScore}`,
    glow: riskHudGlow(riskLevel),
    intensity: brief.metrics.riskScore / 100,
  };

  const kellySignal: StageHeroSignal = {
    label: "Kelly",
    value: formatKellyLabel(mode, brief.metrics.kellyFraction),
    glow: mode === "REAL" ? "gold" : "cyan",
  };

  const primary = mode === "REAL" ? riskSignal : confidenceSignal;

  const proposalActive = brief.verdict !== "hold" && brief.proposalHash !== null;
  const showKellySecondary =
    proposalActive && (!isCalm || riskIsHighOrAbove(riskLevel));

  const secondary = showKellySecondary ? kellySignal : null;

  const heroLabels = new Set([primary.label, secondary?.label].filter(Boolean));

  const overflow: StageOverflowSignal[] = [];

  if (!heroLabels.has("Confidence")) {
    overflow.push({ id: "confidence", ...confidenceSignal });
  }
  if (!heroLabels.has("Risk")) {
    overflow.push({ id: "risk", ...riskSignal });
  }
  if (!heroLabels.has("Kelly") && proposalActive) {
    overflow.push({ id: "kelly", ...kellySignal });
  }

  overflow.push(
    { id: "regime", label: "Regime", value: brief.metrics.regime, glow: "neutral" },
    { id: "position", label: "Position", value: formatPositionSide(trading), glow: "cyan" },
    { id: "size", label: "Size", value: formatPositionQty(trading), glow: "neutral" },
    {
      id: "openPnl",
      label: "Open P&L",
      value: formatUsd(position?.open_pnl ?? null),
      glow: (position?.open_pnl ?? 0) >= 0 ? "emerald" : "amber",
    },
    {
      id: "daily",
      label: "Daily",
      value: formatUsd(position?.daily_pnl ?? null),
      glow: (position?.daily_pnl ?? 0) >= 0 ? "emerald" : "amber",
    },
    {
      id: "losses",
      label: "Losses",
      value: `${trading?.consecutive_losses ?? 0}`,
      glow: (trading?.consecutive_losses ?? 0) > 2 ? "amber" : "neutral",
    },
    {
      id: "killSwitch",
      label: "Kill Switch",
      value: killSwitchActive ? "ON" : "Off",
      glow: killSwitchActive ? "amber" : "emerald",
    },
  );

  return { primary, secondary, overflow };
}

export const DECISION_TRADE_PREVIEW_MAX = 2;

export function resolveDecisionTradePreview(
  trades: import("@/lib/liveTradingTypes").TradeRecord[],
  maxRows = DECISION_TRADE_PREVIEW_MAX,
): {
  preview: import("@/lib/liveTradingTypes").TradeRecord[];
  overflowCount: number;
} {
  const preview = trades.slice(0, maxRows);
  return {
    preview,
    overflowCount: Math.max(0, trades.length - preview.length),
  };
}
