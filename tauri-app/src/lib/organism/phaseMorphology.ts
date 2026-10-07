/**
 * Visual-only metamorphosis of the Lumina organism.
 * Display geometry only. Isolated from trading, risk, and maturity law.
 */
import type { MaturationPhaseId } from "@/components/birth/GenesisMaturityLadder";

export type OrganismTradingMode = "SIM" | "REAL";

export interface OrganismMorphology {
  /** 0 spore → 1 adult. Display only. */
  evolution: number;
  helixOpacity: number;
  helixRadius: number;
  helixTube: number;
  coreScale: number;
  ringOpacity: number;
  eyeOpen: number;
  vaneSpan: number;
  vaneCount: number;
  bodyOpacity: number;
  filamentCount: number;
  armor: number;
  constellation: number;
  hover: number;
  crown: number;
  fitHalfHeight: number;
  fitHalfWidth: number;
}

export const ORGANISM_MORPHOLOGY: Record<MaturationPhaseId, OrganismMorphology> = {
  setup: {
    evolution: 0.05,
    helixOpacity: 0.42,
    helixRadius: 0.48,
    helixTube: 0.04,
    coreScale: 0.72,
    ringOpacity: 0.28,
    eyeOpen: 0,
    vaneSpan: 0,
    vaneCount: 0,
    bodyOpacity: 0,
    filamentCount: 0,
    armor: 0,
    constellation: 0,
    hover: 0.04,
    crown: 0,
    fitHalfHeight: 1.55,
    fitHalfWidth: 0.7,
  },
  genesis: {
    evolution: 0.12,
    helixOpacity: 0.68,
    helixRadius: 0.52,
    helixTube: 0.046,
    coreScale: 0.86,
    ringOpacity: 0.5,
    eyeOpen: 0,
    vaneSpan: 0,
    vaneCount: 0,
    bodyOpacity: 0,
    filamentCount: 0,
    armor: 0,
    constellation: 0.04,
    hover: 0.06,
    crown: 0,
    fitHalfHeight: 1.6,
    fitHalfWidth: 0.74,
  },
  birth: {
    evolution: 0.22,
    helixOpacity: 1,
    helixRadius: 0.56,
    helixTube: 0.052,
    coreScale: 1,
    ringOpacity: 1,
    eyeOpen: 0,
    vaneSpan: 0,
    vaneCount: 0,
    bodyOpacity: 0,
    filamentCount: 0,
    armor: 0,
    constellation: 0.06,
    hover: 0.08,
    crown: 0,
    fitHalfHeight: 1.68,
    fitHalfWidth: 0.78,
  },
  awakening: {
    evolution: 0.4,
    helixOpacity: 1,
    helixRadius: 0.48,
    helixTube: 0.05,
    coreScale: 0.7,
    ringOpacity: 0.35,
    eyeOpen: 0.95,
    vaneSpan: 0.16,
    vaneCount: 2,
    bodyOpacity: 0.28,
    filamentCount: 0,
    armor: 0,
    constellation: 0.22,
    hover: 0.12,
    crown: 0,
    fitHalfHeight: 1.72,
    fitHalfWidth: 0.9,
  },
  playground: {
    evolution: 0.58,
    helixOpacity: 0.96,
    helixRadius: 0.4,
    helixTube: 0.048,
    coreScale: 0.5,
    ringOpacity: 0.12,
    eyeOpen: 1,
    vaneSpan: 0.68,
    vaneCount: 4,
    bodyOpacity: 0.55,
    filamentCount: 0,
    armor: 0,
    constellation: 0.4,
    hover: 0.26,
    crown: 0,
    fitHalfHeight: 1.78,
    fitHalfWidth: 1.12,
  },
  apprenticeship: {
    evolution: 0.74,
    helixOpacity: 0.95,
    helixRadius: 0.36,
    helixTube: 0.046,
    coreScale: 0.42,
    ringOpacity: 0.08,
    eyeOpen: 1,
    vaneSpan: 0.82,
    vaneCount: 4,
    bodyOpacity: 0.7,
    filamentCount: 0,
    armor: 0.18,
    constellation: 0.55,
    hover: 0.14,
    crown: 0,
    fitHalfHeight: 1.82,
    fitHalfWidth: 1.18,
  },
  proving_ground: {
    evolution: 0.88,
    helixOpacity: 0.9,
    helixRadius: 0.34,
    helixTube: 0.044,
    coreScale: 0.38,
    ringOpacity: 0.05,
    eyeOpen: 1,
    vaneSpan: 0.4,
    vaneCount: 4,
    bodyOpacity: 0.58,
    filamentCount: 0,
    armor: 0.92,
    constellation: 0.48,
    hover: 0.08,
    crown: 0,
    fitHalfHeight: 1.8,
    fitHalfWidth: 1.08,
  },
  real: {
    evolution: 1,
    helixOpacity: 1,
    helixRadius: 0.34,
    helixTube: 0.048,
    coreScale: 0.32,
    ringOpacity: 0,
    eyeOpen: 1,
    vaneSpan: 1,
    vaneCount: 4,
    bodyOpacity: 0.88,
    filamentCount: 0,
    armor: 0,
    constellation: 1,
    hover: 0.18,
    crown: 0,
    fitHalfHeight: 1.86,
    fitHalfWidth: 1.22,
  },
};

export function resolveOrganismMorphology(
  phase: MaturationPhaseId,
  tradingMode: OrganismTradingMode = "SIM",
): OrganismMorphology {
  if (tradingMode === "REAL") {
    return ORGANISM_MORPHOLOGY.real;
  }
  return ORGANISM_MORPHOLOGY[phase] ?? ORGANISM_MORPHOLOGY.genesis;
}

export function organismHasAnatomy(morph: OrganismMorphology): boolean {
  return (
    morph.eyeOpen > 0.02 ||
    morph.vaneSpan > 0.02 ||
    morph.bodyOpacity > 0.02 ||
    morph.armor > 0.02 ||
    morph.crown > 0.02 ||
    morph.filamentCount > 0 ||
    morph.constellation > 0.12
  );
}
