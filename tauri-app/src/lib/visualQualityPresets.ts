export type VisualQuality = "low" | "balanced" | "high";

export interface RenderConfig {
  dpr: [number, number];
  antialias: boolean;
  particleScale: number;
  burstParticles: number;
  forceTicksPerFrame: number;
}

export const VISUAL_QUALITY_PRESETS: Record<VisualQuality, RenderConfig> = {
  low: {
    dpr: [1, 1],
    antialias: false,
    particleScale: 0.5,
    burstParticles: 20,
    forceTicksPerFrame: 1,
  },
  balanced: {
    dpr: [1, 1.25],
    antialias: true,
    particleScale: 1.0,
    burstParticles: 40,
    forceTicksPerFrame: 2,
  },
  high: {
    dpr: [1, 1.5],
    antialias: true,
    particleScale: 1.0,
    burstParticles: 40,
    forceTicksPerFrame: 4,
  },
};

export const VISUAL_QUALITY_LABELS: Record<
  VisualQuality,
  { title: string; description: string }
> = {
  low: {
    title: "Low",
    description: "Best performance — reduced particles, no antialiasing",
  },
  balanced: {
    title: "Balanced",
    description: "Recommended — smooth visuals with efficient GPU use",
  },
  high: {
    title: "High",
    description: "Maximum fidelity — higher DPR and force simulation rate",
  },
};

export function resolveRenderConfig(quality: VisualQuality): RenderConfig {
  return VISUAL_QUALITY_PRESETS[quality];
}
