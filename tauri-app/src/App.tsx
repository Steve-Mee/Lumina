import { Suspense, lazy } from "react";

import { CockpitShell } from "@/components/cockpit/CockpitShell";
import { CorePanelSlot } from "@/components/cockpit/CorePanelSlot";
import { FadeInView } from "@/components/cockpit/FadeInView";
import { PanelErrorBoundary } from "@/components/cockpit/PanelErrorBoundary";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { OnboardingGate } from "@/components/onboarding/OnboardingGate";
import { DecisionTheater } from "@/components/DecisionTheater";
import { RiskCitadel } from "@/components/RiskCitadel";
import { useTauriGlobalShortcuts } from "@/hooks/useTauriGlobalShortcuts";import {
  selectConnectionStatus,
  selectCurrentMode,
  selectEvolutionState,
  selectFallbackMode,
  selectLiveMetrics,
  selectRiskLevel,
  useCoreStore,
} from "@/store/coreStore";
import { Toaster } from "sonner";

const LivingCore = lazy(() =>
  import("@/components/LivingCore").then((module) => ({
    default: module.LivingCore,
  })),
);

const EvolutionArena = lazy(() =>
  import("@/components/EvolutionArena").then((module) => ({
    default: module.EvolutionArena,
  })),
);

function CoreDebugPanel() {
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

  return (
    <aside
      className="fixed bottom-12 right-3 z-50 max-w-sm rounded-lg border border-white/10 bg-black/70 p-3 font-mono text-[10px] text-cyan-100/90 shadow-lg backdrop-blur-md"
      aria-label="WebSocket debug panel"
    >
      <p className="mb-2 text-[9px] tracking-[0.18em] text-cyan-300/80 uppercase">
        Debug — WS /ws/core/live
      </p>
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
    </aside>
  );
}

function ThreeDPanelFallback() {
  return <PanelLoader label="Loading 3D module…" className="min-h-[220px]" />;
}

function CommandDeckGrid() {
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const telemetryPending =
    connectionStatus === "connecting" && liveMetrics.equity === null;

  return (
    <main className="command-deck-grid grid h-full min-h-0 gap-3">
      <FadeInView delay={0} className="command-deck-area-left flex min-h-0 flex-col gap-3">
        <CorePanelSlot
          title="Risk Monitor"
          subtitle="VaR, drawdown & policy verdicts"
          className="min-h-[220px] overflow-hidden"
          loading={telemetryPending}
          loadingLabel="Connecting risk citadel…"
        >
          <PanelErrorBoundary panelName="Risk Monitor">
            <RiskCitadel className="h-full w-full" />
          </PanelErrorBoundary>
        </CorePanelSlot>

        <CorePanelSlot
          title="Neural Core"
          subtitle="Central organism visualization"
          className="min-h-[280px] flex-1 overflow-hidden"
          loading={telemetryPending}
          loadingLabel="Awakening neural core…"
        >
          <PanelErrorBoundary panelName="Neural Core">
            <Suspense fallback={<ThreeDPanelFallback />}>
              <LivingCore className="h-full w-full" />
            </Suspense>
          </PanelErrorBoundary>
        </CorePanelSlot>
      </FadeInView>

      <FadeInView delay={0.08} layout className="command-deck-area-center min-h-[360px]">
        <CorePanelSlot
          title="Evolution Queue"
          subtitle="Pending mutation proposals"
          className="min-h-[360px] overflow-hidden"
        >
          <PanelErrorBoundary panelName="Evolution Arena">
            <Suspense fallback={<ThreeDPanelFallback />}>
              <EvolutionArena className="h-full w-full" />
            </Suspense>
          </PanelErrorBoundary>
        </CorePanelSlot>
      </FadeInView>

      <FadeInView delay={0.16} className="command-deck-area-right min-h-[360px]">
        <CorePanelSlot
          title="Intelligence"
          subtitle="Decision theater & reasoning chain"
          className="min-h-[360px] overflow-hidden"
        >
          <PanelErrorBoundary panelName="Decision Theater">
            <DecisionTheater className="h-full w-full" />
          </PanelErrorBoundary>
        </CorePanelSlot>
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
              {import.meta.env.DEV ? <CoreDebugPanel /> : null}
            </>
          )
        }
      </OnboardingGate>
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          className: "font-mono text-xs border border-white/10 bg-black/85",
        }}
      />
    </>
  );
}