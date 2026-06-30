import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { OrganismEnvelopeProvider } from "@/context/OrganismEnvelopeContext";
import { CommandHud } from "@/components/cockpit/CommandHud";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import { resolveDeckPhaseHeader } from "@/lib/luminaPhasePresentation";
import { DeckBlockingOverlay } from "@/components/cockpit/DeckBlockingOverlay";
import { PPOEvolutionProvider } from "@/context/PPOEvolutionContext";
import { AdaptiveIntelligenceProvider } from "@/context/AdaptiveIntelligenceContext";
import { RealSafeModeOverlay } from "@/components/cockpit/RealSafeModeOverlay";
import { StatusBar } from "@/components/cockpit/StatusBar";
import { useOrganismClock } from "@/hooks/useOrganismClock";
import { useRealSafeModeMonitor } from "@/hooks/useRealSafeModeMonitor";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { useDeckStatusSyncToast } from "@/hooks/useDeckStatusResolution";
import { useDeckLifecycleGuard } from "@/hooks/useDeckLifecycleGuard";
import { fetchAndHydrateDeckApiKey } from "@/lib/setupClient";
import { connectCoreLive, disconnectCoreLive } from "@/lib/websocket";
import { useApiKeyStore } from "@/store/apiKeyStore";
import {
  selectCurrentMode,
  selectModeSyncStatus,
  useCoreStore,
} from "@/store/coreStore";
import { useVisualSettingsStore, selectVisualQuality } from "@/store/visualSettingsStore";
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

  const hydrateApiKey = useApiKeyStore((s) => s.hydrate);
  const modeSyncStatus = useCoreStore(selectModeSyncStatus);
  const modeSyncError = useCoreStore((s) => s.modeSyncError);
  const suppressSyncToast = useDeckStatusSyncToast();
  const lastModeErrorToast = useRef<string | null>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const reducedMotion = usePrefersReducedMotion();
  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const clockFrozen = visualQuality === "low";

  useOrganismClock(shellRef, operatorMode, reducedMotion, clockFrozen);

  useEffect(() => {
    if (modeSyncStatus === "error" && modeSyncError && !suppressSyncToast) {
      if (lastModeErrorToast.current !== modeSyncError) {
        lastModeErrorToast.current = modeSyncError;
        toast.error(modeSyncError);
      }
    } else if (modeSyncStatus !== "error") {
      lastModeErrorToast.current = null;
    }
  }, [modeSyncStatus, modeSyncError, suppressSyncToast]);

  useEffect(() => {
    hydrateOperatorMode();
    hydrateVisualSettings();
    void fetchAndHydrateDeckApiKey().then((ok) => {
      if (ok) hydrateApiKey();
    });
    connectCoreLive();
    return () => disconnectCoreLive();
  }, [hydrateOperatorMode, hydrateVisualSettings, hydrateApiKey]);

  useRealSafeModeMonitor();
  useDeckLifecycleGuard();

  return (
    <OrganismEnvelopeProvider>
      <div
        ref={shellRef}
        data-mode={operatorMode}
        className={cn(
          "cockpit-shell lumina-glow-ambient relative flex h-screen flex-col overflow-hidden text-foreground",
          className,
        )}
      >
        <div className="cockpit-stars pointer-events-none absolute inset-0" />
        <div className="cockpit-grid pointer-events-none absolute inset-0 opacity-40" />
        <div className="deck-vignette pointer-events-none" aria-hidden />

        <PPOEvolutionProvider>
          <AdaptiveIntelligenceProvider>
            <LuminaPhaseHeader
              {...resolveDeckPhaseHeader(operatorMode)}
              variant="strip"
              className="relative z-20 shrink-0"
            />
            <CommandHud />
            <DeckBlockingOverlay />

            <div className="relative z-10 min-h-0 flex-1 overflow-hidden p-3">
              {children}
            </div>

            <StatusBar />
            <RealSafeModeOverlay />
          </AdaptiveIntelligenceProvider>
        </PPOEvolutionProvider>
      </div>
    </OrganismEnvelopeProvider>
  );
}
