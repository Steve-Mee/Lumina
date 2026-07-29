import type { VisualQuality } from "@/lib/visualQualityPresets";

import { CeremonyHelixScene } from "@/components/birth/BirthHelixCeremonyScene";
import { LegacyHelixScene } from "@/components/birth/BirthHelixLegacyScene";

export interface BirthHelixSceneProps {
  activating: boolean;
  primed: boolean;
  ceremonyMode: boolean;
  reducedMotion: boolean;
  particleCount: number;
  emissiveBoost: number;
  visualQuality: VisualQuality;
  tubeSegments: number;
}

export function BirthHelixScene({
  activating,
  primed,
  ceremonyMode,
  reducedMotion,
  particleCount,
  emissiveBoost,
  visualQuality,
  tubeSegments,
}: BirthHelixSceneProps) {
  if (ceremonyMode) {
    return (
      <CeremonyHelixScene
        activating={activating}
        primed={primed}
        reducedMotion={reducedMotion}
        particleCount={particleCount}
        emissiveBoost={emissiveBoost}
        visualQuality={visualQuality}
        tubeSegments={tubeSegments}
      />
    );
  }

  return (
    <LegacyHelixScene
      activating={activating}
      primed={primed}
      reducedMotion={reducedMotion}
      particleCount={particleCount}
      emissiveBoost={emissiveBoost}
      visualQuality={visualQuality}
      tubeSegments={tubeSegments}
    />
  );
}
