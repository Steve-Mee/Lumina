import type { CSSProperties } from "react";
import { useState } from "react";

import type { HudHeroPrimary } from "@/lib/hudSignalLayout";
import type { TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface HudOrganismCenterProps {
  mode: TradingMode;
  heroPrimary: HudHeroPrimary;
  readout: string;
  readoutLabel: string;
  vitality?: number;
  onActivate?: () => void;
  className?: string;
}

export function HudOrganismCenter({
  mode,
  heroPrimary,
  readout,
  readoutLabel,
  vitality = 0.75,
  onActivate,
  className,
}: HudOrganismCenterProps) {
  const [focused, setFocused] = useState(false);
  const fillBase = Math.min(1, Math.max(0.2, vitality * 0.75));
  const fillGain = Math.min(1, Math.max(0, vitality * 0.25));

  return (
    <button
      type="button"
      data-mode={mode}
      data-hero={heroPrimary}
      className={cn(
        "hud-organism-center group relative flex flex-col items-center justify-center gap-1 border-0 bg-transparent p-0",
        className,
      )}
      title={`${readoutLabel}: ${readout}`}
      aria-label={`${readoutLabel} ${readout}. Open performance annex for details.`}
      onClick={onActivate}
      onKeyDown={(event) => {
        if (onActivate && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onActivate();
        }
      }}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onMouseEnter={() => setFocused(true)}
      onMouseLeave={() => setFocused(false)}
    >
      <span
        className="hud-organism-center__pulse"
        aria-hidden
        style={
          {
            "--hud-pulse-fill": `calc(${fillBase} + ${fillGain} * var(--organism-envelope, 0.5))`,
          } as CSSProperties
        }
      >
        <span className="hud-organism-center__ring" />
        <span className="hud-organism-center__core" />
      </span>
      <span
        className={cn(
          "hud-organism-center__readout font-mono text-[10px] tracking-wide uppercase transition-opacity",
          focused ? "opacity-100" : "opacity-0 md:opacity-60",
        )}
      >
        <span className="text-muted-foreground">{readoutLabel}</span>{" "}
        <span className="text-foreground/90">{readout}</span>
      </span>
    </button>
  );
}
