import type { CSSProperties } from "react";

import type { IntegrityTier } from "@/lib/riskCitadelMetrics";
import type { WallMetric } from "@/lib/riskCitadelMetrics";
import type { TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface CitadelEnergyFieldProps {
  aggregate: number;
  tier: IntegrityTier;
  walls: WallMetric[];
  mode: TradingMode;
  lockdown: boolean;
  calmMode: boolean;
  reducedMotion: boolean;
}

const CONDUIT_TARGETS: Record<string, { x: number; y: number }> = {
  risk: { x: 50, y: 12 },
  kelly: { x: 12, y: 50 },
  regime: { x: 88, y: 50 },
  drawdown: { x: 50, y: 88 },
};

export function CitadelEnergyField({
  aggregate,
  tier,
  walls,
  mode,
  lockdown,
  calmMode,
  reducedMotion,
}: CitadelEnergyFieldProps) {
  const opacity = 0.25 + (aggregate / 100) * 0.45;
  const breathClass = calmMode
    ? "citadel-energy-field--calm"
    : "citadel-energy-field--sim";

  return (
    <div
      className={cn(
        "citadel-energy-field pointer-events-none absolute inset-0",
        breathClass,
        lockdown && "citadel-lockdown",
        reducedMotion && "citadel-energy-field--static",
      )}
      aria-hidden
      style={{ "--citadel-field-opacity": opacity } as CSSProperties}
    >
      <div
        className={cn(
          "citadel-energy-field__dome",
          mode === "REAL" ? "citadel-energy-field__dome--real" : "citadel-energy-field__dome--sim",
          tier === "red" && "citadel-energy-field__dome--critical",
        )}
      />

      <svg
        className="citadel-energy-field__svg"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid meet"
      >
        <circle
          cx="50"
          cy="50"
          r="38"
          fill="none"
          stroke="color-mix(in srgb, var(--lumina-cyan) 8%, transparent)"
          strokeWidth="0.6"
        />
        <circle
          cx="50"
          cy="50"
          r="38"
          fill="none"
          className="citadel-energy-field__ring"
          stroke={
            tier === "green"
              ? "color-mix(in srgb, #34d399 55%, var(--lumina-cyan))"
              : tier === "orange"
                ? "color-mix(in srgb, #fbbf24 55%, var(--lumina-cyan))"
                : "color-mix(in srgb, #ef4444 55%, var(--lumina-cyan))"
          }
          strokeWidth="1.2"
          strokeDasharray={`${(aggregate / 100) * 238} 238`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
        {walls.map((wall) => {
          const target = CONDUIT_TARGETS[wall.id];
          if (!target) {
            return null;
          }
          return (
            <line
              key={wall.id}
              x1={target.x}
              y1={target.y}
              x2="50"
              y2="50"
              className="citadel-energy-field__conduit"
              stroke="var(--lumina-cyan)"
              strokeWidth="0.5"
              strokeOpacity={0.15 + (wall.integrity / 100) * 0.55}
            />
          );
        })}
      </svg>
    </div>
  );
}
