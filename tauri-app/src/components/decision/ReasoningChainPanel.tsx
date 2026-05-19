import { motion } from "framer-motion";

import { Badge } from "@/components/ui/badge";
import {
  confidenceLabel,
  confidenceTone,
  type ReasoningStep,
} from "@/lib/decisionTheaterModel";
import { cn } from "@/lib/utils";

function toneClass(tone: "high" | "moderate" | "low"): string {
  switch (tone) {
    case "high":
      return "border-emerald-400/30 bg-emerald-500/10 text-emerald-300";
    case "moderate":
      return "border-amber-400/30 bg-amber-500/10 text-amber-300";
    case "low":
      return "border-red-400/30 bg-red-500/10 text-red-300";
  }
}

function ReasoningStepCard({
  step,
  index,
  isLast,
}: {
  step: ReasoningStep;
  index: number;
  isLast: boolean;
}) {
  const tone = confidenceTone(step.confidence);
  return (
    <motion.div
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3 }}
      className="relative pl-5"
    >
      {!isLast ? <span className="absolute top-6 bottom-0 left-[7px] w-px bg-white/10" /> : null}
      <span className="absolute top-1.5 left-0 size-3.5 rounded-full border border-cyan-400/40 bg-cyan-500/20" />
      <div className={cn("reasoning-step rounded-lg border p-2.5", toneClass(tone))}>
        <div className="mb-1 flex items-center justify-between gap-2">
          <p className="text-[9px] tracking-[0.16em] uppercase">
            {index + 1}. {step.title}
          </p>
          <Badge variant="outline" className="h-4 px-1.5 text-[9px]">
            {confidenceLabel(step.confidence)} · {Math.round(step.confidence * 100)}%
          </Badge>
        </div>
        <p className="text-[11px] leading-relaxed text-foreground/90">{step.body}</p>
      </div>
    </motion.div>
  );
}

interface ReasoningChainPanelProps {
  steps: ReasoningStep[];
  className?: string;
}

export function ReasoningChainPanel({ steps, className }: ReasoningChainPanelProps) {
  return (
    <section className={cn("flex min-h-0 flex-col", className)}>
      <h4 className="mb-2 font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase">
        Reasoning Chain
      </h4>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1 [scrollbar-width:thin]">
        {steps.map((step, index) => (
          <ReasoningStepCard
            key={step.id}
            step={step}
            index={index}
            isLast={index === steps.length - 1}
          />
        ))}
      </div>
    </section>
  );
}
