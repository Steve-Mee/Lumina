import { Suspense } from "react";

import { LuminaLogo } from "@/components/cockpit/LuminaLogo";
import { VisibilityCanvas } from "@/components/cockpit/VisibilityCanvas";
import { BirthHelixScene } from "@/components/birth/BirthHelixScenes";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { helixTubeSegments } from "@/components/three/helixPrimitives";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import {
  birthEmissiveFromTrades,
  birthParticleCount,
} from "@/lib/birthHelixGeometry";
import { cn } from "@/lib/utils";
import {
  selectRenderConfig,
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

interface BirthHelixVisualProps {
  activating?: boolean;
  primed?: boolean;
  ceremonyMode?: boolean;
  trainingTrades?: number;
  className?: string;
}

export function BirthHelixVisual({
  activating = false,
  primed = false,
  ceremonyMode = false,
  trainingTrades,
  className,
}: BirthHelixVisualProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const renderConfig = useVisualSettingsStore(selectRenderConfig);
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const tubeSegments = helixTubeSegments(visualQuality);
  const particleCount = birthParticleCount(
    renderConfig.particleScale,
    trainingTrades,
    visualQuality,
  );
  const emissiveBoost = birthEmissiveFromTrades(trainingTrades);
  const sceneParticleCount = ceremonyMode
    ? Math.max(24, Math.round(particleCount * 0.5))
    : particleCount;
  const ceremonyCssFallback = ceremonyMode && (prefersReducedMotion || visualQuality === "low");
  const legacyCssFallback = !ceremonyMode && (prefersReducedMotion || visualQuality === "low");

  const minHeightClass = ceremonyMode ? "min-h-0 h-full" : "min-h-[280px]";
  const ceremonyCamera = { position: [0, 0, 4.0] as [number, number, number], fov: 34 };

  if (ceremonyCssFallback) {
    return (
      <div
        className={cn(
          "relative flex h-full min-h-0 items-center justify-center",
          className,
        )}
      >
        <LuminaLogo className="pointer-events-none absolute size-56 opacity-40 md:size-64" />
        <BirthOrganismVisual
          awakening={activating}
          className="relative size-64 md:size-72"
        />
      </div>
    );
  }

  if (legacyCssFallback) {
    return (
      <div className={cn("flex h-full items-center justify-center", minHeightClass, className)}>
        <BirthOrganismVisual
          awakening={activating}
          className={cn(ceremonyMode ? "size-72 md:size-80" : "size-56 md:size-64")}
        />
      </div>
    );
  }

  return (
    <div className={cn("relative flex h-full w-full items-center justify-center", minHeightClass, className)} aria-hidden>
      <Suspense
        fallback={
          <div className={cn("flex h-full items-center justify-center", minHeightClass)}>
            <BirthOrganismVisual className="size-48 opacity-70" />
          </div>
        }
      >
        <VisibilityCanvas
          panelName="Birth Helix"
          idleLabel="Birth helix paused — scroll into view"
          minHeight={minHeightClass}
          camera={ceremonyMode ? ceremonyCamera : { position: [0, 0.5, 5.5], fov: 42 }}
        >
          <BirthHelixScene
            activating={activating}
            primed={primed}
            ceremonyMode={ceremonyMode}
            reducedMotion={prefersReducedMotion}
            particleCount={sceneParticleCount}
            emissiveBoost={emissiveBoost}
            visualQuality={visualQuality}
            tubeSegments={tubeSegments}
          />
        </VisibilityCanvas>
      </Suspense>
    </div>
  );
}
