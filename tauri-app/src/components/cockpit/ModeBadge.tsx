import { Badge } from "@/components/ui/badge";
import { realBadgeClass } from "@/lib/modePresentation";
import type { TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface ModeBadgeProps {
  mode: TradingMode;
  className?: string;
}

export function ModeBadge({ mode, className }: ModeBadgeProps) {
  const isReal = mode === "REAL";

  return (
    <Badge
      className={cn(
        "h-6 px-3 font-mono text-[11px] tracking-[0.2em] uppercase",
        isReal
          ? realBadgeClass()
          : "border-cyan-400/40 bg-cyan-400/10 text-cyan-300 lumina-glow-edge",
        className,
      )}
    >
      {mode}
    </Badge>
  );
}
