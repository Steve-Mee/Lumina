import { CeremonyHelixScene } from "@/components/birth/BirthHelixCeremonyScene";
import { LegacyHelixScene } from "@/components/birth/BirthHelixLegacyScene";
import { OrganismAnatomy } from "@/components/organism/OrganismAnatomy";
import { OrganismStageCamera } from "@/components/organism/OrganismStageCamera";
import { OrganismVanes } from "@/components/organism/OrganismVanes";
import type { OrganismMorphology } from "@/lib/organism/phaseMorphology";
import type { VisualQuality } from "@/lib/visualQualityPresets";
import type { TradingMode } from "@/store/coreStore";

export interface BirthHelixSceneProps {
  activating: boolean;
  primed: boolean;
  ceremonyMode: boolean;
  reducedMotion: boolean;
  particleCount: number;
  emissiveBoost: number;
  visualQuality: VisualQuality;
  tubeSegments: number;
  morph: OrganismMorphology;
  tradingMode: TradingMode;
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
  morph,
  tradingMode,
}: BirthHelixSceneProps) {
  if (ceremonyMode) {
    return (
      <>
        <OrganismStageCamera
          halfHeight={morph.fitHalfHeight}
          halfWidth={morph.fitHalfWidth}
          reducedMotion={reducedMotion}
        />
        <CeremonyHelixScene
          activating={activating}
          primed={primed}
          reducedMotion={reducedMotion}
          particleCount={particleCount}
          emissiveBoost={emissiveBoost * morph.helixOpacity}
          visualQuality={visualQuality}
          tubeSegments={tubeSegments}
          strandRadius={morph.helixRadius}
          strandTube={morph.helixTube}
          intensityScale={morph.helixOpacity}
          bloomMode={tradingMode}
          ringOpacity={morph.ringOpacity}
        />
        <OrganismVanes morph={morph} reducedMotion={reducedMotion} />
        <OrganismAnatomy morph={morph} reducedMotion={reducedMotion} />
      </>
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
