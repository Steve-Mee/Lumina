import * as THREE from "three";

import type { VisualQuality } from "@/lib/visualQualityPresets";

export const BIRTH_HELIX_HEIGHT = 3.2;
export const BIRTH_HELIX_TURNS = 2.5;
export const BIRTH_RUNG_COUNT = 20;
export const LIVING_RUNG_COUNT = 40;

export function helixPoint(
  t: number,
  strand: 0 | 1,
  radius: number,
  phase: number,
): THREE.Vector3 {
  const angle = t * Math.PI * 2 * BIRTH_HELIX_TURNS + strand * Math.PI + phase;
  const y = (t - 0.5) * BIRTH_HELIX_HEIGHT;
  return new THREE.Vector3(
    Math.cos(angle) * radius,
    y,
    Math.sin(angle) * radius,
  );
}

export function buildHelixCurve(
  strand: 0 | 1,
  radius: number,
  phase: number,
): THREE.CatmullRomCurve3 {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i <= 64; i++) {
    points.push(helixPoint(i / 64, strand, radius, phase));
  }
  return new THREE.CatmullRomCurve3(points);
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

const BIRTH_PARTICLE_CEILING: Record<VisualQuality, number> = {
  low: 0,
  balanced: 120,
  high: 200,
};

/** Particle density scales with training volume (50–120 base before quality scale). */
export function birthParticleCount(
  particleScale = 1,
  trainingTrades?: number,
  visualQuality: VisualQuality = "balanced",
): number {
  const tradeFactor =
    trainingTrades != null
      ? clamp01((trainingTrades - 5_000) / (500_000 - 5_000))
      : 0.5;
  const base = 50 + Math.round(tradeFactor * 70);
  const raw = Math.max(40, Math.round(base * particleScale));
  const ceiling = BIRTH_PARTICLE_CEILING[visualQuality] ?? BIRTH_PARTICLE_CEILING.balanced;
  return ceiling > 0 ? Math.min(raw, ceiling) : raw;
}

/** Emissive boost from training volume (0.35–1.0). */
export function birthEmissiveFromTrades(trainingTrades?: number): number {
  if (trainingTrades == null) {
    return 0.65;
  }
  return 0.35 + clamp01((trainingTrades - 5_000) / (500_000 - 5_000)) * 0.65;
}
