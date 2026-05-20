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
  chartThemeForMode,
  type ChartTheme,
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
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";

const AmbitiousLab = lazy(() =>
  import("@/components/ppo/ambitious/AmbitiousLab").then((module) => ({
    default: module.AmbitiousLab,
  })),
);

function AmbitiousLabFallback() {
  return (
    <div className="analytics-annex__metric rounded-lg p-4 text-xs text-muted-foreground">
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
          ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-300 lumina-glow-edge"
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
    <div className="inline-flex rounded-md border p-0.5" style={{ borderColor: "var(--annex-border)", background: "var(--annex-surface)" }}>
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
                ? "bg-black/30 text-muted-foreground"
                : "text-muted-foreground/70 hover:bg-white/5 hover:text-muted-foreground",
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

function SupplementalLearningCharts({
  data,
  height,
  chartTheme,
}: {
  data: Record<string, number>[];
  height: number;
  chartTheme: ChartTheme;
}) {
  const charts: SupplementalChartProps[] = [
    {
      title: "Policy & value loss",
      data,
      height,
      lines: [
        { dataKey: "policyLoss", stroke: chartTheme.colors.policyLoss, name: "Policy" },
        { dataKey: "valueLoss", stroke: chartTheme.colors.valueLoss, name: "Value" },
      ],
    },
    {
      title: "Sharpe rolling 5k",
      data,
      height,
      lines: [{ dataKey: "sharpe", stroke: chartTheme.colors.sharpe }],
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {charts.map((chart) => (
        <div
          key={chart.title}
          className="analytics-annex__metric p-3"
        >
          <p className="analytics-annex__section-title mb-2">
            {chart.title}
          </p>
          <div style={{ height: chart.height }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart.data}>
                <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                <XAxis dataKey="step" hide />
                <YAxis width={36} tick={chartTheme.axisTick} />
                <Tooltip contentStyle={chartTheme.tooltip} />
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
  const operatorMode = useCoreStore(selectCurrentMode);
  const chartTheme = chartThemeForMode(operatorMode);
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
        color: chartTheme.colors.reward,
      },
      {
        label: "Entropy",
        displayValue: latest.entropy.toFixed(3),
        fillPercent: gaugePercent(normalizeEntropy(latest.entropy)),
        color: chartTheme.colors.entropy,
      },
      {
        label: "Explained Variance",
        displayValue: `${(latest.explained_variance * 100).toFixed(1)}%`,
        fillPercent: gaugePercent(normalizeExplainedVariance(latest.explained_variance)),
        color: chartTheme.colors.explainedVariance,
      },
      {
        label: "Winrate 5k",
        displayValue: `${(latest.winrate_rolling_5k * 100).toFixed(1)}%`,
        fillPercent: gaugePercent(normalizeWinrate(latest.winrate_rolling_5k)),
        color: chartTheme.colors.sharpe,
      },
    ];
  }, [latest, logs, chartTheme]);

  return (
    <section
      className={cn(
        "relative overflow-hidden p-2",
        isCompactView ? "space-y-3" : "space-y-4",
        className,
      )}
      aria-label={title}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3
            className={cn(
              "analytics-annex__section-title font-semibold",
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
            <SupplementalLearningCharts
              data={supplementalChartData}
              height={chartHeight}
              chartTheme={chartTheme}
            />
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
          <span className="analytics-annex__metric px-2 py-1 text-[11px]">
            Sharpe 5k: {latest.sharpe_rolling_5k.toFixed(2)}
          </span>
          <span className="analytics-annex__metric px-2 py-1 text-[11px]">
            Avg stop: {(latest.avg_stop_pct * 100).toFixed(2)}%
          </span>
          <span className="analytics-annex__metric px-2 py-1 text-[11px]">
            Avg target: {(latest.avg_target_pct * 100).toFixed(2)}%
          </span>
        </div>
      ) : null}
    </section>
  );
}
