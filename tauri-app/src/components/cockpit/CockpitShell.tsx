import type { ReactNode } from "react";
import { useEffect } from "react";

import { CommandHud } from "@/components/cockpit/CommandHud";
import { FallbackBanner } from "@/components/cockpit/FallbackBanner";
import { ModeBanner } from "@/components/cockpit/ModeBanner";
import { RealSafeModeOverlay } from "@/components/cockpit/RealSafeModeOverlay";
import { StatusBar } from "@/components/cockpit/StatusBar";
import { BirthProgressBanner } from "@/components/onboarding/BirthProgressBanner";
import { useRealSafeModeMonitor } from "@/hooks/useRealSafeModeMonitor";
import { connectCoreLive, disconnectCoreLive } from "@/lib/websocket";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { useVisualSettingsStore } from "@/store/visualSettingsStore";
import { cn } from "@/lib/utils";

interface CockpitShellProps {
  className?: string;
  children: ReactNode;
}

export function CockpitShell({ className, children }: CockpitShellProps) {
  const operatorMode = useCoreStore(selectCurrentMode);
  const hydrateOperatorMode = useCoreStore((state) => state.hydrateOperatorMode);
  const hydrateVisualSettings = useVisualSettingsStore(
    (state) => state.hydrateVisualSettings,
  );

  useEffect(() => {
    hydrateOperatorMode();
    hydrateVisualSettings();
    connectCoreLive();
    return () => disconnectCoreLive();
  }, [hydrateOperatorMode, hydrateVisualSettings]);

  useRealSafeModeMonitor();

  return (
    <div
      data-mode={operatorMode}
      className={cn(
        "cockpit-shell relative flex h-screen flex-col overflow-hidden text-foreground",
        className,
      )}
    >
      <div className="cockpit-stars pointer-events-none absolute inset-0" />
      <div className="cockpit-grid pointer-events-none absolute inset-0 opacity-40" />

      <CommandHud />
      <BirthProgressBanner />
      <ModeBanner />
      <FallbackBanner />

      <div className="relative z-10 min-h-0 flex-1 overflow-hidden p-3">
        {children}
      </div>

      <StatusBar />
      <RealSafeModeOverlay />
    </div>
  );
}
