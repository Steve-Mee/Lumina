import { Bloom, ChromaticAberration, EffectComposer, Vignette } from "@react-three/postprocessing";

import type { VisualQuality } from "@/lib/visualQualityPresets";
import type { TradingMode } from "@/store/coreStore";

interface CinematicBloomProps {
  enabled?: boolean;
  mode?: TradingMode;
  reducedMotion?: boolean;
  intensity?: number;
  visualQuality?: VisualQuality;
  /** Birth ceremony / hero surfaces — softer bloom, no chromatic fringing. */
  disableChromaticAberration?: boolean;
}

export function CinematicBloom({
  enabled = true,
  mode = "SIM",
  reducedMotion = false,
  intensity,
  visualQuality = "balanced",
  disableChromaticAberration = false,
}: CinematicBloomProps) {
  if (!enabled) {
    return null;
  }

  const sim = mode === "SIM";
  const lowQuality = visualQuality === "low";
  const highQuality = visualQuality === "high";

  if (reducedMotion || lowQuality) {
    return (
      <mesh position={[0, 0, -1]} scale={[2, 2, 1]}>
        <planeGeometry />
        <meshBasicMaterial
          transparent
          opacity={sim ? 0.08 : 0.14}
          color={sim ? "#0a1628" : "#0f0e0c"}
        />
      </mesh>
    );
  }

  const bloomIntensity = intensity ?? (sim ? 0.45 : 0.28);
  const multisampling = highQuality ? 4 : 0;

  return (
    <EffectComposer multisampling={multisampling}>
      <Bloom
        luminanceThreshold={0.65}
        luminanceSmoothing={0.4}
        intensity={bloomIntensity}
        mipmapBlur
      />
      <Vignette eskil={false} offset={0.1} darkness={sim ? 0.4 : 0.62} />
      {sim && !disableChromaticAberration ? (
        <ChromaticAberration offset={[0.003, 0.003]} />
      ) : null}
    </EffectComposer>
  );
}
