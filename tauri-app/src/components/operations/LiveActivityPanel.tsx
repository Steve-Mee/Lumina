import { useCallback, useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { toast } from "sonner";

import { DeckMetricTile } from "@/components/cockpit/DeckMetricTile";
import { DeckSection } from "@/components/cockpit/DeckSection";
import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { Button } from "@/components/ui/button";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { fetchLogTail } from "@/lib/opsClient";
import { selectPanelRefreshMs, usePanelRefreshStore } from "@/store/panelRefreshStore";
import { fetchRuntimeStatus, type RuntimeStatus } from "@/lib/runtimeClient";
import { modeTitleClass } from "@/lib/modePresentation";
import { selectCurrentMode, selectTradingLive, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

export function LiveActivityPanel({ className }: { className?: string }) {
  const trading = useCoreStore(selectTradingLive);
  const operatorMode = useCoreStore(selectCurrentMode);
  const { metrics, apiKeyConfigured } = useAdaptiveIntelligenceContext();
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [viewCleared, setViewCleared] = useState(false);
  const refreshMs = usePanelRefreshStore(selectPanelRefreshMs);

  const refresh = useCallback(async () => {
    try {
      const [status, logs] = await Promise.all([fetchRuntimeStatus(), fetchLogTail(50)]);
      setRuntime(status);
      if (!viewCleared) {
        setLines(logs.lines ?? []);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Live activity refresh failed");
    }
  }, [viewCleared]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), refreshMs);
    return () => window.clearInterval(id);
  }, [refresh, refreshMs]);

  if (!apiKeyConfigured) {
    return <ApiKeySetupCallout className={className} />;
  }

  const heartbeat =
    runtime?.alive && metrics?.session_active && !metrics?.activity_stale
      ? "Live"
      : runtime?.alive
        ? "Stale"
        : "Stopped";

  const copyLastLines = async () => {
    const text = lines.slice(-50).join("\n");
    if (!text) {
      toast.warning("No log lines to copy");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied last 50 log lines");
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-1", className)}>
      <div className="flex items-center gap-2">
        <Activity className={cn("size-4", modeTitleClass(operatorMode))} />
        <h3 className={cn("deck-title text-[11px] tracking-[0.14em]", modeTitleClass(operatorMode))}>
          Live Activity
        </h3>
        <Button type="button" size="xs" variant="command-ghost" className="ml-auto" onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <DeckMetricTile
          label="Engine"
          value={runtime?.alive ? `Running (pid ${runtime.pid ?? "?"})` : "Stopped"}
        />
        <DeckMetricTile label="Heartbeat" value={heartbeat} />
        <DeckMetricTile label="Session" value={metrics?.session_kind ?? "idle"} />
        <DeckMetricTile
          label="Runtime state"
          value={trading?.runtime_state ? "Updated" : "Missing"}
        />
        <DeckMetricTile label="Open P&L" value={String(trading?.position.open_pnl ?? "—")} />
      </div>

      {trading ? (
        <DeckSection title="Live trading snapshot">
          <details className="text-[11px]">
            <summary className="cursor-pointer deck-accent-text font-mono">Expand JSON</summary>
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-muted-foreground">
              {JSON.stringify(trading, null, 2)}
            </pre>
          </details>
        </DeckSection>
      ) : null}

      <DeckSection title="Log tail" className="min-h-0 flex-1">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Button type="button" size="xs" variant="command-ghost" onClick={() => void copyLastLines()}>
            Copy last 50
          </Button>
          <Button
            type="button"
            size="xs"
            variant="command-ghost"
            onClick={() => {
              setViewCleared(true);
              setLines([]);
              toast.info("View cleared — logs on disk unchanged");
            }}
          >
            Clear view
          </Button>
        </div>
        <pre className="max-h-64 overflow-auto font-mono text-[10px] leading-relaxed text-muted-foreground">
          {viewCleared
            ? "View cleared (refresh to reload from disk)"
            : lines.length
              ? lines.join("\n")
              : "No log lines available"}
        </pre>
      </DeckSection>
    </div>
  );
}
