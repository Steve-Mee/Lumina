import { Suspense, lazy, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ActionDistributionChart } from "@/components/ppo/ActionDistributionChart";
import { EvolutionTimeline } from "@/components/ppo/EvolutionTimeline";
import { Gauge } from "@/components/ppo/Gauge";
import { LearningCurves } from "@/components/ppo/LearningCurves";
import { PolicyHealthPanel } from "@/components/ppo/PolicyHealthPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CHART_AXIS_TICK,
  CHART_COLORS,
  CHART_GRID_STROKE,
  CHART_TOOLTIP_STYLE,
} from "@/lib/ppoEvolutionChartTheme";
import {
  gaugePercent,
  normalizeEntropy,
  normalizeExplainedVariance,
  normalizeMeanReward,
  normalizeWinrate,
} from "@/lib/ppoEvolutionMetrics";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

const AmbitiousLab = lazy(() =>
  import("@/components/ppo/ambitious/AmbitiousLab").then((module) => ({
    default: module.AmbitiousLab,
  })),
);

function AmbitiousLabFallback() {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-4 text-xs text-muted-foreground">
      Loading ambitious lab…
    </div>
  );
}

export interface PPOEvolutionDashboardProps {
  logs: PPOEvolutionMetric[];
  connected: boolean;
  title?: string;
  compact?: boolean;
  showAdvancedFeatures?: boolean;
  className?: string;
}

type DashboardViewMode = "compact" | "advanced";

interface SupplementalChartProps {
  title: string;
  data: Record<string, number>[];
  lines: Array<{ dataKey: string; stroke: string; name?: string }>;
  height: number;
}

function ConnectionBadge({ connected }: { connected: boolean }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "font-mono text-[10px] tracking-wider uppercase",
        connected
          ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-300 shadow-[0_0_12px_rgba(52,211,153,0.25)]"
          : "border-red-500/40 bg-red-950/30 text-red-300",
      )}
    >
      <span
        className={cn(
          "mr-1.5 inline-block size-1.5 rounded-full",
          connected ? "bg-emerald-400" : "bg-red-400",
        )}
        aria-hidden
      />
      {connected ? "Live" : "Offline"}
    </Badge>
  );
}

function ViewModeToggle({
  viewMode,
  onChange,
  disabled,
}: {
  viewMode: DashboardViewMode;
  onChange: (mode: DashboardViewMode) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex rounded-md border border-white/10 bg-black/30 p-0.5">
      {(["compact", "advanced"] as const).map((mode) => {
        const active = viewMode === mode;
        return (
          <Button
            key={mode}
            type="button"
            size="sm"
            variant="ghost"
            disabled={disabled}
            className={cn(
              "h-7 px-2.5 font-mono text-[10px] tracking-wide uppercase",
              active
                ? "bg-cyan-500/15 text-cyan-200 shadow-[0_0_12px_rgba(34,211,238,0.15)]"
                : "text-muted-foreground hover:bg-white/5 hover:text-cyan-100/80",
            )}
            onClick={() => onChange(mode)}
          >
            {mode}
          </Button>
        );
      })}
    </div>
  );
}

