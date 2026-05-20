import { useCallback, useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import { DeckSection } from "@/components/cockpit/DeckSection";
import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { Button } from "@/components/ui/button";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import {
  fetchMetricsJson,
  fetchMonitoringDiagnostics,
  fetchWorkspaceSnapshot,
  type MonitoringDiagnostics,
} from "@/lib/opsClient";
import { runOvernightSim } from "@/lib/runtimeClient";
import { CHART_AXIS_TICK, CHART_TOOLTIP_STYLE } from "@/lib/ppoEvolutionChartTheme";
import { selectPanelRefreshMs, usePanelRefreshStore } from "@/store/panelRefreshStore";
import { cn } from "@/lib/utils";

type MonitorTab =
  | "debug"
  | "overview"
  | "firstboot"
  | "errors"
  | "trends"
  | "observability";

const TAB_LABELS: Record<MonitorTab, string> = {
  debug: "Debug",
  overview: "Overview",
  firstboot: "First Boot",
  errors: "Health & Errors",
  trends: "Trends",
  observability: "Observability",
};

export function MonitoringDeepPanel({ className }: { className?: string }) {
  const { apiKeyConfigured } = useAdaptiveIntelligenceContext();
  const refreshMs = usePanelRefreshStore(selectPanelRefreshMs);
  const [tab, setTab] = useState<MonitorTab>("overview");
  const [diag, setDiag] = useState<MonitoringDiagnostics | null>(null);
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);
  const [metricsJson, setMetricsJson] = useState<Record<string, unknown> | null>(null);

  const refresh = useCallback(async () => {
    if (!apiKeyConfigured) return;
    try {
      const [d, s, m] = await Promise.all([
        fetchMonitoringDiagnostics(),
        fetchWorkspaceSnapshot(),
        fetchMetricsJson().catch(() => null),
      ]);
      setDiag(d);
      setSnapshot(s);
      setMetricsJson(m);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Monitoring refresh failed");
    }
  }, [apiKeyConfigured]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), refreshMs);
    return () => window.clearInterval(id);
  }, [refresh, refreshMs]);

  if (!apiKeyConfigured) {
    return <ApiKeySetupCallout className={className} />;
  }

  const latencyChart = (diag?.reasoning_latency ?? []).map((row, idx) => ({
    label: String(idx + 1),
    ms: Number(row.elapsed_ms ?? row.latency_ms ?? 0),
  }));
  const modelChart = (diag?.model_load_times ?? []).map((row, idx) => ({
    label: String(idx + 1),
    ms: Number(row.load_ms ?? row.elapsed_ms ?? 0),
  }));

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap gap-1">
        {(Object.keys(TAB_LABELS) as MonitorTab[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cn("deck-tab-chip", tab === key && "deck-tab-chip--active")}
          >
            {TAB_LABELS[key]}
          </button>
        ))}
        <Button type="button" size="xs" variant="ghost" className="ml-auto" onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      {tab === "debug" ? (
        <DeckSection title="Debug controls">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() =>
                void runOvernightSim(240)
                  .then((r) => toast.success(r.message))
                  .catch((e) => toast.error(e instanceof Error ? e.message : "Failed"))
              }
            >
              Overnight SIM (240m)
            </Button>
          </div>
        </DeckSection>
      ) : null}

      {tab === "overview" ? (
        <DeckSection title="System overview">
          <div className="text-[11px] text-muted-foreground">
            <p>Mode: {String(snapshot?.config_mode ?? "—")}</p>
            <p>Workspace: {String(diag?.paths?.workspace_root ?? "—")}</p>
            <pre className="mt-2 max-h-32 overflow-auto font-mono text-[9px]">
              {JSON.stringify(snapshot?.runtime_metrics ?? {}, null, 2)}
            </pre>
          </div>
        </DeckSection>
      ) : null}

      {tab === "firstboot" ? (
        <DeckSection title="First boot progress">
          <pre className="max-h-40 overflow-auto font-mono text-[9px] text-muted-foreground">
            {JSON.stringify(snapshot?.first_boot_progress ?? {}, null, 2)}
          </pre>
        </DeckSection>
      ) : null}

      {tab === "errors" ? (
        <div className="space-y-2">
          <DeckSection title="Structured errors">
            <ul className="max-h-36 space-y-1 overflow-auto text-[10px] text-muted-foreground">
              {(diag?.structured_errors ?? []).slice(-15).map((row, idx) => (
                <li key={idx} className="deck-section rounded px-2 py-1 font-mono">
                  {String(row.message ?? row.error ?? JSON.stringify(row))}
                </li>
              ))}
            </ul>
          </DeckSection>
          <DeckSection title="Twin training (recent)">
            <ul className="max-h-24 space-y-1 overflow-auto text-[10px] font-mono text-muted-foreground">
              {(diag?.twin_training ?? []).slice(-8).map((row, idx) => (
                <li key={idx}>{JSON.stringify(row)}</li>
              ))}
            </ul>
          </DeckSection>
        </div>
      ) : null}

      {tab === "trends" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {latencyChart.length > 0 ? (
            <DeckSection title="Reasoning latency" className="p-2">
              <div style={{ height: 120 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={latencyChart}>
                    <XAxis dataKey="label" tick={CHART_AXIS_TICK} hide />
                    <YAxis tick={CHART_AXIS_TICK} width={32} />
                    <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                    <Line type="monotone" dataKey="ms" stroke="#34d399" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </DeckSection>
          ) : null}
          {modelChart.length > 0 ? (
            <DeckSection title="Model load times" className="p-2">
              <div style={{ height: 120 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={modelChart}>
                    <XAxis dataKey="label" tick={CHART_AXIS_TICK} hide />
                    <YAxis tick={CHART_AXIS_TICK} width={32} />
                    <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                    <Line type="monotone" dataKey="ms" stroke="#a78bfa" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </DeckSection>
          ) : null}
        </div>
      ) : null}

      {tab === "observability" ? (
        <DeckSection title="Backend metrics JSON">
          <pre className="max-h-48 overflow-auto font-mono text-[9px] text-muted-foreground">
            {metricsJson ? JSON.stringify(metricsJson, null, 2) : "Loading…"}
          </pre>
          <a
            className="deck-accent-text mt-2 inline-block font-mono text-[10px] underline"
            href={`${import.meta.env.VITE_LUMINA_BACKEND_URL ?? "http://127.0.0.1:8000"}/api/monitoring/metrics`}
            target="_blank"
            rel="noreferrer"
          >
            Open Prometheus metrics
          </a>
        </DeckSection>
      ) : null}
    </div>
  );
}
