import type { RiskLevel, TradingMode } from "@/store/coreStore";

export interface LivingCorePalette {
  primary: string;
  secondary: string;
  accent: string;
  pulseSpeed: number;
}

const SIM_PALETTE: LivingCorePalette = {
  primary: "#00e5ff",
  secondary: "#a855f7",
  accent: "#ec4899",
  pulseSpeed: 1.4,
};

const REAL_PALETTE: LivingCorePalette = {
  primary: "#64748b",
  secondary: "#3b82f6",
  accent: "#f59e0b",
  pulseSpeed: 0.7,
};

const RISK_AGITATION: Record<RiskLevel, number> = {
  NORMAL: 0.25,
  ELEVATED: 0.5,
  HIGH: 0.75,
  CRITICAL: 1.0,
  UNKNOWN: 0.35,
};

const RISK_TINT: Record<RiskLevel, string> = {
  NORMAL: "#2dd4bf",
  ELEVATED: "#fbbf24",
  HIGH: "#f97316",
  CRITICAL: "#ef4444",
  UNKNOWN: "#94a3b8",
};

export function modePalette(mode: TradingMode): LivingCorePalette {
  return mode === "SIM" ? SIM_PALETTE : REAL_PALETTE;
}

export function riskAgitation(risk: RiskLevel): number {
  return RISK_AGITATION[risk];
}

export function riskTint(risk: RiskLevel): string {
  return RISK_TINT[risk];
}
