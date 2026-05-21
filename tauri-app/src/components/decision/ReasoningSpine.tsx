import { useState } from "react";
import { motion } from "framer-motion";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone } from "@/lib/motionPresets";
import { reasoningSpineTitleClass } from "@/lib/modePresentation";
import { confidenceLabel, type ReasoningStep } from "@/lib/decisionTheaterModel";
import type { TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface ReasoningSpineProps {
  steps: ReasoningStep[];
  mode: TradingMode;
  className?: string;
  motionReduced?: boolean;
  compact?: boolean;
}

function SpineStep({
  step,
  index,
  isLast,
  reducedMotion,
  modeMotion,
  mode,
  compact,
}: {
  step: ReasoningStep;
  index: number;
  isLast: boolean;
  reducedMotion: boolean;
  modeMotion: ReturnType<typeof useModeMotion>;
  mode: TradingMode;
  compact: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const collapsible = !compact && step.body.length > 120;

  if (compact) {
    return (
      <motion.article
        initial={reducedMotion ? false : { opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={transitionOrNone(reducedMotion, { ...modeMotion, delay: index * 0.05 })}
        className={cn("reasoning-spine__step relative pb-3 pl-6", isLast && "pb-1")}
      >
        <span className="reasoning-spine__node absolute top-1 left-0" aria-hidden />
        {!isLast ? (
          <span className="reasoning-spine__connector absolute top-3 bottom-0 left-[5px]" aria-hidden />
        ) : null}
        <p className={cn("font-mono text-xs tracking-[0.16em] uppercase", reasoningSpineTitleClass(mode))}>
          {index + 1}. {step.title}
        </p>
      </motion.article>
    );
  }

  return (
    <motion.article
      initial={reducedMotion ? false : { opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={transitionOrNone(reducedMotion, { ...modeMotion, delay: index * 0.05 })}
      className={cn("reasoning-spine__step relative pb-4 pl-6", isLast && "pb-2")}
    >
      <span className="reasoning-spine__node absolute top-1 left-0" aria-hidden />
      {!isLast ? (
        <span className="reasoning-spine__connector absolute top-3 bottom-0 left-[5px]" aria-hidden />
      ) : null}
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <p className={cn("font-mono text-xs tracking-[0.16em] uppercase", reasoningSpineTitleClass(mode))}>
          {index + 1}. {step.title}
        </p>
        <span className="font-mono text-[10px] text-muted-foreground/80">
          {confidenceLabel(step.confidence)} · {Math.round(step.confidence * 100)}%
        </span>
      </header>
      <p
        className={cn(
          "mt-1.5 text-sm leading-relaxed text-foreground/90",
          collapsible && !expanded && "reasoning-spine__body--collapsed",
        )}
      >
        {step.body}
      </p>
      {collapsible ? (
        <button
          type="button"
          className="reasoning-spine__toggle"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? "Collapse" : "Expand reasoning"}
        </button>
      ) : null}
    </motion.article>
  );
}

export function ReasoningSpine({ steps, mode, className, motionReduced, compact = false }: ReasoningSpineProps) {
  const reducedMotionPref = usePrefersReducedMotion();
  const reducedMotion = motionReduced ?? reducedMotionPref;
  const modeMotion = useModeMotion();

  if (steps.length === 0) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)}>
        No reasoning steps yet — waiting for live intelligence stream.
      </p>
    );
  }

  return (
    <aside className={cn("reasoning-spine min-w-0", className)} aria-label="Reasoning spine">
      <span className="reasoning-spine__rail mb-4 block" aria-hidden />
      {steps.map((step, index) => (
        <SpineStep
          key={`${step.title}-${index}`}
          step={step}
          index={index}
          isLast={index === steps.length - 1}
          reducedMotion={reducedMotion}
          modeMotion={modeMotion}
          mode={mode}
          compact={compact}
        />
      ))}
    </aside>
  );
}
