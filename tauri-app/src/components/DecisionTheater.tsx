import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  CheckCircle2,
  PauseCircle,
  Shield,
  XCircle,
} from "lucide-react";
import { useMemo } from "react";

import { ModeBadge } from "@/components/cockpit/ModeBadge";
import { FadeInView } from "@/components/cockpit/FadeInView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  dispatchApproveLastMutation,
  dispatchPause,
  dispatchRejectMutation,
  dispatchShadowDeploy,
  modifierKeyLabel,
} from "@/lib/commandActions";
import {
  confidenceLabel,
  confidenceTone,
  deriveDecisionBrief,
  verdictLabel,
  verdictTone,
  type DecisionBrief,
  type ReasoningStep,
} from "@/lib/decisionTheaterModel";
import { staggerContainer, staggerItem } from "@/lib/motionPresets";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { cn } from "@/lib/utils";
import {
  selectCurrentMode,
  selectEvolutionState,
  selectLiveMetrics,
  selectRiskLevel,
  useCoreStore,
  type TradingMode,
} from "@/store/coreStore";

interface DecisionTheaterProps {
  className?: string;
  brief?: DecisionBrief;
}

type DecisionAction = "approve" | "reject" | "shadow" | "pause";

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

function MetricCard({
  label,
  value,
  subtext,
  barPct,
}: {
  label: string;
  value: string;
  subtext?: string;
  barPct?: number;
}) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/20 px-2.5 py-2 backdrop-blur-sm">
      <p className="text-[9px] tracking-[0.14em] text-muted-foreground uppercase">
        {label}
      </p>
      <p className="mt-0.5 font-mono text-sm text-cyan-100">{value}</p>
      {barPct !== undefined ? (
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400"
            style={{ width: `${Math.round(barPct)}%` }}
          />
        </div>
      ) : null}
      {subtext ? (
        <p className="mt-1 text-[9px] text-muted-foreground/80">{subtext}</p>
      ) : null}
    </div>
  );
}

