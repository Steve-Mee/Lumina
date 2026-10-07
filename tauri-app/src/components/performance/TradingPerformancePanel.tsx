import { useState, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { BirthKpiTile, type BirthKpiTone } from "@/components/birth/BirthKpiTile";
import { StatusChip } from "@/components/birth/BirthGenesisDeckPrimitives";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { useTradingPerformance } from "@/hooks/useTradingPerformance";
import { chartThemeForMode } from "@/lib/ppoEvolutionChartTheme";
import {
  formatMaxDrawdownPct,
  formatProfitFactor,
  formatSharpe,
  formatUsd,
  formatWinrate,
  kpiToneClass,
} from "@/lib/tradingPerformanceModel";
import { selectCurrentMode, selectFortress, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface TradingPerformancePanelProps {
  className?: string;
}

function kpiTileTone(kind: "sharpe" | "drawdown", value: number, killPct?: number): BirthKpiTone {
  const cls = kpiToneClass(kind, value, killPct);
  if (cls.includes("emerald")) return "success";
  if (cls.includes("amber")) return "warn";
  return "accent";
}

function pnlTileTone(amount: number | null): BirthKpiTone {
  if (amount == null || amount === 0) return "default";
  return amount > 0 ? "success" : "warn";
}

function ChartCard({
  title,
  children,
  height = 160,
}: {
  title: string;
  children: ReactNode;
  height?: number;
}) {
  return (
    <section className="risk-envelope-field-card command-deck-ops__perf-chart flex min-h-0 flex-col">
      <p className="risk-envelope-field-label">{title}</p>
      <div className="mt-2 min-h-0 flex-1" style={{ height }}>
        {children}
      </div>
    </section>
  );
}

function ChartEmpty({ copy }: { copy: string }) {
  return (
    <p className="flex h-full items-center justify-center font-mono text-[11px] tracking-wide text-white/40">
      {copy}
    </p>
  );
}

export function TradingPerformancePanel({ className }: TradingPerformancePanelProps) {
  const [pnlExpanded, setPnlExpanded] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const mode = useCoreStore(selectCurrentMode);
  const chartTheme = chartThemeForMode(mode);
  const equityStroke = chartTheme.colors.equity;
  const { view, connected, tradesError } = useTradingPerformance();
  const fortress = useCoreStore(selectFortress);
  const drawdownKillPct = fortress?.drawdown_kill_pct ?? 8;
  const animationActive = !reducedMotion;
  const equityData = view.equityChart.map((point) => ({
    t: point.t,
    equity: point.equity,
  }));

  return (
    <div className={cn("command-deck-ops__performance", className)}>
      <div
        className="command-deck-ops__arena-strip"
        role="status"
        aria-label="Performance telemetry"
      >
        <StatusChip
          label={connected ? "LIVE" : "OFFLINE"}
          state={connected ? "ok" : "warn"}
          tip={connected ? `Telemetry source ${view.source}.` : "Live stream is not connected."}
        />
        <StatusChip
          label={view.source.toUpperCase()}
          state={view.hasLiveData ? "partial" : "idle"}
          tip="Where session KPIs are read from."
        />
        <StatusChip
          label={view.hasLiveData ? "SESSION" : "STANDBY"}
          state={view.hasLiveData ? "ok" : "idle"}
          tip="Live session occupancy. Standby until the engine publishes equity."
        />
      </div>

      {!view.hasLiveData ? (
        <p className="font-mono text-[11px] leading-relaxed tracking-wide text-white/45">
          Awaiting live session data. KPIs fill from the last run summary when the engine is
          offline.
        </p>
      ) : null}

      <div className="command-deck-ops__perf-kpis">
        <BirthKpiTile label="Winrate" value={formatWinrate(view.kpis.winrate)} tone="accent" />
        <BirthKpiTile
          label="Sharpe"
          value={formatSharpe(view.kpis.sharpeAnnualized)}
          detail="annualized"
          tone={kpiTileTone("sharpe", view.kpis.sharpeAnnualized)}
        />
        <BirthKpiTile
          label="Max DD"
          value={formatMaxDrawdownPct(view.kpis.maxDrawdownPct)}
          detail={`kill ${drawdownKillPct}%`}
          tone={kpiTileTone("drawdown", view.kpis.maxDrawdownPct, drawdownKillPct)}
        />
        <BirthKpiTile
          label="Profit factor"
          value={formatProfitFactor(view.kpis.profitFactor)}
          tone={view.kpis.profitFactor >= 1 ? "success" : "default"}
        />
      </div>

      <button
        type="button"
        className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle command-deck-ops__organ-btn"
        aria-expanded={pnlExpanded}
        onClick={() => setPnlExpanded((open) => !open)}
      >
        {pnlExpanded ? "Hide session P&L" : "Session P&L"}
      </button>
      {pnlExpanded ? (
        <div className="command-deck-ops__perf-kpis command-deck-ops__perf-kpis--three">
          <BirthKpiTile
            label="Daily P&L"
            value={formatUsd(view.dailyPnl)}
            tone={pnlTileTone(view.dailyPnl)}
          />
          <BirthKpiTile
            label="Open P&L"
            value={formatUsd(view.openPnl)}
            tone={pnlTileTone(view.openPnl)}
          />
          <BirthKpiTile
            label="Realized"
            value={formatUsd(view.sessionRealizedPnl)}
            tone={pnlTileTone(view.sessionRealizedPnl)}
          />
        </div>
      ) : null}

      <ChartCard title="Live equity" height={168}>
        {equityData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={equityData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={equityStroke} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={equityStroke} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="t" hide />
              <YAxis
                tick={chartTheme.axisTick}
                width={52}
                tickFormatter={(v: number) =>
                  v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v.toFixed(0)}`
                }
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={chartTheme.tooltip}
                formatter={(value) => [
                  `$${Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
                  "Equity",
                ]}
                labelFormatter={() => ""}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke={equityStroke}
                strokeWidth={2}
                fill="url(#equityGradient)"
                dot={false}
                activeDot={{ r: 4, fill: equityStroke, stroke: "#fff", strokeWidth: 1 }}
                isAnimationActive={animationActive}
                animationDuration={280}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <ChartEmpty copy="No equity points yet" />
        )}
      </ChartCard>

      <div className="command-deck-ops__perf-charts">
        <ChartCard title="Daily P&L" height={132}>
          {view.dailyPnlChart.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={view.dailyPnlChart} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={chartTheme.axisTick} interval="preserveStartEnd" />
                <YAxis tick={chartTheme.axisTick} width={44} tickFormatter={(v: number) => `$${v}`} />
                <Tooltip
                  contentStyle={chartTheme.tooltip}
                  formatter={(value) => [`$${Number(value ?? 0).toFixed(0)}`, "Daily P&L"]}
                />
                <Bar dataKey="dailyPnl" radius={[3, 3, 0, 0]} isAnimationActive={animationActive}>
                  {view.dailyPnlChart.map((entry) => (
                    <Cell
                      key={entry.t}
                      fill={entry.dailyPnl >= 0 ? chartTheme.colors.positive : chartTheme.colors.negative}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <ChartEmpty copy="Daily history after runtime snapshots" />
          )}
        </ChartCard>

        <ChartCard title="Cumulative P&L" height={132}>
          {view.cumulativePnlChart.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={view.cumulativePnlChart}
                margin={{ top: 4, right: 4, left: 0, bottom: 0 }}
              >
                <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={chartTheme.axisTick} interval="preserveStartEnd" />
                <YAxis tick={chartTheme.axisTick} width={44} tickFormatter={(v: number) => `$${v}`} />
                <Tooltip
                  contentStyle={chartTheme.tooltip}
                  formatter={(value) => [`$${Number(value ?? 0).toFixed(0)}`, "Cumulative"]}
                />
                <Line
                  type="monotone"
                  dataKey="cumulativePnl"
                  stroke={chartTheme.colors.policyLoss}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={animationActive}
                  animationDuration={280}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <ChartEmpty
              copy={tradesError ? "Unable to load trade history" : "No closed trades yet"}
            />
          )}
        </ChartCard>
      </div>
    </div>
  );
}
