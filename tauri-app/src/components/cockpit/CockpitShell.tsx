import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { OrganismEnvelopeProvider } from "@/context/OrganismEnvelopeContext";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import { resolveDeckPhaseHeader } from "@/lib/luminaPhasePresentation";
import { DeckBlockingOverlay } from "@/components/cockpit/DeckBlockingOverlay";
import { PPOEvolutionProvider } from "@/context/PPOEvolutionContext";
import { AdaptiveIntelligenceProvider } from "@/context/AdaptiveIntelligenceContext";
import { RealSafeModeOverlay } from "@/components/cockpit/RealSafeModeOverlay";
import { useOrganismClock } from "@/hooks/useOrganismClock";
import { useRealSafeModeMonitor } from "@/hooks/useRealSafeModeMonitor";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { useDeckStatusSyncToast } from "@/hooks/useDeckStatusResolution";
import { useDeckLifecycleGuard } from "@/hooks/useDeckLifecycleGuard";
import { postPlaygroundDeckLive } from "@/lib/maturationClient";
import { fetchAndHydrateDeckApiKey } from "@/lib/setupClient";
import { connectCoreLive, disconnectCoreLive } from "@/lib/websocket";
import { useApiKeyStore } from "@/store/apiKeyStore";
import {
  selectCurrentMode,
  selectModeSyncStatus,
  useCoreStore,
} from "@/store/coreStore";
import { useOnboardingStore } from "@/store/onboardingStore";
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
  const appSurface = useOnboardingStore((s) => s.payload?.app_surface);

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

  useEffect(() => {
    if (appSurface !== "playground") return;
    void postPlaygroundDeckLive().catch(() => undefined);
  }, [appSurface]);

  useRealSafeModeMonitor();
  useDeckLifecycleGuard();

  return (
    <OrganismEnvelopeProvider>
      <div
        ref={shellRef}
        data-mode={operatorMode}
        className={cn(
          "cockpit-shell cockpit-shell--phase birth-phase-screen birth-phase-screen--cinematic lumina-glow-ambient relative h-dvh max-h-dvh min-h-0 overflow-hidden text-foreground",
          className,
        )}
      >
        <div className="cockpit-stars pointer-events-none absolute inset-0" />
        <div className="cockpit-grid pointer-events-none absolute inset-0 opacity-40" />

        <PPOEvolutionProvider>
          <AdaptiveIntelligenceProvider>
            <LuminaPhaseHeader
              {...resolveDeckPhaseHeader(operatorMode)}
              variant="compact"
              className="lumina-phase-header relative z-20 shrink-0"
            />
            <EvolutionLadderStrip className="relative z-20 evolution-ladder-strip--dense !py-1" />
            <DeckBlockingOverlay />

            <div className="cockpit-shell__stage relative z-10 min-h-0 overflow-hidden">
              {children}
            </div>

            <RealSafeModeOverlay />
          </AdaptiveIntelligenceProvider>
        </PPOEvolutionProvider>
      </div>
    </OrganismEnvelopeProvider>
  );
}