function ChartPlaceholder({ mode }: { mode: TradingMode }) {
  return (
    <div
      className="decision-chart-placeholder relative flex h-full min-h-[220px] flex-col items-center justify-center overflow-hidden rounded-lg border border-dashed border-white/15 bg-black/25 p-4 backdrop-blur-sm"
      aria-label="NinjaTrader chart placeholder for future embed"
    >
      <div className="decision-chart-scan pointer-events-none absolute inset-x-0 top-1/2 h-px bg-cyan-400/40" />
      <BarChart3 className="mb-3 size-10 text-cyan-400/50" aria-hidden />
      <p className="text-center font-mono text-[11px] tracking-wide text-cyan-100/90">
        NinjaTrader Chart — embed pending
      </p>
      <p className="mt-1 text-center font-mono text-[10px] text-muted-foreground/70">
        ES · 5m
      </p>
      <div className="mt-3">
        <ModeBadge mode={mode} />
      </div>
    </div>
  );
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
      transition={{ delay: index * 0.08, duration: 0.35 }}
      className="relative pl-5"
    >
      {!isLast ? (
        <span className="absolute top-6 bottom-0 left-[7px] w-px bg-white/10" />
      ) : null}
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

function ReasoningPanel({
  brief,
  mode,
  riskLevel,
  onAction,
}: {
  brief: DecisionBrief;
  mode: TradingMode;
  riskLevel: string;
  onAction: (action: DecisionAction) => void;
}) {
  const verdictClass = toneClass(verdictTone(brief.verdict));
  const actionsDisabled = brief.proposalHash === null || brief.verdict === "hold";
  const mod = modifierKeyLabel();
  const reducedMotion = usePrefersReducedMotion();

  return (
    <div className="flex h-full min-h-[220px] flex-col overflow-hidden rounded-lg border border-white/10 bg-black/20 backdrop-blur-sm">
      <div className="border-b border-white/10 px-3 py-2.5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <AnimatePresence mode="wait">
              <motion.p
                key={brief.headline}
                className="font-mono text-[11px] leading-snug text-violet-100/95"
                initial={reducedMotion ? false : { opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reducedMotion ? undefined : { opacity: 0, y: -4 }}
                transition={{ duration: 0.2 }}
              >
                {brief.headline}
              </motion.p>
            </AnimatePresence>
            {brief.proposalHash ? (
              <p className="mt-1 truncate font-mono text-[9px] text-muted-foreground/70">
                proposal: {brief.proposalHash.slice(0, 16)}…
              </p>
            ) : null}
          </div>
          <Badge className={cn("shrink-0 text-[9px] uppercase", verdictClass)}>
            {verdictLabel(brief.verdict)}
          </Badge>
        </div>

        <div className="mt-2 grid grid-cols-3 gap-1.5">
          <MetricCard
            label="Confidence"
            value={`${Math.round(brief.metrics.overallConfidence * 100)}%`}
            barPct={brief.metrics.overallConfidence * 100}
          />
          <MetricCard
            label="Kelly"
            value={`${Math.round(brief.metrics.kellyFraction * 100)}%`}
            subtext={mode === "REAL" ? "Quarter-Kelly cap" : "SIM sizing"}
          />
          <MetricCard
            label="Risk"
            value={`${brief.metrics.riskScore}`}
            subtext={riskLevel}
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-2.5">
        {brief.steps.map((step, index) => (
          <ReasoningStepCard
            key={step.id}
            step={step}
            index={index}
            isLast={index === brief.steps.length - 1}
          />
        ))}
      </div>

      <div className="border-t border-white/10 px-3 py-2.5">
        <motion.div
          className="flex flex-wrap gap-1.5"
          variants={staggerContainer}
          initial={reducedMotion ? false : "hidden"}
          animate="visible"
        >
          <motion.div variants={staggerItem}>
          <Button
            size="xs"
            className="bg-emerald-600/80 text-white hover:bg-emerald-600"
            disabled={actionsDisabled}
            onClick={() => onAction("approve")}
          >
            <CheckCircle2 data-icon="inline-start" />
            Approve
            <span className="ml-1 text-[9px] text-emerald-100/70">{mod}+A</span>
          </Button>
          </motion.div>
          <motion.div variants={staggerItem}>
          <Button
            size="xs"
            variant="destructive"
            onClick={() => onAction("reject")}
          >
            <XCircle data-icon="inline-start" />
            Reject
          </Button>
          </motion.div>
          <motion.div variants={staggerItem}>
          <Button
            size="xs"
            variant="outline"
            disabled={actionsDisabled}
            onClick={() => onAction("shadow")}
          >
            <Shield data-icon="inline-start" />
            Shadow Deploy
          </Button>
          </motion.div>
          <motion.div variants={staggerItem}>
          <Button size="xs" variant="secondary" onClick={() => onAction("pause")}>
            <PauseCircle data-icon="inline-start" />
            Pause
            <span className="ml-1 text-[9px] text-muted-foreground/80">{mod}+P</span>
          </Button>
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
}

export function DecisionTheater({ className, brief: briefOverride }: DecisionTheaterProps) {
  const currentMode = useCoreStore(selectCurrentMode);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const riskLevel = useCoreStore(selectRiskLevel);
  const evolutionState = useCoreStore(selectEvolutionState);

  const brief = useMemo(() => {
    if (briefOverride) {
      return briefOverride;
    }
    return deriveDecisionBrief({
      ...useCoreStore.getState(),
      operatorMode: currentMode,
      liveMetrics,
      riskLevel,
      evolutionState,
    });
  }, [briefOverride, currentMode, liveMetrics, riskLevel, evolutionState]);

  const handleAction = (action: DecisionAction) => {
    switch (action) {
      case "approve":
        dispatchApproveLastMutation();
        break;
      case "reject":
        dispatchRejectMutation();
        break;
      case "shadow":
        dispatchShadowDeploy();
        break;
      case "pause":
        dispatchPause();
        break;
    }
  };

  return (
    <div
      className={cn(
        "decision-theater-shell grid h-full min-h-[220px] grid-cols-2 gap-2",
        className,
      )}
      aria-label={`Decision theater — ${brief.steps.length} reasoning steps`}
    >
      <FadeInView delay={0.04} className="min-h-0">
        <ChartPlaceholder mode={currentMode} />
      </FadeInView>
      <FadeInView delay={0.1} className="min-h-0">
        <ReasoningPanel
          brief={brief}
          mode={currentMode}
          riskLevel={riskLevel}
          onAction={handleAction}
        />
      </FadeInView>
    </div>
  );
}