function SupplementalLearningCharts({ data, height }: { data: Record<string, number>[]; height: number }) {
  const charts: SupplementalChartProps[] = [
    {
      title: "Policy & value loss",
      data,
      height,
      lines: [
        { dataKey: "policyLoss", stroke: CHART_COLORS.policyLoss, name: "Policy" },
        { dataKey: "valueLoss", stroke: CHART_COLORS.valueLoss, name: "Value" },
      ],
    },
    {
      title: "Sharpe rolling 5k",
      data,
      height,
      lines: [{ dataKey: "sharpe", stroke: CHART_COLORS.sharpe }],
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {charts.map((chart) => (
        <div
          key={chart.title}
          className="rounded-lg border border-white/10 bg-black/20 p-3"
        >
          <p className="mb-2 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
            {chart.title}
          </p>
          <div style={{ height: chart.height }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart.data}>
                <CartesianGrid stroke={CHART_GRID_STROKE} vertical={false} />
                <XAxis dataKey="step" hide />
                <YAxis width={36} tick={CHART_AXIS_TICK} />
                <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
                {chart.lines.map((line) => (
                  <Line
                    key={line.dataKey}
                    type="monotone"
                    dataKey={line.dataKey}
                    name={line.name ?? line.dataKey}
                    stroke={line.stroke}
                    dot={false}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ))}
    </div>
  );
}

export function PPOEvolutionDashboard({
  logs,
  connected,
  title = "PPO Evolution Dashboard",
  compact = false,
  showAdvancedFeatures = false,
  className,
}: PPOEvolutionDashboardProps) {
  const [viewMode, setViewMode] = useState<DashboardViewMode>(compact ? "compact" : "advanced");
  const isAdvanced = !compact && viewMode === "advanced";
  const isCompactView = !isAdvanced;

  const latest = useMemo(
    () => (logs.length > 0 ? logs[logs.length - 1]! : null),
    [logs],
  );

  const supplementalChartData = useMemo(
    () =>
      logs.map((metric) => ({
        step: metric.step,
        policyLoss: metric.policy_loss,
        valueLoss: metric.value_loss,
        sharpe: metric.sharpe_rolling_5k,
      })),
    [logs],
  );

  const chartHeight = isCompactView ? 96 : 128;
  const hasChartData = logs.length >= 2;

  const gauges = useMemo(() => {
    if (!latest) return [];
    return [
      {
        label: "Mean Reward",
        displayValue: latest.mean_reward.toFixed(3),
        fillPercent: gaugePercent(normalizeMeanReward(latest.mean_reward, logs)),
        color: CHART_COLORS.reward,
      },
      {
        label: "Entropy",
        displayValue: latest.entropy.toFixed(3),
        fillPercent: gaugePercent(normalizeEntropy(latest.entropy)),
        color: CHART_COLORS.entropy,
      },
      {
        label: "Explained Variance",
        displayValue: `${(latest.explained_variance * 100).toFixed(1)}%`,
        fillPercent: gaugePercent(normalizeExplainedVariance(latest.explained_variance)),
        color: CHART_COLORS.explainedVariance,
      },
      {
        label: "Winrate 5k",
        displayValue: `${(latest.winrate_rolling_5k * 100).toFixed(1)}%`,
        fillPercent: gaugePercent(normalizeWinrate(latest.winrate_rolling_5k)),
        color: CHART_COLORS.sharpe,
      },
    ];
  }, [latest, logs]);

  return (
    <section
      className={cn(
        "cockpit-panel relative overflow-hidden rounded-lg border border-white/10 bg-black/25 p-4 backdrop-blur-sm",
        isCompactView ? "space-y-3" : "space-y-4",
        className,
      )}
      aria-label={title}
    >
      <div
        className="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-cyan-400/60 to-violet-400/30"
        aria-hidden
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3
            className={cn(
              "font-semibold tracking-[0.18em] text-cyan-200/90 uppercase",
              isCompactView ? "text-[10px]" : "text-xs",
            )}
          >
            {title}
          </h3>
          <ConnectionBadge connected={connected} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {latest ? (
            <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
              step {latest.step.toLocaleString()}
            </span>
          ) : null}
          <ViewModeToggle
            viewMode={viewMode}
            onChange={setViewMode}
            disabled={compact}
          />
        </div>
      </div>

      {latest ? (
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {gauges.map((gauge) => (
            <Gauge
              key={gauge.label}
              label={gauge.label}
              displayValue={gauge.displayValue}
              fillPercent={gauge.fillPercent}
              color={gauge.color}
              compact={isCompactView}
            />
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          {connected
            ? "Waiting for PPO training metrics…"
            : "Connecting to PPO evolution stream…"}
        </p>
      )}

      {hasChartData ? (
        <div className="space-y-3">
          <LearningCurves logs={logs} compact={isCompactView} />

          {isAdvanced && latest ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <PolicyHealthPanel metric={latest} />
              <ActionDistributionChart distribution={latest.action_distribution} />
            </div>
          ) : null}

          {isAdvanced ? (
            <SupplementalLearningCharts data={supplementalChartData} height={chartHeight} />
          ) : null}

          {isAdvanced && logs.length > 0 ? (
            <EvolutionTimeline logs={logs} maxSteps={50} orientation="vertical" />
          ) : null}

          {isAdvanced && showAdvancedFeatures && logs.length >= 2 ? (
            <Suspense fallback={<AmbitiousLabFallback />}>
              <AmbitiousLab logs={logs} />
            </Suspense>
          ) : null}
        </div>
      ) : null}

      {showAdvancedFeatures && isAdvanced && latest ? (
        <div className="flex flex-wrap gap-2 text-[11px]">
          <span className="rounded-md border border-white/10 bg-white/5 px-2 py-1">
            Sharpe 5k: {latest.sharpe_rolling_5k.toFixed(2)}
          </span>
          <span className="rounded-md border border-white/10 bg-white/5 px-2 py-1">
            Avg stop: {(latest.avg_stop_pct * 100).toFixed(2)}%
          </span>
          <span className="rounded-md border border-white/10 bg-white/5 px-2 py-1">
            Avg target: {(latest.avg_target_pct * 100).toFixed(2)}%
          </span>
        </div>
      ) : null}
    </section>
  );
}
