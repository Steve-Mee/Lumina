import { Badge } from "@/components/ui/badge";
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
          ? "border-amber-500/40 bg-amber-500/10 text-amber-300 shadow-[0_0_16px_oklch(0.7_0.18_45/25%)]"
          : "border-cyan-400/40 bg-cyan-400/10 text-cyan-300 shadow-[0_0_16px_oklch(0.75_0.15_195/25%)]",
        className,
      )}
    >
      {mode}
    </Badge>
  );
}
