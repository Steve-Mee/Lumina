import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface DeckMetricTileProps {
  label: string;
  value: ReactNode;
  suffix?: string;
  className?: string;
}

export function DeckMetricTile({ label, value, suffix, className }: DeckMetricTileProps) {
  return (
    <div className={cn("deck-metric-tile", className)}>
      <p className="deck-metric-tile__label">{label}</p>
      <p className="deck-metric-tile__value">
        {value}
        {suffix ? (
          <span className="ml-0.5 text-[10px] text-muted-foreground">{suffix}</span>
        ) : null}
      </p>
    </div>
  );
}
