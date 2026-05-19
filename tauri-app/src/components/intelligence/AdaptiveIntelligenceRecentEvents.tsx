import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { formatModeLabel, formatTierLabel } from "@/lib/intelligenceDisplay";
import { cn } from "@/lib/utils";

interface AdaptiveIntelligenceRecentEventsProps {
  className?: string;
  maxRows?: number;
}

export function AdaptiveIntelligenceRecentEvents({
  className,
  maxRows = 8,
}: AdaptiveIntelligenceRecentEventsProps) {
  const { history } = useAdaptiveIntelligenceContext();
  const recent = [...history].reverse().slice(0, maxRows);

  return (
    <section className={cn("space-y-2", className)}>
      <h4 className="font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase">
        Recent events
      </h4>
      {recent.length === 0 ? (
        <p className="text-xs text-muted-foreground">No intelligence events recorded yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {recent.map((event, index) => {
            const payload = event.payload ?? {};
            const tier = payload.tier ? formatTierLabel(payload.tier as never) : "—";
            const mode = payload.mode ? formatModeLabel(String(payload.mode)) : "—";
            const ts = event.timestamp
              ? new Date(event.timestamp).toLocaleString()
              : "Unknown time";
            return (
              <li
                key={`${event.timestamp ?? index}-${index}`}
                className="rounded-md border border-white/8 bg-black/25 px-3 py-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[10px] text-cyan-200/90">{tier}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{mode}</span>
                  {payload.degraded_state ? (
                    <span className="rounded border border-amber-500/30 px-1.5 py-0.5 font-mono text-[9px] text-amber-200/90 uppercase">
                      Degraded
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 truncate text-[11px] text-muted-foreground">
                  {payload.recommended_model ?? "unknown model"}
                </p>
                <p className="font-mono text-[9px] text-muted-foreground/80">{ts}</p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
