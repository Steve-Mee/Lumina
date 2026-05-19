import { cn } from "@/lib/utils";
import type { IntelligenceHealth } from "@/lib/intelligenceDisplay";
import { HEALTH_DOT } from "@/lib/intelligenceDisplay";

interface IntelligenceHealthDotProps {
  health: IntelligenceHealth;
  pulse?: boolean;
  className?: string;
}

export function IntelligenceHealthDot({
  health,
  pulse = false,
  className,
}: IntelligenceHealthDotProps) {
  const visual = HEALTH_DOT[health];
  return (
    <span
      className={cn("relative inline-flex size-2 shrink-0 rounded-full", className)}
      style={{ backgroundColor: visual.color, boxShadow: `0 0 8px ${visual.glow}` }}
      aria-label={visual.label}
      title={visual.label}
    >
      {pulse ? (
        <span
          className="absolute inset-0 animate-ping rounded-full opacity-60"
          style={{ backgroundColor: visual.color }}
          aria-hidden
        />
      ) : null}
    </span>
  );
}
