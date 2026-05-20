import { motion } from "framer-motion";
import { useMemo, useState } from "react";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone } from "@/lib/motionPresets";
import { predictWhatIf } from "@/lib/ppoWhatIfModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

export interface WhatIfSimulatorProps {
  logs: PPOEvolutionMetric[];
  className?: string;
}

function SliderControl({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
          {label}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-cyan-200/90">{value}</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/10 accent-cyan-400"
      />
    </label>
  );
}

function PredictionCard({
  label,
  value,
  reducedMotion,
  modeMotion,
}: {
  label: string;
  value: string;
  reducedMotion: boolean;
  modeMotion: ReturnType<typeof useModeMotion>;
}) {
  return (
    <div className="lumina-surface-muted rounded-lg p-3">
      <p className="text-[10px] tracking-[0.14em] text-muted-foreground uppercase">{label}</p>
      <motion.p
        key={value}
        className="mt-1 font-mono text-lg font-semibold tabular-nums text-cyan-100/95"
        initial={reducedMotion ? false : { opacity: 0.7, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={transitionOrNone(reducedMotion, modeMotion)}
      >
        {value}
      </motion.p>
    </div>
  );
}

export function WhatIfSimulator({ logs, className }: WhatIfSimulatorProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const latest = logs.length > 0 ? logs[logs.length - 1]! : null;
  const [entropyLevel, setEntropyLevel] = useState(50);
  const [riskAversion, setRiskAversion] = useState(50);

  const prediction = useMemo(() => {
    if (!latest) return null;
    return predictWhatIf(latest, { entropyLevel, riskAversion });
  }, [latest, entropyLevel, riskAversion]);

  return (
    <section
      className={cn(
        "relative overflow-hidden lumina-surface-muted rounded-lg p-4",
        className,
      )}
      aria-label="What-if simulator"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/30 to-violet-400/20"
        aria-hidden
      />
      <p className="mb-1 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
        What-If Simulator
      </p>
      {latest ? (
        <p className="mb-4 text-[11px] text-muted-foreground">
          Based on step{" "}
          <span className="font-mono text-cyan-200/90">{latest.step.toLocaleString()}</span>
        </p>
      ) : null}

      {!latest || !prediction ? (
        <p className="text-xs text-muted-foreground">Waiting for baseline metrics…</p>
      ) : (
        <div className="space-y-4">
          <SliderControl label="Entropy Level" value={entropyLevel} onChange={setEntropyLevel} />
          <SliderControl label="Risk Aversion" value={riskAversion} onChange={setRiskAversion} />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <PredictionCard
              label="Expected Reward"
              value={prediction.expectedReward.toFixed(3)}
              reducedMotion={reducedMotion}
              modeMotion={modeMotion}
            />
            <PredictionCard
              label="Expected Sharpe"
              value={prediction.expectedSharpe.toFixed(2)}
              reducedMotion={reducedMotion}
              modeMotion={modeMotion}
            />
            <PredictionCard
              label="Confidence"
              value={`${(prediction.confidence * 100).toFixed(0)}%`}
              reducedMotion={reducedMotion}
              modeMotion={modeMotion}
            />
          </div>
        </div>
      )}
    </section>
  );
}
