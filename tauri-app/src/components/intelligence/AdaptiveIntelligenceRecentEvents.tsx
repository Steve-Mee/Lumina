import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { formatModeLabel, formatTierLabel } from "@/lib/intelligenceDisplay";
import { distressPanelClass, modeValueClass, utilityListItemClass } from "@/lib/modePresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";

interface AdaptiveIntelligenceRecentEventsProps {
  className?: string;
  maxRows?: number;
}

export function AdaptiveIntelligenceRecentEvents({
  className,
  maxRows = 8,
}: AdaptiveIntelligenceRecentEventsProps) {
  const { history } = useAdaptiveIntelligenceContext();
  const operatorMode = useCoreStore(selectCurrentMode);
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
                className={utilityListItemClass(operatorMode)}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("font-mono text-[10px]", modeValueClass(operatorMode))}>{tier}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">{mode}</span>
                  {payload.degraded_state ? (
                    <span className={cn("px-1.5 py-0.5 font-mono text-[9px] uppercase", distressPanelClass("warn"))}>
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
