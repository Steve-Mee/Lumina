import { PolicyComparison } from "@/components/ppo/ambitious/PolicyComparison";
import { RegimeHeatmap } from "@/components/ppo/ambitious/RegimeHeatmap";
import { WhatIfSimulator } from "@/components/ppo/ambitious/WhatIfSimulator";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

export interface AmbitiousLabProps {
  logs: PPOEvolutionMetric[];
  className?: string;
}

export function AmbitiousLab({ logs, className }: AmbitiousLabProps) {
  return (
    <section className={cn("space-y-3", className)} aria-label="Ambitious Lab">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] tracking-[0.18em] text-violet-200/90 uppercase">
          Ambitious Lab
        </p>
        <span className="rounded-full border border-violet-500/30 bg-violet-950/30 px-2 py-0.5 font-mono text-[9px] tracking-wide text-violet-200 uppercase">
          Experimental
        </span>
      </div>

      <PolicyComparison logs={logs} />
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <RegimeHeatmap logs={logs} />
        <WhatIfSimulator logs={logs} />
      </div>
    </section>
  );
}
