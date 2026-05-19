import { Activity, Cpu, Gauge, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { Button } from "@/components/ui/button";
import { fetchLogTail, fetchOpsData, fetchTrainingReports, type OpsData, type TrainingReport } from "@/lib/opsClient";
import { CHART_AXIS_TICK, CHART_TOOLTIP_STYLE } from "@/lib/ppoEvolutionChartTheme";
import { selectRiskLevel, useCoreStore } from "@/store/coreStore";
import { useDeckPanelStore } from "@/store/deckPanelStore";
import { cn } from "@/lib/utils";
function MetricTile({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-black/30 px-3 py-2.5">
      <p className="font-mono text-[9px] tracking-[0.14em] text-muted-foreground uppercase">
        {label}
      </p>
      <p className="mt-1 font-mono text-sm tabular-nums text-cyan-100/90">
        {value}
        {suffix ? (
          <span className="ml-0.5 text-[10px] text-muted-foreground">{suffix}</span>
        ) : null}
      </p>
    </div>
  );
}

interface SystemMonitorPanelProps {
  className?: string;
}

export function SystemMonitorPanel({ className }: SystemMonitorPanelProps) {
  const { metrics, healthSnapshot, loading, error, apiKeyConfigured } =
    useAdaptiveIntelligenceContext();
  const riskLevel = useCoreStore(selectRiskLevel);
  const [ops, setOps] = useState<OpsData | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [trainingReports, setTrainingReports] = useState<TrainingReport[]>([]);
  const setActiveRightTab = useDeckPanelStore((s) => s.setActiveRightTab);

  const refreshOps = useCallback(async () => {
    if (!apiKeyConfigured) return;
    try {
      setOps(await fetchOpsData());
    } catch {
      setOps(null);
    }
  }, [apiKeyConfigured]);

  useEffect(() => {
    void refreshOps();
    const id = window.setInterval(() => void refreshOps(), 15_000);
    return () => window.clearInterval(id);
  }, [refreshOps]);

  useEffect(() => {
    if (!apiKeyConfigured) return;
    void fetchTrainingReports(10)
      .then(setTrainingReports)
      .catch(() => setTrainingReports([]));
  }, [apiKeyConfigured, metrics?.training_completed_trades]);

  useEffect(() => {
    if (!apiKeyConfigured) return;
    void fetchLogTail(20)
      .then((payload) => setLogLines(payload.lines ?? []))
      .catch(() => setLogLines([]));
  }, [apiKeyConfigured, metrics?.approval_twin_reward]);
  if (!apiKeyConfigured) {
    return <ApiKeySetupCallout className={className} />;
  }

  if (loading && !metrics) {
    return <p className={cn("text-xs text-muted-foreground", className)}>Loading system metrics…</p>;
  }

  if (error && !metrics) {
    return (
      <p className={cn("rounded-md border border-red-500/30 bg-red-950/20 p-3 text-xs text-red-200/90", className)}>
        {error.message}
      </p>
    );
  }

  const m = metrics!;
  const target = m.training_target_trades;
  const tradesPct =
    target > 0 ? Math.min(100, Math.round((m.training_completed_trades / target) * 100)) : 0;

  const pnlTrend = (ops?.daily_pnl_trend ?? []).map((row, idx) => ({
    label: String(row.day ?? row.date ?? idx + 1),
    pnl: Number(row.pnl ?? row.total_pnl ?? 0),
  }));
  const twinTrend = [
    { label: "now", reward: m.approval_twin_reward },
    ...(ops?.twin_decisions ?? []).slice(-8).map((row, idx) => ({
      label: String(idx + 1),
      reward: Number(row.score ?? row.reward ?? 0),
    })),
  ];

  return (
    <div className={cn("space-y-4", className)}>
      <section className="rounded-lg border border-white/10 bg-black/25 p-3">
        <div className="mb-2 flex items-center gap-2">
          <Activity className="size-3.5 text-cyan-300/80" />
          <h4 className="font-mono text-[10px] tracking-[0.16em] text-cyan-200/80 uppercase">
            System health
          </h4>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <MetricTile label="Status" value={healthSnapshot?.status ?? "unknown"} />
          <MetricTile label="Risk (deck)" value={riskLevel} />
          <MetricTile
            label="Uptime"
            value={healthSnapshot?.uptime_s != null ? `${Math.round(healthSnapshot.uptime_s)}s` : "—"}
          />
          <MetricTile
            label="Kill switch"
            value={healthSnapshot?.kill_switch_active ? "ACTIVE" : "Off"}
          />
          <MetricTile label="Regime" value={healthSnapshot?.current_regime ?? "—"} />
          <MetricTile label="Regime risk" value={healthSnapshot?.regime_risk_state ?? "—"} />
        </div>
        {healthSnapshot?.issues && healthSnapshot.issues.length > 0 ? (
          <ul className="mt-2 space-y-1 text-[11px] text-amber-200/85">
            {healthSnapshot.issues.map((issue) => (
              <li key={issue}>• {issue}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="rounded-lg border border-white/10 bg-black/25 p-3">
        <div className="mb-2 flex items-center gap-2">
          <Gauge className="size-3.5 text-violet-300/80" />
          <h4 className="font-mono text-[10px] tracking-[0.16em] text-violet-200/80 uppercase">
            Training horizon
          </h4>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <MetricTile label="Trades" value={String(m.training_completed_trades)} />
          <MetricTile label="Target" value={target > 0 ? String(target) : "—"} />
          <MetricTile label="Progress" value={target > 0 ? `${tradesPct}%` : "—"} />
          <MetricTile label="Phase" value={m.phase || m.first_boot_stage || "idle"} />
          <MetricTile label="PPO steps" value={m.ppo_steps.toLocaleString()} />
          <MetricTile label="PPO progress" value={`${m.ppo_progress_pct.toFixed(1)}%`} />
          <MetricTile label="Twin reward" value={m.approval_twin_reward.toFixed(3)} />
          <MetricTile
            label="ETA"
            value={m.eta_minutes != null ? `${Math.round(m.eta_minutes)}m` : "—"}
          />
        </div>
      </section>

      <section className="rounded-lg border border-white/10 bg-black/25 p-3">
        <div className="mb-2 flex items-center gap-2">
          <Cpu className="size-3.5 text-emerald-300/80" />
          <h4 className="font-mono text-[10px] tracking-[0.16em] text-emerald-200/80 uppercase">
            Resources
          </h4>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <MetricTile label="CPU" value={`${m.cpu.toFixed(1)}`} suffix="%" />
          <MetricTile label="GPU" value={`${m.gpu.toFixed(1)}`} suffix="%" />
          <MetricTile label="RAM" value={`${m.ram.toFixed(1)}`} suffix="%" />
          <MetricTile label="Velocity" value={m.velocity.toFixed(2)} />
          <MetricTile label="Historical" value={`${m.historical_days}`} suffix="d" />
          <MetricTile label="Synthetic" value={`${m.synthetic_percent.toFixed(1)}`} suffix="%" />
        </div>
        <div className="mt-2 flex items-center gap-2 font-mono text-[10px] text-muted-foreground">
          <Zap className="size-3" />
          Session: {m.session_kind || "idle"}
          {m.session_active ? " · active" : ""}
          {m.activity_stale ? " · stale" : ""}
        </div>
      </section>

      {ops ? (
        <>
          <section className="rounded-lg border border-white/10 bg-black/25 p-3">
            <h4 className="mb-2 font-mono text-[10px] tracking-[0.16em] text-cyan-200/80 uppercase">
              ApprovalTwin (recent)
            </h4>
            {ops.twin_decisions.length === 0 ? (
              <p className="text-xs text-muted-foreground">No twin decisions yet.</p>
            ) : (
              <ul className="space-y-1 text-[11px] text-muted-foreground">
                {ops.twin_decisions.slice(-5).map((row, idx) => (
                  <li key={idx} className="font-mono">
                    score {String(row.score ?? "—")} · {String(row.approve ?? row.decision ?? "—")}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="rounded-lg border border-white/10 bg-black/25 p-3">
            <h4 className="mb-2 font-mono text-[10px] tracking-[0.16em] text-violet-200/80 uppercase">
              Shadow runs
            </h4>
            <p className="text-xs text-muted-foreground">
              {Object.keys(ops.shadow_runs).length} tracked shadow deployment(s)
            </p>
          </section>
          <section className="rounded-lg border border-white/10 bg-black/25 p-3">
            <h4 className="mb-2 font-mono text-[10px] tracking-[0.16em] text-emerald-200/80 uppercase">
              Gate rejections (recent)
            </h4>
            <p className="font-mono text-sm text-cyan-100/90">{ops.gate_rejections.length}</p>
          </section>

          {(pnlTrend.length > 0 || twinTrend.length > 1) && (
            <section className="rounded-lg border border-white/10 bg-black/25 p-3">
              <h4 className="mb-2 font-mono text-[10px] tracking-[0.16em] text-cyan-200/80 uppercase">
                Trends
              </h4>
              <div className="grid gap-3 sm:grid-cols-2">
                {pnlTrend.length > 0 ? (
                  <div style={{ height: 120 }}>
                    <p className="mb-1 font-mono text-[9px] text-muted-foreground uppercase">Daily PnL</p>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={pnlTrend}>
                        <XAxis dataKey="label" tick={CHART_AXIS_TICK} hide />
                        <YAxis tick={CHART_AXIS_TICK} width={32} />
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                        <Line type="monotone" dataKey="pnl" stroke="#34d399" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : null}
                {twinTrend.length > 1 ? (
                  <div style={{ height: 120 }}>
                    <p className="mb-1 font-mono text-[9px] text-muted-foreground uppercase">Twin reward</p>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={twinTrend}>
                        <XAxis dataKey="label" tick={CHART_AXIS_TICK} hide />
                        <YAxis tick={CHART_AXIS_TICK} width={32} />
                        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                        <Line type="monotone" dataKey="reward" stroke="#a78bfa" dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : null}
              </div>
            </section>
          )}

          {trainingReports.length > 0 ? (
            <section className="rounded-lg border border-white/10 bg-black/25 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h4 className="font-mono text-[10px] tracking-[0.16em] text-violet-200/80 uppercase">
                  Training history
                </h4>
                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  onClick={() =>
                    void navigator.clipboard
                      .writeText(JSON.stringify(trainingReports, null, 2))
                      .then(() => undefined)
                  }
                >
                  Copy JSON
                </Button>
              </div>
              <ul className="space-y-2 text-[11px] text-muted-foreground">
                {trainingReports.slice(0, 5).map((report, index) => (
                  <li key={`${report._path ?? "report"}-${index}`} className="rounded border border-white/8 bg-black/20 px-2 py-1.5">
                    <p className="font-mono text-cyan-200/85">
                      {String(report._run_type ?? "Run")} ·{" "}
                      {report.timestamp ? new Date(String(report.timestamp)).toLocaleString() : "unknown time"}
                    </p>
                    <p className="mt-0.5 truncate font-mono text-[9px]">
                      trades {String(report.trades_completed ?? report.total_trades ?? "—")} · sharpe{" "}
                      {String(report.sharpe_annualized ?? report.sharpe ?? "—")}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="rounded-lg border border-white/10 bg-black/25 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h4 className="font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase">
                Log tail
              </h4>
              <Button type="button" size="xs" variant="ghost" onClick={() => setActiveRightTab("liveActivity")}>
                Open Activity
              </Button>
            </div>
            <pre className="max-h-24 overflow-auto font-mono text-[9px] text-muted-foreground">
              {logLines.length ? logLines.slice(-20).join("\n") : "No log lines"}
            </pre>
          </section>
        </>
      ) : null}
    </div>
  );
}