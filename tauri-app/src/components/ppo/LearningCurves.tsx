import { useId } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  CHART_AXIS_TICK,
  CHART_COLORS,
  CHART_GRID_STROKE,
  CHART_TOOLTIP_STYLE,
} from "@/lib/ppoEvolutionChartTheme";
import { mapLogsToLearningCurvePoints } from "@/lib/ppoLearningCurvesModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

export interface LearningCurvesProps {
  logs: PPOEvolutionMetric[];
  compact?: boolean;
  className?: string;
}

interface CurveCardProps {
  title: string;
  dataKey: "meanReward" | "entropy";
  stroke: string;
  gradientId: string;
  data: ReturnType<typeof mapLogsToLearningCurvePoints>;
  height: number;
  formatValue: (value: number) => string;
}

function CurveCard({
  title,
  dataKey,
  stroke,
  gradientId,
  data,
  height,
  formatValue,
}: CurveCardProps) {
  const uid = useId();
  const resolvedGradientId = `${gradientId}${uid.replace(/:/g, "")}`;

  return (
    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
      <p className="mb-2 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
        {title}
      </p>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data}>
            <defs>
              <linearGradient id={resolvedGradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
                <stop offset="100%" stopColor={stroke} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={CHART_GRID_STROKE} vertical={false} />
            <XAxis dataKey="step" hide />
            <YAxis width={36} tick={CHART_AXIS_TICK} />
            <Tooltip
              contentStyle={CHART_TOOLTIP_STYLE}
              labelFormatter={(step) => `step ${Number(step).toLocaleString()}`}
              formatter={(value) => [
                formatValue(Number(value)),
                title,
              ]}
            />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke="none"
              fill={`url(#${resolvedGradientId})`}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={stroke}
              dot={false}
              strokeWidth={1.75}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function LearningCurves({ logs, compact = false, className }: LearningCurvesProps) {
  if (logs.length < 2) return null;

  const data = mapLogsToLearningCurvePoints(logs);
  const height = compact ? 96 : 128;

  return (
    <div className={cn("grid grid-cols-1 gap-3 md:grid-cols-2", className)}>
      <CurveCard
        title="Mean reward"
        dataKey="meanReward"
        stroke={CHART_COLORS.reward}
        gradientId="ppo-reward-gradient"
        data={data}
        height={height}
        formatValue={(value) => value.toFixed(4)}
      />
      <CurveCard
        title="Entropy"
        dataKey="entropy"
        stroke={CHART_COLORS.entropy}
        gradientId="ppo-entropy-gradient"
        data={data}
        height={height}
        formatValue={(value) => value.toFixed(4)}
      />
    </div>
  );
}
