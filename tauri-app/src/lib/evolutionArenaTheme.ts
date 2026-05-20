import {
  MODE_REAL_ACCENT,
  MODE_REAL_ACCENT_SOFT,
  MODE_REAL_PRIMARY,
  MODE_REAL_SECONDARY,
  MODE_SIM_ACCENT,
  MODE_SIM_ACCENT_SOFT,
  MODE_SIM_SECONDARY,
} from "@/lib/designTokens";
import type { VisualQuality } from "@/lib/visualQualityPresets";
import type { TradingMode } from "@/store/coreStore";

export interface EvolutionPalette {
  primary: string;
  secondary: string;
  accent: string;
  edgeCore: string;
  edgeHalo: string;
  birthPrimary: string;
  birthSecondary: string;
  championRing: string;
  pulseSpeed: number;
}

export interface FitnessGlow {
  core: string;
  emissive: string;
  emissiveIntensity: number;
}

export interface BirthEffectParams {
  durationS: number;
  particleCount: number;
  spread: number;
  nodeBirthDurationS: number;
}

const SIM_PALETTE: EvolutionPalette = {
  primary: MODE_SIM_ACCENT,
  secondary: MODE_SIM_SECONDARY,
  accent: MODE_SIM_ACCENT_SOFT,
  edgeCore: "#22d3ee",
  edgeHalo: MODE_SIM_ACCENT,
  birthPrimary: MODE_SIM_ACCENT,
  birthSecondary: MODE_SIM_SECONDARY,
  championRing: "#fcd34d",
  pulseSpeed: 4,
};

const REAL_PALETTE: EvolutionPalette = {
  primary: MODE_REAL_ACCENT_SOFT,
  secondary: MODE_REAL_SECONDARY,
  accent: MODE_REAL_ACCENT,
  edgeCore: MODE_REAL_ACCENT_SOFT,
  edgeHalo: MODE_REAL_PRIMARY,
  birthPrimary: MODE_REAL_ACCENT_SOFT,
  birthSecondary: "#64748b",
  championRing: MODE_REAL_ACCENT,
  pulseSpeed: 2.2,
};

export function calmMode(mode: TradingMode): boolean {
  return mode === "REAL";
}

export function evolutionPalette(mode: TradingMode): EvolutionPalette {
  return mode === "SIM" ? SIM_PALETTE : REAL_PALETTE;
}

export function fitnessGlow(fitness: number, mode: TradingMode): FitnessGlow {
  const palette = evolutionPalette(mode);
  if (fitness >= 0.7) {
    return {
      core: palette.primary,
      emissive: palette.primary,
      emissiveIntensity: mode === "SIM" ? 0.32 : 0.22,
    };
  }
  if (fitness >= 0.55) {
    return {
      core: palette.secondary,
      emissive: palette.secondary,
      emissiveIntensity: mode === "SIM" ? 0.28 : 0.18,
    };
  }
  return {
    core: "#64748b",
    emissive: "#475569",
    emissiveIntensity: 0.15,
  };
}

export function edgeGlowColor(mode: TradingMode): { core: string; halo: string } {
  const palette = evolutionPalette(mode);
  return { core: palette.edgeCore, halo: palette.edgeHalo };
}

export function edgeGlowInnerOpacity(mode: TradingMode, calm: boolean): number {
  const base = calm ? 0.38 : 0.55;
  return mode === "SIM" ? Math.min(1, base * 1.2) : base;
}

export function edgeGlowHaloOpacity(mode: TradingMode): number {
  return mode === "SIM" ? 0.144 : 0.12;
}

export function championRingOpacity(mode: TradingMode): number {
  return mode === "SIM" ? 0.8625 : 0.75;
}

export function nodeRadius(fitness: number): number {
  return 0.12 + fitness * 0.18;
}

export function birthEffectParams(
  mode: TradingMode,
  quality: VisualQuality,
  burstParticles: number,
  particleScale: number,
): BirthEffectParams {
  const calm = calmMode(mode);
  const qualityScale =
    quality === "low" ? 0.5 : quality === "high" ? 1 : 0.85;

  return {
    durationS: calm ? 2.4 : 1.6,
    particleCount: Math.max(
      8,
      Math.round(burstParticles * particleScale * qualityScale),
    ),
    spread: calm ? 0.9 : 1.4,
    nodeBirthDurationS: calm ? 1 : 0.8,
  };
}

export function birthClearTimeoutMs(mode: TradingMode): number {
  return calmMode(mode) ? 2600 : 1800;
}

export function dustParticleCount(
  mode: TradingMode,
  quality: VisualQuality,
): number {
  if (calmMode(mode) || quality === "low") {
    return 0;
  }
  return quality === "high" ? 80 : 40;
}

/** SIM-only ambient dust orbit speed multiplier (0 in REAL). */
export function evolutionDustDriftScale(mode: TradingMode): number {
  return mode === "SIM" ? 1.25 : 0;
}

export function truncateHash(hash: string, head = 8, tail = 6): string {
  if (hash.length <= head + tail + 3) {
    return hash;
  }
  return `${hash.slice(0, head)}…${hash.slice(-tail)}`;
}

/** Returns birth scale factor 0→1 based on elapsed time since mount. */
export function birthScaleFactor(
  isNew: boolean,
  reducedMotion: boolean,
  elapsed: number,
  nodeBirthDurationS: number,
): number {
  if (!isNew || reducedMotion) {
    return 1;
  }
  const t = Math.min(1, elapsed / nodeBirthDurationS);
  return 0.15 + t * 0.85 * (2 - t);
}
