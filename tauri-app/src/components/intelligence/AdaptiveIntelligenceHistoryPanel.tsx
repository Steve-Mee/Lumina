import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { filterAdaptiveHistoryEvents } from "@/lib/adaptiveIntelligenceTypes";
import { formatModeLabel, formatTierLabel } from "@/lib/intelligenceDisplay";
import { cn } from "@/lib/utils";

interface AdaptiveIntelligenceHistoryPanelProps {
  className?: string;
}

export function AdaptiveIntelligenceHistoryPanel({
  className,
}: AdaptiveIntelligenceHistoryPanelProps) {
  const { history } = useAdaptiveIntelligenceContext();
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () => filterAdaptiveHistoryEvents([...history].reverse(), query),
    [history, query],
  );

  return (
    <section className={cn("flex min-h-0 flex-col gap-2", className)}>
      <div className="relative">
        <Search className="pointer-events-none absolute top-2.5 left-2.5 size-3.5 text-muted-foreground" />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search tier, model, mode, reason…"
          className="w-full rounded-md border border-white/10 bg-black/35 py-2 pr-3 pl-8 font-mono text-xs text-foreground outline-none focus:border-cyan-400/40"
          aria-label="Search adaptive intelligence history"
        />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1 [scrollbar-width:thin]">
        {filtered.length === 0 ? (
          <p className="py-4 text-xs text-muted-foreground">No matching events.</p>
        ) : (
          <ul className="space-y-1.5">
            {filtered.map((event, index) => {
              const payload = event.payload ?? {};
              return (
                <li
                  key={`${event.timestamp ?? "row"}-${index}`}
                  className="rounded-md border border-white/8 bg-black/25 px-3 py-2"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[10px] text-cyan-200/90">
                      {payload.tier ? formatTierLabel(payload.tier as never) : "—"}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {payload.mode ? formatModeLabel(String(payload.mode)) : "—"}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-foreground">
                    {payload.recommended_model ?? "unknown"} ·{" "}
                    {payload.recommended_provider ?? "unknown provider"}
                  </p>
                  {payload.status_reason ? (
                    <p className="mt-1 text-[10px] text-amber-200/80">{payload.status_reason}</p>
                  ) : null}
                  <p className="mt-1 font-mono text-[9px] text-muted-foreground">
                    {event.timestamp ? new Date(event.timestamp).toLocaleString() : "Unknown time"}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
