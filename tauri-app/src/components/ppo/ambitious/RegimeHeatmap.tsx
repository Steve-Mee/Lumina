import { motion } from "framer-motion";
import type { CSSProperties } from "react";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { fadeUp, transitionOrNone } from "@/lib/motionPresets";
import { buildRegimeHeatmap, type RegimeHeatmapCell } from "@/lib/ppoRegimeHeatmapModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

export interface RegimeHeatmapProps {
  logs: PPOEvolutionMetric[];
  className?: string;
}

function heatmapStyle(cell: RegimeHeatmapCell): CSSProperties {
  const alpha = 0.15 + cell.intensity * 0.55;
  return {
    background: `linear-gradient(135deg, rgba(34,211,238,${alpha}) 0%, rgba(167,139,250,${alpha * 0.7}) 100%)`,
  };
}

function RegimeCell({
  cell,
  index,
  reducedMotion,
}: {
  cell: RegimeHeatmapCell;
  index: number;
  reducedMotion: boolean;
}) {
  return (
    <motion.div
      className={cn(
        "rounded-lg border border-white/10 p-3 transition-colors hover:border-cyan-400/30",
        cell.sampleCount === 0 && "opacity-50",
      )}
      style={heatmapStyle(cell)}
      title={`${cell.displayName}: ${cell.avgReward.toFixed(3)} avg reward (${cell.sampleCount} samples)`}
      variants={fadeUp}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
      transition={transitionOrNone(reducedMotion, {
        duration: 0.3,
        delay: reducedMotion ? 0 : index * 0.05,
      })}
    >
      <p className="text-[10px] tracking-[0.14em] text-cyan-50/90 uppercase">{cell.displayName}</p>
      <p className="mt-2 font-mono text-lg font-semibold tabular-nums text-white/95">
        {cell.sampleCount > 0 ? cell.avgReward.toFixed(3) : "—"}
      </p>
      <p className="mt-1 text-[10px] text-white/70">{cell.sampleCount} samples</p>
    </motion.div>
  );
}

export function RegimeHeatmap({ logs, className }: RegimeHeatmapProps) {
  const reducedMotion = usePrefersReducedMotion();
  const cells = buildRegimeHeatmap(logs);

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-lg border border-white/10 bg-black/20 p-4",
        className,
      )}
      aria-label="Regime heatmap"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/30 to-violet-400/20"
        aria-hidden
      />
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
          Regime Heatmap
        </p>
        <div className="flex items-center gap-2 text-[9px] text-muted-foreground uppercase">
          <span>Low</span>
          <div className="h-1.5 w-16 rounded-full bg-gradient-to-r from-white/10 via-cyan-400/50 to-violet-400/70" />
          <span>High</span>
        </div>
      </div>

      {logs.length === 0 ? (
        <p className="text-xs text-muted-foreground">Waiting for regime samples…</p>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          {cells.map((cell, index) => (
            <RegimeCell
              key={cell.regime}
              cell={cell}
              index={index}
              reducedMotion={reducedMotion}
            />
          ))}
        </div>
      )}
    </section>
  );
}
