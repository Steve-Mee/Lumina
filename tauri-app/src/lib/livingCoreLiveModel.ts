import type { IntelligenceHealth } from "@/lib/adaptiveIntelligenceTypes";
import type { LivingCorePalette } from "@/lib/livingCoreTheme";
import type {
  ConnectionStatus,
  RiskLevel,
  TradingMode,
} from "@/store/coreStore";

export type RegimeVisualKey =
  | "TRENDING_UP"
  | "TRENDING_DOWN"
  | "RANGING"
  | "HIGH_VOLATILITY"
  | "UNKNOWN";

export type VitalityBucket = "low" | "mid" | "high";

export interface LivingCoreLiveSignals {
  mode: TradingMode;
  riskLevel: RiskLevel;
  regime: string;
  regimeConfidence: number | null;
  connectionStatus: ConnectionStatus;
  fallbackMode: boolean;
  intelligenceHealth: IntelligenceHealth;
}

export interface LivingCoreVisualParams {
  palette: LivingCorePalette;
  vitality: number;
  agitation: number;
  breatheSpeed: number;
  helixDrift: number;
  particleOpacity: number;
  emissiveBoost: number;
  regimePhase: number;
  regimeKey: RegimeVisualKey;
}

const CONNECTION_VITALITY: Record<ConnectionStatus, number> = {
  connected: 1,
  reconnecting: 0.55,
  connecting: 0.35,
  disconnected: 0.15,
};

const INTELLIGENCE_VITALITY: Record<IntelligenceHealth, number> = {
  healthy: 1,
  degraded: 0.7,
  error: 0.4,
};

const RISK_AGITATION: Record<RiskLevel, number> = {
  NORMAL: 0.25,
  ELEVATED: 0.5,
  HIGH: 0.75,
  CRITICAL: 1,
  UNKNOWN: 0.35,
};

function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value));
}

export function normalizeRegimeKey(regime: string): RegimeVisualKey {
  const key = regime.trim().toUpperCase().replace(/\s+/g, "_");

  if (
    key.includes("TRENDING_UP") ||
    key === "TRENDING" ||
    key.includes("BULL") ||
    key.includes("UPTREND")
  ) {
    return "TRENDING_UP";
  }
  if (key.includes("TRENDING_DOWN") || key.includes("BEAR") || key.includes("DOWNTREND")) {
    return "TRENDING_DOWN";
  }
  if (
    key.includes("HIGH_VOL") ||
    key.includes("VOLATILE") ||
    key.includes("VOLATILITY") ||
    key === "CHAOTIC"
  ) {
    return "HIGH_VOLATILITY";
  }
  if (key.includes("RANG") || key.includes("SIDEWAYS") || key.includes("NEUTRAL")) {
    return "RANGING";
  }
  return "UNKNOWN";
}

export function computeVitality(signals: LivingCoreLiveSignals): number {
  let vitality = CONNECTION_VITALITY[signals.connectionStatus];
  vitality *= INTELLIGENCE_VITALITY[signals.intelligenceHealth];
  if (signals.fallbackMode) {
    vitality *= 0.6;
  }
  if (signals.regimeConfidence != null) {
    vitality += clamp(signals.regimeConfidence) * 0.15;
  }
  return clamp(vitality, 0.35, 1);
}

export function vitalityBucket(vitality: number): VitalityBucket {
  if (vitality < 0.4) {
    return "low";
  }
  if (vitality < 0.75) {
    return "mid";
  }
  return "high";
}

export interface RegimeCharacter {
  helixDrift: number;
  breatheSpeed: number;
  emissiveBoost: number;
  regimePhase: number;
  turbulenceBoost: number;
  secondaryShift: string | null;
  accentShift: string | null;
}

export function regimeCharacter(key: RegimeVisualKey): RegimeCharacter {
  switch (key) {
    case "TRENDING_UP":
      return {
        helixDrift: 0.22,
        breatheSpeed: 0.55,
        emissiveBoost: 1.08,
        regimePhase: 0.15,
        turbulenceBoost: 0.05,
        secondaryShift: "#34d399",
        accentShift: null,
      };
    case "TRENDING_DOWN":
      return {
        helixDrift: 0.14,
        breatheSpeed: 0.48,
        emissiveBoost: 0.92,
        regimePhase: -0.12,
        turbulenceBoost: 0.04,
        secondaryShift: "#60a5fa",
        accentShift: null,
      };
    case "RANGING":
      return {
        helixDrift: 0.1,
        breatheSpeed: 0.42,
        emissiveBoost: 0.88,
        regimePhase: 0,
        turbulenceBoost: 0,
        secondaryShift: null,
        accentShift: null,
      };
    case "HIGH_VOLATILITY":
      return {
        helixDrift: 0.18,
        breatheSpeed: 0.62,
        emissiveBoost: 1.05,
        regimePhase: 0.25,
        turbulenceBoost: 0.12,
        secondaryShift: null,
        accentShift: "#fbbf24",
      };
    default:
      return {
        helixDrift: 0.12,
        breatheSpeed: 0.45,
        emissiveBoost: 0.75,
        regimePhase: 0,
        turbulenceBoost: 0.02,
        secondaryShift: "#94a3b8",
        accentShift: null,
      };
  }
}

export function riskAgitationForLevel(risk: RiskLevel): number {
  return RISK_AGITATION[risk];
}

export function buildVisualParamsFromSignals(
  palette: LivingCorePalette,
  signals: LivingCoreLiveSignals,
): LivingCoreVisualParams {
  const regimeKey = normalizeRegimeKey(signals.regime);
  const character = regimeCharacter(regimeKey);
  const vitality = computeVitality(signals);
  const baseAgitation = riskAgitationForLevel(signals.riskLevel);
  const agitation = clamp(
    (baseAgitation + character.turbulenceBoost) * vitality,
    0,
    1,
  );

  const modeDriftScale = signals.mode === "SIM" ? 1 : 0.55;
  const modeBreathScale = signals.mode === "SIM" ? 1 : 0.75;

  return {
    palette: {
      ...palette,
      secondary: character.secondaryShift ?? palette.secondary,
      accent: character.accentShift ?? palette.accent,
      pulseSpeed: palette.pulseSpeed * modeBreathScale,
    },
    vitality,
    agitation,
    breatheSpeed: character.breatheSpeed * modeBreathScale,
    helixDrift: character.helixDrift * modeDriftScale,
    particleOpacity: clamp(0.25 + vitality * 0.55, 0.15, 0.85),
    emissiveBoost: character.emissiveBoost * clamp(0.35 + vitality * 0.65),
    regimePhase: character.regimePhase,
    regimeKey,
  };
}
