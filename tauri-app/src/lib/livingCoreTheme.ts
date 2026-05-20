import type { IntelligenceHealth } from "@/lib/adaptiveIntelligenceTypes";
import {
  MODE_REAL_ACCENT,
  MODE_REAL_PRIMARY,
  MODE_REAL_SECONDARY,
  MODE_SIM_ACCENT,
  MODE_SIM_ACCENT_SOFT,
  MODE_SIM_SECONDARY,
  STATUS_ERROR,
  STATUS_WARN,
} from "@/lib/designTokens";
import {
  buildVisualParamsFromSignals,
  type LivingCoreLiveSignals,
  type LivingCoreVisualParams,
} from "@/lib/livingCoreLiveModel";
import type { RiskLevel, TradingMode } from "@/store/coreStore";

export interface LivingCorePalette {
  primary: string;
  secondary: string;
  accent: string;
  pulseSpeed: number;
}

const SIM_PALETTE: LivingCorePalette = {
  primary: MODE_SIM_ACCENT,
  secondary: MODE_SIM_SECONDARY,
  accent: MODE_SIM_ACCENT_SOFT,
  pulseSpeed: 0.55,
};

const REAL_PALETTE: LivingCorePalette = {
  primary: MODE_REAL_PRIMARY,
  secondary: MODE_REAL_SECONDARY,
  accent: MODE_REAL_ACCENT,
  pulseSpeed: 0.35,
};

const RISK_AGITATION: Record<RiskLevel, number> = {
  NORMAL: 0.25,
  ELEVATED: 0.5,
  HIGH: 0.75,
  CRITICAL: 1,
  UNKNOWN: 0.35,
};

const RISK_TINT: Record<RiskLevel, string> = {
  NORMAL: "#2dd4bf",
  ELEVATED: STATUS_WARN,
  HIGH: STATUS_WARN,
  CRITICAL: STATUS_ERROR,
  UNKNOWN: MODE_REAL_PRIMARY,
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

export function buildLivingCoreVisualParams(
  signals: LivingCoreLiveSignals,
): LivingCoreVisualParams {
  return buildVisualParamsFromSignals(modePalette(signals.mode), signals);
}

export type { IntelligenceHealth, LivingCoreLiveSignals, LivingCoreVisualParams };
