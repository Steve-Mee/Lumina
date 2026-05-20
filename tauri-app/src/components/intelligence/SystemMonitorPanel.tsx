import { Activity, Cpu, Gauge, Zap } from "lucide-react";

import { useCallback, useEffect, useState } from "react";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";



import { DeckMetricTile } from "@/components/cockpit/DeckMetricTile";

import { DeckSection } from "@/components/cockpit/DeckSection";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";

import { ReactDashboardButton } from "@/components/cockpit/ReactDashboardButton";

import { MonitoringDeepPanel } from "@/components/intelligence/MonitoringDeepPanel";

import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";

import { Button } from "@/components/ui/button";

import { fetchLogTail, fetchOpsData, fetchTrainingReports, type OpsData, type TrainingReport } from "@/lib/opsClient";

import { selectPanelRefreshMs, usePanelRefreshStore } from "@/store/panelRefreshStore";

import { chartThemeForMode } from "@/lib/ppoEvolutionChartTheme";

import { selectCurrentMode, selectRiskLevel, useCoreStore } from "@/store/coreStore";

import { useDeckPanelStore } from "@/store/deckPanelStore";

import { cn } from "@/lib/utils";



interface SystemMonitorPanelProps {

  className?: string;

}



export function SystemMonitorPanel({ className }: SystemMonitorPanelProps) {

  const { metrics, healthSnapshot, loading, error, apiKeyConfigured } =

    useAdaptiveIntelligenceContext();

  const riskLevel = useCoreStore(selectRiskLevel);
  const operatorMode = useCoreStore(selectCurrentMode);
  const chartTheme = chartThemeForMode(operatorMode);

  const [ops, setOps] = useState<OpsData | null>(null);

  const [logLines, setLogLines] = useState<string[]>([]);

  const [trainingReports, setTrainingReports] = useState<TrainingReport[]>([]);

  const setActiveRightTab = useDeckPanelStore((s) => s.setActiveRightTab);

  const refreshMs = usePanelRefreshStore(selectPanelRefreshMs);



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

    const id = window.setInterval(() => void refreshOps(), refreshMs);

    return () => window.clearInterval(id);

  }, [refreshOps, refreshMs]);



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

      <div className="flex flex-wrap items-center gap-2">

        <ReactDashboardButton />

      </div>



      <DeckSection title="System health" icon={Activity}>

        <div className="grid grid-cols-2 gap-2 text-xs">

          <DeckMetricTile label="Status" value={healthSnapshot?.status ?? "unknown"} />

          <DeckMetricTile label="Risk (deck)" value={riskLevel} />

          <DeckMetricTile

            label="Uptime"

            value={healthSnapshot?.uptime_s != null ? `${Math.round(healthSnapshot.uptime_s)}s` : "—"}

          />

          <DeckMetricTile

            label="Kill switch"

            value={healthSnapshot?.kill_switch_active ? "ACTIVE" : "Off"}

          />

          <DeckMetricTile label="Regime" value={healthSnapshot?.current_regime ?? "—"} />

          <DeckMetricTile label="Regime risk" value={healthSnapshot?.regime_risk_state ?? "—"} />

        </div>

        {healthSnapshot?.issues && healthSnapshot.issues.length > 0 ? (

          <ul className="mt-2 space-y-1 text-[11px] text-[var(--status-warn-fg)]">

            {healthSnapshot.issues.map((issue) => (

              <li key={issue}>• {issue}</li>

            ))}

          </ul>

        ) : null}

      </DeckSection>



      <DeckSection title="Training horizon" icon={Gauge}>

        <div className="grid grid-cols-2 gap-2">

          <DeckMetricTile label="Trades" value={String(m.training_completed_trades)} />

          <DeckMetricTile label="Target" value={target > 0 ? String(target) : "—"} />

          <DeckMetricTile label="Progress" value={target > 0 ? `${tradesPct}%` : "—"} />

          <DeckMetricTile label="Phase" value={m.phase || m.first_boot_stage || "idle"} />

          <DeckMetricTile label="PPO steps" value={m.ppo_steps.toLocaleString()} />

          <DeckMetricTile label="PPO progress" value={`${m.ppo_progress_pct.toFixed(1)}%`} />

          <DeckMetricTile label="Twin reward" value={m.approval_twin_reward.toFixed(3)} />

          <DeckMetricTile

            label="ETA"

            value={m.eta_minutes != null ? `${Math.round(m.eta_minutes)}m` : "—"}

          />

        </div>

      </DeckSection>



      <DeckSection title="Resources" icon={Cpu}>

        <div className="grid grid-cols-3 gap-2">

          <DeckMetricTile label="CPU" value={`${m.cpu.toFixed(1)}`} suffix="%" />

          <DeckMetricTile label="GPU" value={`${m.gpu.toFixed(1)}`} suffix="%" />

          <DeckMetricTile label="RAM" value={`${m.ram.toFixed(1)}`} suffix="%" />

          <DeckMetricTile label="Velocity" value={m.velocity.toFixed(2)} />

          <DeckMetricTile label="Historical" value={`${m.historical_days}`} suffix="d" />

          <DeckMetricTile label="Synthetic" value={`${m.synthetic_percent.toFixed(1)}`} suffix="%" />

        </div>

        <div className="mt-2 flex items-center gap-2 font-mono text-[10px] text-muted-foreground">

          <Zap className="size-3" />

          Session: {m.session_kind || "idle"}

          {m.session_active ? " · active" : ""}

          {m.activity_stale ? " · stale" : ""}

        </div>

      </DeckSection>



      {ops ? (

        <>

          <DeckSection title="ApprovalTwin (recent)">

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

          </DeckSection>



          <DeckSection title="Shadow runs">

            <p className="text-xs text-muted-foreground">

              {Object.keys(ops.shadow_runs).length} tracked shadow deployment(s)

            </p>

          </DeckSection>



          <DeckSection title="Gate rejections (recent)">

            <p className="deck-metric-tile__value text-sm">{ops.gate_rejections.length}</p>

          </DeckSection>



          {(pnlTrend.length > 0 || twinTrend.length > 1) && (

            <DeckSection title="Trends">

              <div className="grid gap-3 sm:grid-cols-2">

                {pnlTrend.length > 0 ? (

                  <div style={{ height: 120 }}>

                    <p className="mb-1 font-mono text-[9px] text-muted-foreground uppercase">Daily PnL</p>

                    <ResponsiveContainer width="100%" height="100%">

                      <LineChart data={pnlTrend}>

                        <XAxis dataKey="label" tick={chartTheme.axisTick} hide />

                        <YAxis tick={chartTheme.axisTick} width={32} />

                        <Tooltip contentStyle={chartTheme.tooltip} />

                        <Line type="monotone" dataKey="pnl" stroke={chartTheme.colors.positive} dot={false} />

                      </LineChart>

                    </ResponsiveContainer>

                  </div>

                ) : null}

                {twinTrend.length > 1 ? (

                  <div style={{ height: 120 }}>

                    <p className="mb-1 font-mono text-[9px] text-muted-foreground uppercase">Twin reward</p>

                    <ResponsiveContainer width="100%" height="100%">

                      <LineChart data={twinTrend}>

                        <XAxis dataKey="label" tick={chartTheme.axisTick} hide />

                        <YAxis tick={chartTheme.axisTick} width={32} />

                        <Tooltip contentStyle={chartTheme.tooltip} />

                        <Line type="monotone" dataKey="reward" stroke={chartTheme.colors.entropy} dot={false} />

                      </LineChart>

                    </ResponsiveContainer>

                  </div>

                ) : null}

              </div>

            </DeckSection>

          )}



          {trainingReports.length > 0 ? (

            <DeckSection title="Training history">

              <div className="mb-2 flex flex-wrap items-center justify-end gap-2">

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

                  <li key={`${report._path ?? "report"}-${index}`} className="deck-section rounded px-2 py-1.5">

                    <p className="deck-accent-text font-mono">

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

            </DeckSection>

          ) : null}



          <DeckSection title="Log tail">

            <div className="mb-2 flex items-center justify-end gap-2">

              <Button type="button" size="xs" variant="ghost" onClick={() => setActiveRightTab("liveActivity")}>

                Open Activity

              </Button>

            </div>

            <pre className="max-h-24 overflow-auto font-mono text-[9px] text-muted-foreground">

              {logLines.length ? logLines.slice(-20).join("\n") : "No log lines"}

            </pre>

          </DeckSection>

        </>

      ) : null}



      <MonitoringDeepPanel />

    </div>

  );

}


