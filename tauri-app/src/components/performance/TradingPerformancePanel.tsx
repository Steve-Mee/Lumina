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
import { TrendingUp } from "lucide-react";

import { AnimatedMetric } from "@/components/cockpit/AnimatedMetric";
import { Badge } from "@/components/ui/badge";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { useTradingPerformance } from "@/hooks/useTradingPerformance";
import {
  chartThemeForMode,
} from "@/lib/ppoEvolutionChartTheme";
import {
  formatMaxDrawdownPct,
  formatProfitFactor,
  formatSharpe,
  formatUsd,
  formatWinrate,
  kpiToneClass,
  pnlToneClass,
} from "@/lib/tradingPerformanceModel";
import { selectCurrentMode, selectFortress, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface TradingPerformancePanelProps {
  className?: string;
}

function ConnectionBadge({ connected, source }: { connected: boolean; source: string }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "font-mono text-[10px] tracking-wider uppercase",
        connected
          ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-300 lumina-glow-edge"
          : "border-red-500/40 bg-red-950/30 text-red-300",
      )}
    >
      <span
        className={cn(
          "mr-1.5 inline-block size-1.5 rounded-full",
          connected ? "bg-emerald-400 animate-pulse" : "bg-red-400",
        )}
        aria-hidden
      />
      {connected ? `Live · ${source}` : "Offline"}
    </Badge>
  );
}

function KpiTile({
  label,
  value,
  toneClass,
}: {
  label: string;
  value: string;
  toneClass?: string;
}) {
  return (
    <div className="analytics-annex__metric">
      <p className="font-mono text-[9px] tracking-[0.14em] text-muted-foreground uppercase">
        {label}
      </p>
      <AnimatedMetric value={value} className={cn("analytics-annex__metric-value text-sm", toneClass)} />
    </div>
  );
}

function PnlStripTile({
  label,
  value,
  amount,
}: {
  label: string;
  value: string;
  amount: number | null;
}) {
  return (
    <div className="analytics-annex__metric px-4 py-3">
      <p className="font-mono text-[9px] tracking-[0.16em] text-muted-foreground uppercase">
        {label}
      </p>
      <AnimatedMetric
        value={value}
        className={cn("text-lg font-medium", pnlToneClass(amount))}
      />
    </div>
  );
}

function ChartShell({
  title,
  children,
  height = 160,
}: {
  title: string;
  children: ReactNode;
  height?: number;
}) {
  return (
    <section className="analytics-annex__metric p-3">
      <div className="mb-2 flex items-center gap-2">
        <TrendingUp className="size-3.5 text-muted-foreground/70" />
        <h4 className="analytics-annex__section-title">
          {title}
        </h4>
      </div>
      <div style={{ height }}>{children}</div>
    </section>
  );
}

export function TradingPerformancePanel({ className }: TradingPerformancePanelProps) {
  const [pnlExpanded, setPnlExpanded] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const mode = useCoreStore(selectCurrentMode);
  const chartTheme = chartThemeForMode(mode);
  const equityStroke = chartTheme.colors.equity;
  const equityFill = "url(#equityGradient)";
  const { view, connected, tradesError } = useTradingPerformance();
  const fortress = useCoreStore(selectFortress);
  const drawdownKillPct = fortress?.drawdown_kill_pct ?? 8;

  const animationActive = !reducedMotion;
  const equityData = view.equityChart.map((point) => ({
    t: point.t,
    equity: point.equity,
  }));

  return (
    <div
      className={cn(
        "deck-annex-inset flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto [scrollbar-width:thin]",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <ConnectionBadge connected={connected} source={view.source} />
      </div>

      {!view.hasLiveData ? (
        <p className="analytics-annex__metric px-3 py-2 text-xs text-muted-foreground">
          Awaiting live session data. KPIs will populate from the last run summary when the engine
          is offline.
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <KpiTile label="Winrate" value={formatWinrate(view.kpis.winrate)} />
        <KpiTile
          label="Sharpe (ann.)"
          value={formatSharpe(view.kpis.sharpeAnnualized)}
          toneClass={kpiToneClass("sharpe", view.kpis.sharpeAnnualized)}
        />
        <KpiTile
          label="Max DD"
          value={formatMaxDrawdownPct(view.kpis.maxDrawdownPct)}
          toneClass={kpiToneClass("drawdown", view.kpis.maxDrawdownPct, drawdownKillPct)}
        />
        <KpiTile label="Profit Factor" value={formatProfitFactor(view.kpis.profitFactor)} />
      </div>

      <button
        type="button"
        className="rounded-md border border-white/10 px-3 py-2 text-left font-mono text-[10px] tracking-wide text-muted-foreground uppercase transition-colors hover:border-white/20 hover:text-foreground"
        onClick={() => setPnlExpanded((open) => !open)}
      >
        {pnlExpanded ? "Hide session P&L" : "Show session P&L"}
      </button>
      {pnlExpanded ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <PnlStripTile
            label="Daily P&L"
            value={formatUsd(view.dailyPnl)}
            amount={view.dailyPnl}
          />
          <PnlStripTile
            label="Open P&L"
            value={formatUsd(view.openPnl)}
            amount={view.openPnl}
          />
          <PnlStripTile
            label="Session Realized"
            value={formatUsd(view.sessionRealizedPnl)}
            amount={view.sessionRealizedPnl}
          />
        </div>
      ) : null}

      <ChartShell title="Live Equity Curve" height={200}>
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
                fill={equityFill}
                dot={false}
                activeDot={{ r: 4, fill: equityStroke, stroke: "#fff", strokeWidth: 1 }}
                isAnimationActive={animationActive}
                animationDuration={280}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="flex h-full items-center justify-center text-xs text-muted-foreground">
            No equity points yet
          </p>
        )}
      </ChartShell>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <ChartShell title="Daily P&L History" height={150}>
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
            <p className="flex h-full items-center justify-center text-xs text-muted-foreground">
              Daily history populates after runtime snapshots
            </p>
          )}
        </ChartShell>

        <ChartShell title="Cumulative P&L (Trades)" height={150}>
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
            <p className="flex h-full items-center justify-center text-xs text-muted-foreground">
              {tradesError ? "Unable to load trade history" : "No closed trades yet"}
            </p>
          )}
        </ChartShell>
      </div>
    </div>
  );
}
