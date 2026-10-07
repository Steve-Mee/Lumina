import { useEffect, useState } from "react";

import { CommandDeckTour } from "@/components/cockpit/CommandDeckTour";
import { CockpitShell } from "@/components/cockpit/CockpitShell";
import { CommandDeckScreen } from "@/components/cockpit/CommandDeckScreen";
import { OnboardingGate } from "@/components/onboarding/OnboardingGate";
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
import { useOnboardingStore } from "@/store/onboardingStore";
import { Toaster } from "sonner";

import { BirthConfirmHost } from "@/components/birth/BirthConfirmHost";
import { TwinEscalationModal } from "@/components/operations/TwinEscalationModal";

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

function GlobalShortcutsProvider() {
  useTauriGlobalShortcuts();
  return null;
}

/** No toast storm during cold-start readiness cover. */
function AppToaster() {
  const phase = useOnboardingStore((s) => s.phase);
  const ntStartupResolved = useOnboardingStore((s) => s.ntStartupResolved);
  if (phase === "loading" || !ntStartupResolved) {
    return null;
  }
  return (
    <Toaster
      theme="dark"
      position="top-right"
      toastOptions={{
        className: "lumina-glass lumina-glass--overlay font-mono text-xs",
      }}
    />
  );
}

export default function App() {
  return (
    <>
      <OnboardingGate>
        {() => (
          <>
            <GlobalShortcutsProvider />
            <CockpitShell>
              <CommandDeckScreen />
            </CockpitShell>
            <CommandDeckTour />
            {import.meta.env.DEV && localStorage.getItem("lumina.debugPanel") === "1" ? (
              <CoreDebugPanel />
            ) : null}
          </>
        )}
      </OnboardingGate>
      <BirthConfirmHost />
      <TwinEscalationModal />
      <AppToaster />
    </>
  );
}