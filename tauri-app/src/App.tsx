import { Suspense, lazy, useEffect, useState } from "react";

import { CommandDeckTour } from "@/components/cockpit/CommandDeckTour";
import { CockpitShell } from "@/components/cockpit/CockpitShell";
import { CorePanelSlot } from "@/components/cockpit/CorePanelSlot";
import { EvolutionDeckPanel } from "@/components/cockpit/EvolutionDeckPanel";
import { FadeInView } from "@/components/cockpit/FadeInView";
import { PanelErrorBoundary } from "@/components/cockpit/PanelErrorBoundary";
import { DECK_LOADING_COPY } from "@/lib/deckLoadingCopy";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { OnboardingGate } from "@/components/onboarding/OnboardingGate";
import { IntelligenceDeckPanel } from "@/components/cockpit/IntelligenceDeckPanel";
import { RiskCitadel } from "@/components/RiskCitadel";
import { useTauriGlobalShortcuts } from "@/hooks/useTauriGlobalShortcuts";
import {
  selectConnectionStatus,
  selectCurrentMode,
  selectEvolutionState,
  selectFallbackMode,
  selectLiveMetrics,
  selectRiskLevel,
  useCoreStore,
} from "@/store/coreStore";
import { Toaster } from "sonner";

import { BirthConfirmHost } from "@/components/birth/BirthConfirmHost";

const LivingCore = lazy(() =>
  import("@/components/LivingCore").then((module) => ({
    default: module.LivingCore,
  })),
);

function CoreDebugPanel() {
  const [expanded, setExpanded] = useState(false);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const currentMode = useCoreStore(selectCurrentMode);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const riskLevel = useCoreStore(selectRiskLevel);
  const evolutionState = useCoreStore(selectEvolutionState);
  const lastSeq = useCoreStore((s) => s.lastSeq);
  const lastError = useCoreStore((s) => s.lastError);
  const reconnectAttempt = useCoreStore((s) => s.reconnectAttempt);

  const lastPayload = {
    seq: lastSeq,
    mode: currentMode.toLowerCase(),
    equity: liveMetrics.equity,
    regime: liveMetrics.regime,
    risk_level: riskLevel,
    active_mutations: evolutionState.activeMutations.map((mutation) => ({
      hash: mutation.hash,
      timestamp: mutation.timestamp,
      challenger_count: mutation.challengerCount,
    })),
    source_ts: liveMetrics.lastUpdatedTs,
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "d") {
        event.preventDefault();
        setExpanded((value) => !value);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <aside
      className="fixed bottom-12 right-3 z-50 max-w-sm rounded-lg border border-white/10 bg-black/70 font-mono text-[10px] text-cyan-100/90 shadow-lg backdrop-blur-md"
      aria-label="WebSocket debug panel"
    >
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-[9px] tracking-[0.18em] text-cyan-300/80 uppercase hover:bg-white/5"
        onClick={() => setExpanded((value) => !value)}
        title="Toggle debug panel (Ctrl+Shift+D)"
      >
        Debug — WS /ws/core/live
        <span className="text-muted-foreground">{expanded ? "▾" : "▸"}</span>
      </button>
      {expanded ? (
        <div className="border-t border-white/10 p-3">
          <dl className="space-y-1">
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Status</dt>
              <dd className="uppercase">{connectionStatus}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Fallback</dt>
              <dd className={fallbackMode ? "text-amber-300/90" : undefined}>
                {fallbackMode ? "true" : "false"}
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-muted-foreground">Mode</dt>
              <dd>{currentMode}</dd>
            </div>
            {lastError ? (
              <div className="flex gap-2 text-red-300/90">
                <dt>Error</dt>
                <dd>{lastError}</dd>
              </div>
            ) : null}
            {reconnectAttempt > 0 ? (
              <div className="flex gap-2 text-amber-300/90">
                <dt>Retry</dt>
                <dd>{reconnectAttempt}</dd>
              </div>
            ) : null}
          </dl>
          <pre className="mt-2 max-h-[120px] overflow-auto rounded border border-white/5 bg-black/40 p-2 text-[9px] leading-relaxed text-emerald-200/80">
            {JSON.stringify(lastPayload, null, 2)}
          </pre>
        </div>
      ) : null}
    </aside>
  );
}

function ThreeDPanelFallback() {
  return <PanelLoader label={DECK_LOADING_COPY.generic3d} className="min-h-[220px]" />;
}

function CommandDeckGrid() {
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const operatorMode = useCoreStore(selectCurrentMode);
  const telemetryPending =
    connectionStatus === "connecting" && liveMetrics.equity === null;

  return (
    <main className="command-deck-grid grid h-full min-h-0 gap-3">
      <FadeInView delay={0} className="command-deck-area-left flex min-h-0 flex-col gap-3">
        <div
          className="flex min-h-0 flex-col gap-3"
          data-mode={operatorMode}
          data-tour="risk-citadel"
        >
        <CorePanelSlot
          title="Risk Monitor"
          subtitle="Fortress integrity & drawdown buffer"
          className="min-h-[220px] overflow-hidden"
          frameVariant="muted"
          loading={telemetryPending}
          loadingLabel={DECK_LOADING_COPY.riskCitadel}
        >
          <PanelErrorBoundary panelName="Risk Monitor">
            <RiskCitadel key={operatorMode} className="h-full w-full" />
          </PanelErrorBoundary>
        </CorePanelSlot>

        <CorePanelSlot
          title="Neural Core"
          immersive
          frameless
          className="min-h-[280px] flex-1 overflow-hidden border-none"
          loading={telemetryPending}
          loadingLabel={DECK_LOADING_COPY.neuralCore}
        >
          <PanelErrorBoundary panelName="Neural Core">
            <Suspense fallback={<ThreeDPanelFallback />}>
              <LivingCore className="h-full w-full" />
            </Suspense>
          </PanelErrorBoundary>
        </CorePanelSlot>
        </div>
      </FadeInView>

      <FadeInView delay={0.08} layout className="command-deck-area-center min-h-[360px]">
        <PanelErrorBoundary panelName="Evolution Deck">
          <EvolutionDeckPanel className="h-full min-h-[360px]" frameVariant="muted" />
        </PanelErrorBoundary>
      </FadeInView>

      <FadeInView delay={0.16} className="command-deck-area-right min-h-[360px]">
        <PanelErrorBoundary panelName="Intelligence Deck">
          <IntelligenceDeckPanel className="h-full min-h-[360px]" frameVariant="glass" />
        </PanelErrorBoundary>
      </FadeInView>
    </main>
  );
}

function GlobalShortcutsProvider() {
  useTauriGlobalShortcuts();
  return null;
}

export default function App() {
  return (
    <>
      <OnboardingGate>
        {(phase) =>
          phase === "loading" ? (
            <div className="flex h-screen items-center justify-center bg-background text-sm text-muted-foreground">
              Initializing Neural Command Deck…
            </div>
          ) : (
            <>
              <GlobalShortcutsProvider />
              <CockpitShell>
                <CommandDeckGrid />
              </CockpitShell>
              <CommandDeckTour />
              {import.meta.env.DEV && localStorage.getItem("lumina.debugPanel") === "1" ? (
                <CoreDebugPanel />
              ) : null}
            </>
          )
        }
      </OnboardingGate>
      <BirthConfirmHost />
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          className: "lumina-glass lumina-glass--overlay font-mono text-xs",
        }}
      />
    </>
  );
}