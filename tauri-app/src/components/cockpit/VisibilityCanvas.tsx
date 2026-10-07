import { Canvas, type CanvasProps } from "@react-three/fiber";
import type { ReactNode } from "react";

import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { PanelErrorBoundary } from "@/components/cockpit/PanelErrorBoundary";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { usePanelVisibility } from "@/hooks/usePanelVisibility";
import { cn } from "@/lib/utils";
import {
  selectRenderConfig,
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

interface VisibilityCanvasProps {
  className?: string;
  minHeight?: string;
  idleLabel?: string;
  panelName: string;
  camera: CanvasProps["camera"];
  children: ReactNode;
  onCreated?: CanvasProps["onCreated"];
  /** 0 keeps the CSS void; 1 is required when EffectComposer bloom is mounted. */
  clearAlpha?: number;
}

export function VisibilityCanvas({
  className,
  minHeight = "min-h-[220px]",
  idleLabel = "3D panel paused — scroll into view",
  panelName,
  camera,
  children,
  onCreated,
  clearAlpha = 0,
}: VisibilityCanvasProps) {
  const { ref, isVisible } = usePanelVisibility();
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const renderConfig = useVisualSettingsStore(selectRenderConfig);

  return (
    <div
      ref={ref}
      className={cn("relative h-full w-full min-h-0", minHeight, className)}
      style={{ width: "100%", height: "100%" }}
    >
      <PanelErrorBoundary panelName={panelName}>
        <Canvas
          key={visualQuality}
          className={cn("h-full w-full touch-none", minHeight)}
          style={{ width: "100%", height: "100%", visibility: isVisible ? "visible" : "hidden" }}
          frameloop={isVisible ? "always" : "never"}
          dpr={renderConfig.dpr}
          camera={camera}
          resize={{ debounce: 0 }}
          gl={{
            antialias: renderConfig.antialias,
            alpha: true,
            powerPreference: "high-performance",
          }}
          onCreated={(state) => {
            state.gl.setClearColor(0x070b12, clearAlpha);
            if (state.size.width > 0 && state.size.height > 0) {
              state.gl.setSize(state.size.width, state.size.height, false);
            }
            onCreated?.(state);
          }}
        >
          {children}
        </Canvas>
      </PanelErrorBoundary>
      {isVisible ? null : (
        <div
          className={cn(
            "pointer-events-none absolute inset-0 flex h-full w-full flex-col items-center justify-center gap-3 opacity-40",
            minHeight,
          )}
        >
          <BirthOrganismVisual className="size-16" />
          <PanelLoader label={idleLabel} className="min-h-0" rows={2} />
        </div>
      )}
    </div>
  );
}
