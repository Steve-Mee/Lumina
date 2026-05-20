import { motion } from "framer-motion";
import { Activity, AlertTriangle, Target, TrendingUp, type LucideIcon } from "lucide-react";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone } from "@/lib/motionPresets";
import {
  buildEvolutionTimeline,
  DEFAULT_TIMELINE_MAX_STEPS,
  type EvolutionEventType,
  type EvolutionTimelineEntry,
  type EvolutionTimelineEvent,
} from "@/lib/ppoEvolutionTimelineModel";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { cn } from "@/lib/utils";

export interface EvolutionTimelineProps {
  logs: PPOEvolutionMetric[];
  maxSteps?: number;
  orientation?: "vertical" | "horizontal";
  compact?: boolean;
  className?: string;
}

const EVENT_ICON: Record<EvolutionEventType, LucideIcon> = {
  reward_spike: TrendingUp,
  entropy_dip: Activity,
  winrate_surge: Target,
  explained_variance_drop: AlertTriangle,
};

const EVENT_STYLES: Record<EvolutionEventType, string> = {
  reward_spike: "border-cyan-500/30 bg-cyan-950/40 text-cyan-200",
  entropy_dip: "border-violet-500/30 bg-violet-950/40 text-violet-200",
  winrate_surge: "border-emerald-500/30 bg-emerald-950/40 text-emerald-200",
  explained_variance_drop: "border-amber-500/30 bg-amber-950/40 text-amber-200",
};

function EventPill({ event, compact }: { event: EvolutionTimelineEvent; compact?: boolean }) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const Icon = EVENT_ICON[event.type];

  return (
    <motion.span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono",
        compact ? "text-[9px]" : "text-[10px]",
        EVENT_STYLES[event.type],
      )}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={transitionOrNone(reducedMotion, modeMotion)}
    >
      <Icon className={cn(compact ? "size-2.5" : "size-3")} aria-hidden />
      {event.label}
    </motion.span>
  );
}

function TimelineMetrics({
  entry,
  compact,
}: {
  entry: EvolutionTimelineEntry;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap gap-x-4 gap-y-1 font-mono tabular-nums text-muted-foreground",
        compact ? "text-[10px]" : "text-[11px]",
      )}
    >
      <span>
        Reward{" "}
        <span className="text-cyan-100/90">{entry.meanReward.toFixed(3)}</span>
      </span>
      <span>
        Winrate{" "}
        <span className="text-emerald-200/90">{(entry.winrate * 100).toFixed(1)}%</span>
      </span>
    </div>
  );
}

function VerticalTimelineEntry({
  entry,
  index,
  isLatest,
  reducedMotion,
  compact,
}: {
  entry: EvolutionTimelineEntry;
  index: number;
  isLatest: boolean;
  reducedMotion: boolean;
  compact?: boolean;
}) {
  const hasEvents = entry.events.length > 0;

  return (
    <motion.li
      className="relative grid grid-cols-[1.5rem_1fr] gap-3 pb-4 last:pb-0"
      variants={fadeUp}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
      transition={transitionOrNone(reducedMotion, {
        duration: 0.3,
        delay: reducedMotion ? 0 : index * 0.04,
      })}
    >
      <div className="relative flex justify-center">
        <span
          className={cn(
            "relative z-10 mt-1 inline-flex size-3 rounded-full border",
            isLatest
              ? "border-cyan-400/70 bg-cyan-400/30 lumina-glow-edge"
              : "border-white/20 bg-white/10",
            hasEvents && !reducedMotion && "animate-pulse",
          )}
          aria-hidden
        />
      </div>

      <div
        className={cn(
          "lumina-surface-muted rounded-lg border p-3",
          isLatest ? "border-cyan-400/30" : "border-white/10",
        )}
      >
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <span className="font-mono text-xs tracking-wide text-cyan-200/90 uppercase">
            Step {entry.step.toLocaleString()}
          </span>
          {isLatest ? (
            <span className="rounded-full border border-cyan-500/30 bg-cyan-950/40 px-2 py-0.5 font-mono text-[9px] tracking-wide text-cyan-200 uppercase">
              Latest
            </span>
          ) : null}
        </div>
        <TimelineMetrics entry={entry} compact={compact} />
        {hasEvents ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {entry.events.map((event) => (
              <EventPill key={`${entry.step}-${event.type}`} event={event} compact={compact} />
            ))}
          </div>
        ) : null}
      </div>
    </motion.li>
  );
}

function HorizontalTimelineEntry({
  entry,
  index,
  isLatest,
  reducedMotion,
  compact,
}: {
  entry: EvolutionTimelineEntry;
  index: number;
  isLatest: boolean;
  reducedMotion: boolean;
  compact?: boolean;
}) {
  return (
    <motion.li
      className={cn(
        "w-[160px] shrink-0 snap-start lumina-surface-muted rounded-lg border p-3",
        isLatest ? "border-cyan-400/30" : "border-white/10",
      )}
      variants={fadeUp}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
      transition={transitionOrNone(reducedMotion, {
        duration: 0.3,
        delay: reducedMotion ? 0 : index * 0.04,
      })}
    >
      <p className="mb-2 font-mono text-[10px] tracking-wide text-cyan-200/90 uppercase">
        Step {entry.step.toLocaleString()}
      </p>
      <TimelineMetrics entry={entry} compact={compact} />
      {entry.events.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {entry.events.map((event) => {
            const Icon = EVENT_ICON[event.type];
            return (
              <span
                key={`${entry.step}-${event.type}`}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5",
                  EVENT_STYLES[event.type],
                )}
                title={event.label}
              >
                <Icon className="size-2.5" aria-hidden />
              </span>
            );
          })}
        </div>
      ) : null}
    </motion.li>
  );
}

export function EvolutionTimeline({
  logs,
  maxSteps = DEFAULT_TIMELINE_MAX_STEPS,
  orientation = "vertical",
  compact = false,
  className,
}: EvolutionTimelineProps) {
  const reducedMotion = usePrefersReducedMotion();
  const entries = buildEvolutionTimeline(logs, maxSteps);
  const latestStep = entries.length > 0 ? entries[entries.length - 1]!.step : null;

  return (
    <section
      className={cn(
        "relative overflow-hidden lumina-surface-muted rounded-lg p-3",
        className,
      )}
      aria-label="Evolution timeline"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/30 to-violet-400/20"
        aria-hidden
      />
      <p className="mb-3 text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
        Evolution Timeline
      </p>

      {entries.length === 0 ? (
        <p className="text-xs text-muted-foreground">Waiting for training history…</p>
      ) : orientation === "horizontal" ? (
        <ol className="flex gap-3 overflow-x-auto pb-1 snap-x snap-mandatory">
          {entries.map((entry, index) => (
            <HorizontalTimelineEntry
              key={entry.step}
              entry={entry}
              index={index}
              isLatest={entry.step === latestStep}
              reducedMotion={reducedMotion}
              compact={compact}
            />
          ))}
        </ol>
      ) : (
        <div className="max-h-[320px] overflow-y-auto pr-1 [scrollbar-color:rgba(255,255,255,0.15)_transparent] [scrollbar-width:thin]">
          <ol className="relative space-y-0 pl-1">
            <div
              className="pointer-events-none absolute top-2 bottom-2 left-[0.72rem] w-px bg-gradient-to-b from-cyan-400/40 to-violet-400/20"
              aria-hidden
            />
            {entries.map((entry, index) => (
              <VerticalTimelineEntry
                key={entry.step}
                entry={entry}
                index={index}
                isLatest={entry.step === latestStep}
                reducedMotion={reducedMotion}
                compact={compact}
              />
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
