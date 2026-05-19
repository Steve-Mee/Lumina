import { Canvas, type CanvasProps } from "@react-three/fiber";
import type { ReactNode } from "react";

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
}

export function VisibilityCanvas({
  className,
  minHeight = "min-h-[220px]",
  idleLabel = "3D panel paused — scroll into view",
  panelName,
  camera,
  children,
  onCreated,
}: VisibilityCanvasProps) {
  const { ref, isVisible } = usePanelVisibility();
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const renderConfig = useVisualSettingsStore(selectRenderConfig);

  return (
    <div
      ref={ref}
      className={cn("relative h-full w-full", minHeight, className)}
    >
      {isVisible ? (
        <PanelErrorBoundary panelName={panelName}>
          <Canvas
            key={`${visualQuality}-visible`}
            className={cn("h-full w-full touch-none", minHeight)}
            frameloop="always"
            dpr={renderConfig.dpr}
            camera={camera}
            gl={{
              antialias: renderConfig.antialias,
              alpha: true,
              powerPreference: "high-performance",
            }}
            onCreated={onCreated}
          >
            {children}
          </Canvas>
        </PanelErrorBoundary>
      ) : (
        <div
          className={cn(
            "flex h-full w-full items-center justify-center bg-black/20",
            minHeight,
          )}
        >
          <PanelLoader label={idleLabel} className="min-h-0" rows={2} />
        </div>
      )}
    </div>
  );
}
