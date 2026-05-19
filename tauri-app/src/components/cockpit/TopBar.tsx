import { useEffect, useState } from "react";

import { ModeBadge } from "@/components/cockpit/ModeBadge";
import type { TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface TopBarProps {
  mode: TradingMode;
  className?: string;
}

function formatClock(date: Date): string {
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function TopBar({ mode, className }: TopBarProps) {
  const [clock, setClock] = useState(() => formatClock(new Date()));

  useEffect(() => {
    const timer = window.setInterval(() => {
      setClock(formatClock(new Date()));
    }, 1000);

    return () => window.clearInterval(timer);
  }, []);

  return (
    <header
      className={cn(
        "relative z-10 flex h-14 shrink-0 items-center justify-between border-b border-white/10 bg-black/20 px-5 backdrop-blur-md",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <div className="size-2 rounded-full bg-cyan-400 shadow-[0_0_10px_var(--cockpit-glow-primary)]" />
        <div>
          <p className="text-sm font-medium tracking-wide text-foreground">
            LUMINA Neural Command Deck
          </p>
          <p className="font-mono text-[10px] tracking-[0.22em] text-muted-foreground uppercase">
            The Core
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <ModeBadge mode={mode} />
        <time
          className="font-mono text-xs tabular-nums text-cyan-200/80"
          dateTime={clock}
        >
          {clock}
        </time>
      </div>
    </header>
  );
}
