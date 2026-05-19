import type { CoreStore, RiskLevel } from "@/store/coreStore";

export type WallId = "risk" | "drawdown" | "kelly" | "regime";

export type IntegrityTier = "green" | "orange" | "red";

export interface WallMetric {
  id: WallId;
  label: string;
  integrity: number;
  tier: IntegrityTier;
  description: string;
  rawValues: Record<string, string | number | null>;
  isStandby: boolean;
}

const DEFAULT_DRAWDOWN_KILL_PCT = 8;

const RISK_INTEGRITY: Record<RiskLevel, number> = {
  NORMAL: 92,
  ELEVATED: 74,
  HIGH: 52,
  CRITICAL: 28,
  UNKNOWN: 55,
};

const REGIME_INTEGRITY: Record<string, number> = {
  TRENDING: 82,
  NORMAL: 78,
  LOW_VOLATILITY: 85,
  HIGH_RISK: 45,
  CHOP: 58,
  UNKNOWN: 50,
};

function clamp(value: number, min = 0, max = 100): number {
  return Math.min(max, Math.max(min, value));
}

export function integrityTier(pct: number): IntegrityTier {
  if (pct > 85) {
    return "green";
  }
  if (pct >= 60) {
    return "orange";
  }
  return "red";
}

export function aggregateIntegrity(walls: WallMetric[]): number {
  if (walls.length === 0) {
    return 0;
  }
  return Math.min(...walls.map((wall) => wall.integrity));
}

function deriveRiskWall(riskLevel: RiskLevel): WallMetric {
  const integrity = RISK_INTEGRITY[riskLevel];
  return {
    id: "risk",
    label: "Risk",
    integrity,
    tier: integrityTier(integrity),
    description:
      "Constitutional risk posture derived from live policy verdicts and capital-at-risk signals.",
    rawValues: { risk_level: riskLevel },
    isStandby: riskLevel === "UNKNOWN",
  };
}

function deriveDrawdownWall(drawdownPct: number | null): WallMetric {
  if (drawdownPct === null) {
    const integrity = 88;
    return {
      id: "drawdown",
      label: "Drawdown Buffer",
      integrity,
      tier: integrityTier(integrity),
      description:
        "Remaining headroom before the drawdown kill threshold is breached.",
      rawValues: {
        drawdown_pct: null,
        kill_threshold_pct: DEFAULT_DRAWDOWN_KILL_PCT,
      },
      isStandby: true,
    };
  }

  const integrity = clamp(
    100 - (drawdownPct / DEFAULT_DRAWDOWN_KILL_PCT) * 100,
  );
  return {
    id: "drawdown",
    label: "Drawdown Buffer",
    integrity,
    tier: integrityTier(integrity),
    description:
      "Remaining headroom before the drawdown kill threshold is breached.",
    rawValues: {
      drawdown_pct: drawdownPct,
      kill_threshold_pct: DEFAULT_DRAWDOWN_KILL_PCT,
    },
    isStandby: false,
  };
}

function deriveKellyWall(
  winrate: number | null,
  consecutiveLosses: number | null,
): WallMetric {
  if (winrate !== null) {
    const integrity = clamp(winrate * 100);
    return {
      id: "kelly",
      label: "Kelly Factor",
      integrity,
      tier: integrityTier(integrity),
      description:
        "Position-sizing confidence based on recent win-rate and Kelly discipline.",
      rawValues: { winrate, consecutive_losses: consecutiveLosses },
      isStandby: false,
    };
  }

  if (consecutiveLosses !== null && consecutiveLosses > 0) {
    const integrity = clamp(100 - consecutiveLosses * 12);
    return {
      id: "kelly",
      label: "Kelly Factor",
      integrity,
      tier: integrityTier(integrity),
      description:
        "Position-sizing confidence based on recent win-rate and Kelly discipline.",
      rawValues: { winrate: null, consecutive_losses: consecutiveLosses },
      isStandby: false,
    };
  }

  const integrity = 72;
  return {
    id: "kelly",
    label: "Kelly Factor",
    integrity,
    tier: integrityTier(integrity),
    description:
      "Position-sizing confidence based on recent win-rate and Kelly discipline.",
    rawValues: { winrate: null, consecutive_losses: consecutiveLosses },
    isStandby: true,
  };
}

function deriveRegimeWall(
  regime: string,
  regimeConfidence: number | null,
): WallMetric {
  if (regimeConfidence !== null) {
    const integrity = clamp(regimeConfidence * 100);
    return {
      id: "regime",
      label: "Regime Safety",
      integrity,
      tier: integrityTier(integrity),
      description:
        "Confidence that the current market regime classification is stable and actionable.",
      rawValues: { regime, regime_confidence: regimeConfidence },
      isStandby: false,
    };
  }

  const key = regime.toUpperCase().replace(/\s+/g, "_");
  const integrity = REGIME_INTEGRITY[key] ?? REGIME_INTEGRITY.UNKNOWN;
  return {
    id: "regime",
    label: "Regime Safety",
    integrity,
    tier: integrityTier(integrity),
    description:
      "Confidence that the current market regime classification is stable and actionable.",
    rawValues: { regime, regime_confidence: null },
    isStandby: true,
  };
}

export function deriveCitadelWalls(state: CoreStore): WallMetric[] {
  const { liveMetrics, riskLevel } = state;
  return [
    deriveRiskWall(riskLevel),
    deriveDrawdownWall(liveMetrics.drawdownPct),
    deriveKellyWall(liveMetrics.winrate, liveMetrics.consecutiveLosses),
    deriveRegimeWall(liveMetrics.regime, liveMetrics.regimeConfidence),
  ];
}

export function tierLabel(tier: IntegrityTier): string {
  switch (tier) {
    case "green":
      return "Secure";
    case "orange":
      return "Caution";
    case "red":
      return "Critical";
  }
}

export function tierBarClass(tier: IntegrityTier): string {
  switch (tier) {
    case "green":
      return "citadel-bar-glow-emerald bg-emerald-400/85";
    case "orange":
      return "citadel-bar-glow-amber bg-amber-400/85";
    case "red":
      return "citadel-bar-glow-red bg-red-400/85";
  }
}

export function tierBorderClass(tier: IntegrityTier): string {
  switch (tier) {
    case "green":
      return "border-emerald-400/35 hover:border-emerald-400/55 hover:shadow-[0_0_20px_oklch(0.72_0.17_155/25%)]";
    case "orange":
      return "border-amber-400/35 hover:border-amber-400/55 hover:shadow-[0_0_20px_oklch(0.78_0.15_85/25%)]";
    case "red":
      return "border-red-400/40 hover:border-red-400/60 hover:shadow-[0_0_20px_oklch(0.65_0.2_25/30%)]";
  }
}

export function tierRingClass(tier: IntegrityTier): string {
  switch (tier) {
    case "green":
      return "border-emerald-400/50 shadow-[0_0_24px_oklch(0.72_0.17_155/35%)]";
    case "orange":
      return "border-amber-400/50 shadow-[0_0_24px_oklch(0.78_0.15_85/35%)]";
    case "red":
      return "border-red-400/55 shadow-[0_0_24px_oklch(0.65_0.2_25/40%)]";
  }
}
