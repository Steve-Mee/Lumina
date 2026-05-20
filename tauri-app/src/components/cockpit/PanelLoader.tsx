import { cn } from "@/lib/utils";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

interface PanelLoaderProps {
  label?: string;
  className?: string;
  rows?: number;
}

export function PanelLoader({
  label = "Loading…",
  className,
  rows = 3,
}: PanelLoaderProps) {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <div
      className={cn(
        "flex h-full min-h-[120px] flex-col items-center justify-center gap-3 p-4",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div className="w-full max-w-[200px] space-y-2">
        {Array.from({ length: rows }, (_, index) => (
          <div
            key={index}
            className={cn(
              "h-2 overflow-hidden rounded-full bg-white/5",
              index === 0 && "w-full",
              index === 1 && "w-4/5",
              index === 2 && "w-3/5",
            )}
          >
            <div
              className={cn(
                "h-full rounded-full panel-loader__bar",
                !reducedMotion && "cockpit-shimmer",
              )}
              style={{ width: `${100 - index * 12}%` }}
            />
          </div>
        ))}
      </div>
      <p className="font-mono text-[10px] tracking-wide text-muted-foreground/70">
        {label}
      </p>
    </div>
  );
}
