import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import {
  dominantActionSegment,
  mapActionDistributionToChartData,
  type ActionDistributionSegment,
} from "@/lib/ppoActionDistributionModel";
import { CHART_TOOLTIP_STYLE } from "@/lib/ppoEvolutionChartTheme";
import type { PPOActionDistribution } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

export interface ActionDistributionChartProps {
  distribution: PPOActionDistribution | null;
  compact?: boolean;
  variant?: "donut" | "bar";
  className?: string;
}

function DistributionLegend({ segments }: { segments: ActionDistributionSegment[] }) {
  return (
    <div className="flex justify-between gap-2 text-[10px] text-muted-foreground">
      {segments.map((segment) => (
        <span key={segment.key} className="inline-flex items-center gap-1.5">
          <span
            className="inline-block size-2 rounded-full"
            style={{ backgroundColor: segment.fill, boxShadow: `0 0 6px ${segment.fill}88` }}
            aria-hidden
          />
          {segment.name.charAt(0)} {segment.percent}%
        </span>
      ))}
    </div>
  );
}

function ActionDistributionBarView({
  segments,
  compact,
}: {
  segments: ActionDistributionSegment[];
  compact?: boolean;
}) {
  return (
    <div className={cn("space-y-2", compact ? "pt-1" : "pt-2")}>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-white/10">
        {segments.map((segment) => (
          <div
            key={segment.key}
            style={{
              width: `${segment.value * 100}%`,
              backgroundColor: segment.fill,
              boxShadow: `0 0 8px ${segment.fill}66`,
            }}
            title={`${segment.name} ${segment.percent}%`}
          />
        ))}
      </div>
      <DistributionLegend segments={segments} />
    </div>
  );
}

function ActionDistributionDonutView({
  segments,
  compact,
}: {
  segments: ActionDistributionSegment[];
  compact?: boolean;
}) {
  const dominant = dominantActionSegment(segments);
  const chartHeight = compact ? 140 : 180;

  return (
    <div className="relative">
      <div style={{ height: chartHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={segments}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius="58%"
              outerRadius="82%"
              paddingAngle={2}
              stroke="rgba(0,0,0,0.35)"
              strokeWidth={1}
              isAnimationActive={false}
            >
              {segments.map((segment) => (
                <Cell key={segment.key} fill={segment.fill} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={CHART_TOOLTIP_STYLE}
              formatter={(value, name) => [`${Math.round(Number(value) * 100)}%`, String(name)]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <p className="text-[10px] tracking-[0.16em] text-muted-foreground uppercase">
          {dominant.name}
        </p>
        <p className="font-mono text-lg font-semibold tabular-nums text-cyan-100/95">
          {dominant.percent}%
        </p>
      </div>
      <div className="mt-2">
        <DistributionLegend segments={segments} />
      </div>
    </div>
  );
}

export function ActionDistributionChart({
  distribution,
  compact = false,
  variant = "donut",
  className,
}: ActionDistributionChartProps) {
  const segments = distribution ? mapActionDistributionToChartData(distribution) : [];

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-lg border border-white/10 bg-black/20 p-3",
        className,
      )}
      aria-label="Action distribution"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/30 to-violet-400/20"
        aria-hidden
      />
      <p className="mb-3 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
        Action Distribution
      </p>

      {!distribution ? (
        <p className="text-xs text-muted-foreground">Waiting for action mix…</p>
      ) : variant === "bar" ? (
        <ActionDistributionBarView segments={segments} compact={compact} />
      ) : (
        <ActionDistributionDonutView segments={segments} compact={compact} />
      )}
    </section>
  );
}
