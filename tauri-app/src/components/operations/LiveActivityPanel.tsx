import { useCallback, useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { toast } from "sonner";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { Button } from "@/components/ui/button";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { fetchLogTail } from "@/lib/opsClient";
import { fetchRuntimeStatus, type RuntimeStatus } from "@/lib/runtimeClient";
import { selectTradingLive, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

export function LiveActivityPanel({ className }: { className?: string }) {
  const trading = useCoreStore(selectTradingLive);
  const { metrics, apiKeyConfigured } = useAdaptiveIntelligenceContext();
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [viewCleared, setViewCleared] = useState(false);

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
    const id = window.setInterval(() => void refresh(), 10_000);
    return () => window.clearInterval(id);
  }, [refresh]);

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
        <Activity className="size-4 text-cyan-300/90" />
        <h3 className="font-mono text-[11px] tracking-[0.14em] text-cyan-200/90 uppercase">
          Live Activity
        </h3>
        <Button type="button" size="xs" variant="ghost" className="ml-auto" onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          Engine:{" "}
          <span className={runtime?.alive ? "text-emerald-300" : "text-muted-foreground"}>
            {runtime?.alive ? `Running (pid ${runtime.pid ?? "?"})` : "Stopped"}
          </span>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          Heartbeat: <span className="font-mono">{heartbeat}</span>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          Session: <span className="font-mono">{metrics?.session_kind ?? "idle"}</span>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          Runtime state:{" "}
          <span className={trading?.runtime_state ? "text-emerald-300" : "text-muted-foreground"}>
            {trading?.runtime_state ? "Updated" : "Missing"}
          </span>
        </div>
        <div className="rounded border border-white/10 bg-black/25 px-3 py-2">
          Open P&L: <span className="font-mono">{trading?.position.open_pnl ?? "—"}</span>
        </div>
      </div>

      {trading ? (
        <details className="rounded border border-white/10 bg-black/20 p-2 text-[11px]">
          <summary className="cursor-pointer font-mono text-cyan-200/80">Live trading snapshot</summary>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-muted-foreground">
            {JSON.stringify(trading, null, 2)}
          </pre>
        </details>
      ) : null}

      <div className="min-h-0 flex-1 rounded-lg border border-white/10 bg-black/30 p-2">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <p className="font-mono text-[9px] uppercase text-muted-foreground">Log tail</p>
          <Button type="button" size="xs" variant="ghost" onClick={() => void copyLastLines()}>
            Copy last 50
          </Button>
          <Button
            type="button"
            size="xs"
            variant="ghost"
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
      </div>
    </div>
  );
}
