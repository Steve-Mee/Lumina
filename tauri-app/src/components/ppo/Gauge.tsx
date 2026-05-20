import { motion } from "framer-motion";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";

const VIEWBOX_WIDTH = 100;
const VIEWBOX_HEIGHT = 58;
const ARC_RADIUS = 40;
const ARC_CENTER_X = 50;
const ARC_CENTER_Y = 50;
const STROKE_WIDTH = 6;

/** Semicircle arc from 180° to 0° (left to right, bow upward). */
const ARC_PATH = `M ${ARC_CENTER_X - ARC_RADIUS} ${ARC_CENTER_Y} A ${ARC_RADIUS} ${ARC_RADIUS} 0 0 1 ${ARC_CENTER_X + ARC_RADIUS} ${ARC_CENTER_Y}`;

/** Approximate half-circumference for dash animation. */
const ARC_LENGTH = Math.PI * ARC_RADIUS;

export interface GaugeProps {
  label: string;
  displayValue: string;
  fillPercent: number;
  color: string;
  compact?: boolean;
  className?: string;
}

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

export function Gauge({
  label,
  displayValue,
  fillPercent,
  color,
  compact = false,
  className,
}: GaugeProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const percent = clampPercent(fillPercent);
  const dashOffset = ARC_LENGTH * (1 - percent / 100);

  const glowFilter = `drop-shadow(0 0 4px ${color}) drop-shadow(0 0 10px ${color}88)`;

  return (
    <div
      className={cn(
        "relative overflow-hidden lumina-surface-muted rounded-lg p-3",
        compact ? "min-h-[108px]" : "min-h-[128px]",
        className,
      )}
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/30 to-violet-400/20"
        aria-hidden
      />
      <p className="mb-1 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
        {label}
      </p>
      <div className={cn("relative", compact ? "h-[52px]" : "h-[64px]")}>
        <svg
          viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
          className="h-full w-full overflow-visible"
          aria-hidden
        >
          <path
            d={ARC_PATH}
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
          />

          <motion.path
            d={ARC_PATH}
            fill="none"
            stroke={color}
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
            pathLength={ARC_LENGTH}
            strokeDasharray={ARC_LENGTH}
            initial={false}
            animate={{ strokeDashoffset: dashOffset }}
            transition={transitionOrNone(reducedMotion, modeMotion)}
            style={{
              filter: glowFilter,
            }}
            className={cn(!reducedMotion && "ppo-gauge-arc-pulse")}
          />
        </svg>
        <div className="absolute inset-x-0 bottom-0 text-center">
          <motion.p
            key={displayValue}
            className="font-mono text-sm font-semibold tabular-nums text-cyan-100/95"
            initial={reducedMotion ? false : { opacity: 0.7, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={transitionOrNone(reducedMotion, modeMotion)}
          >
            {displayValue}
          </motion.p>
        </div>
      </div>
    </div>
  );
}
