import {
  MODE_SIM_SECONDARY,
  STATUS_SUCCESS,
} from "@/lib/designTokens";
import type { TradingMode } from "@/store/coreStore";

export const CHART_GRID_STROKE = "rgba(255,255,255,0.06)";

export const CHART_AXIS_TICK = { fontSize: 9, fill: "#94a3b8" };

export const CHART_TOOLTIP_STYLE = {
  background: "rgba(0,0,0,0.85)",
  border: "1px solid rgba(255,255,255,0.1)",
  fontSize: 11,
  borderRadius: 6,
};

export const CHART_COLORS = {
  reward: "#22d3ee",
  policyLoss: MODE_SIM_SECONDARY,
  valueLoss: "#f472b6",
  entropy: "#818cf8",
  explainedVariance: STATUS_SUCCESS,
  sharpe: "#fbbf24",
  equity: "#22d3ee",
  positive: STATUS_SUCCESS,
  negative: "#f472b6",
} as const;

export const ANNEX_CHART_GRID_STROKE = "rgba(255,255,255,0.04)";

export const ANNEX_CHART_AXIS_TICK = { fontSize: 9, fill: "#64748b" };

export const ANNEX_CHART_TOOLTIP_STYLE = {
  background: "rgba(8,10,14,0.95)",
  border: "1px solid rgba(255,255,255,0.06)",
  fontSize: 11,
  borderRadius: 4,
};

export const ANNEX_CHART_COLORS = {
  reward: "#64748b",
  policyLoss: "#7c6f9b",
  valueLoss: "#8b7a8f",
  entropy: "#6b7280",
  explainedVariance: "#5f8a72",
  sharpe: "#9a8b5c",
  equity: "#64748b",
  positive: "#5f8a72",
  negative: "#9a7a6a",
} as const;

export type ChartTheme = {
  grid: string;
  axisTick: { fontSize: number; fill: string };
  tooltip: typeof CHART_TOOLTIP_STYLE;
  colors: typeof CHART_COLORS | typeof ANNEX_CHART_COLORS;
};

/** SIM: cyan/violet evolution charts; REAL: monochrome slate charts. */
export function chartThemeForMode(mode: TradingMode): ChartTheme {
  if (mode === "REAL") {
    return {
      grid: ANNEX_CHART_GRID_STROKE,
      axisTick: ANNEX_CHART_AXIS_TICK,
      tooltip: ANNEX_CHART_TOOLTIP_STYLE,
      colors: ANNEX_CHART_COLORS,
    };
  }
  return {
    grid: CHART_GRID_STROKE,
    axisTick: CHART_AXIS_TICK,
    tooltip: CHART_TOOLTIP_STYLE,
    colors: CHART_COLORS,
  };
}
