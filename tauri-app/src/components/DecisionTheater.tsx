import { AnimatePresence, motion } from "framer-motion";
import {
  CheckCircle2,
  PauseCircle,
  Shield,
  XCircle,
} from "lucide-react";
import { useMemo } from "react";

import { ActiveSignalCard } from "@/components/decision/ActiveSignalCard";
import { DecisionTheaterStatusHero } from "@/components/decision/DecisionTheaterStatusHero";
import { LiveTradesFeed } from "@/components/decision/LiveTradesFeed";
import { PositionBanner } from "@/components/decision/PositionBanner";
import { ReasoningChainPanel } from "@/components/decision/ReasoningChainPanel";
import { RiskAtDecisionStrip } from "@/components/decision/RiskAtDecisionStrip";
import { FadeInView } from "@/components/cockpit/FadeInView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { useLiveTrading } from "@/hooks/useLiveTrading";
import {
  dispatchApproveLastMutation,
  dispatchPause,
  dispatchRejectMutation,
  dispatchShadowDeploy,
  modifierKeyLabel,
} from "@/lib/commandActions";
import { isCommandDeckBlocked } from "@/lib/commandDeckGuard";
import {
  deriveDecisionBrief,
  verdictLabel,
  verdictTone,
  type DecisionBrief,
} from "@/lib/decisionTheaterModel";
import { staggerContainer, staggerItem } from "@/lib/motionPresets";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { cn } from "@/lib/utils";
import {
  selectConnectionStatus,
  selectCurrentMode,
  selectEvolutionState,
  selectLiveMetrics,
  selectRiskLevel,
  selectSafeModeActive,
  selectTradingLive,
  useCoreStore,
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
      <p className="text-[9px] tracking-[0.14em] text-muted-foreground uppercase">{label}</p>
      <p className="mt-0.5 font-mono text-sm text-cyan-100">{value}</p>
      {barPct !== undefined ? (
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400"
            style={{ width: `${Math.round(barPct)}%` }}
          />
        </div>
      ) : null}
      {subtext ? <p className="mt-1 text-[9px] text-muted-foreground/80">{subtext}</p> : null}
    </div>
  );
}

function MarketContextStrip({ regime, connected }: { regime: string; connected: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-dashed border-white/10 bg-black/20 px-2.5 py-1.5 font-mono text-[10px] text-muted-foreground">
      <span>Market context · {regime} session</span>
      <span className={connected ? "text-emerald-300/90" : "text-amber-300/90"}>
        {connected ? "Live stream" : "Polling / offline"}
      </span>
    </div>
  );
}

export function DecisionTheater({ className, brief: briefOverride }: DecisionTheaterProps) {
  const currentMode = useCoreStore(selectCurrentMode);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const safeModeActive = useCoreStore(selectSafeModeActive);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const riskLevel = useCoreStore(selectRiskLevel);
  const evolutionState = useCoreStore(selectEvolutionState);
  const tradingLive = useCoreStore(selectTradingLive);
  const { healthSnapshot } = useAdaptiveIntelligenceContext();
  const { trades, connected } = useLiveTrading();
  const reducedMotion = usePrefersReducedMotion();

  const brief = useMemo(() => {
    if (briefOverride) return briefOverride;
    return deriveDecisionBrief({
      ...useCoreStore.getState(),
      operatorMode: currentMode,
      liveMetrics,
      riskLevel,
      evolutionState,
      tradingLive,
    });
  }, [briefOverride, currentMode, liveMetrics, riskLevel, evolutionState, tradingLive]);

  const verdictClass = toneClass(verdictTone(brief.verdict));
  const deckBlocked = isCommandDeckBlocked({
    ...useCoreStore.getState(),
    operatorMode: currentMode,
    safeModeActive,
  });
  const actionsDisabled = deckBlocked || brief.proposalHash === null || brief.verdict === "hold";
  const mod = modifierKeyLabel();

  const hasLiveData =
    trades.length > 0 ||
    Boolean(tradingLive?.active_signal) ||
    Boolean(tradingLive?.current_dream) ||
    brief.steps.length > 0;

  const handleAction = (action: DecisionAction) => {
    switch (action) {
      case "approve":
        void dispatchApproveLastMutation();
        break;
      case "reject":
        void dispatchRejectMutation();
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
      className={cn("decision-theater-shell flex h-full min-h-[320px] flex-col gap-2", className)}
      aria-label={`Decision theater — ${brief.steps.length} reasoning steps`}
    >
      <FadeInView delay={0.01}>
        <DecisionTheaterStatusHero
          connectionStatus={connectionStatus}
          hasLiveData={hasLiveData}
          className="mb-2"
        />
      </FadeInView>

      <FadeInView delay={0.02}>
        <PositionBanner trading={tradingLive} />
      </FadeInView>

      <FadeInView delay={0.04} className="min-h-0 flex-1">
        <div className="grid h-full min-h-[200px] grid-cols-1 gap-2 lg:grid-cols-2">
          <LiveTradesFeed trades={trades} className="min-h-[180px]" />
          <ReasoningChainPanel steps={brief.steps} className="min-h-[180px]" />
        </div>
      </FadeInView>

      <FadeInView delay={0.06}>
        <ActiveSignalCard signal={tradingLive?.active_signal ?? null} />
      </FadeInView>

      {tradingLive?.current_dream || tradingLive?.runtime_state ? (
        <FadeInView delay={0.07}>
          <div className="space-y-2">
            {tradingLive.current_dream ? (
              <details className="rounded-lg border border-white/10 bg-black/20 p-2 text-[11px]">
                <summary className="cursor-pointer font-mono text-cyan-200/80">Current Dream (raw)</summary>
                <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-muted-foreground">
                  {JSON.stringify(tradingLive.current_dream, null, 2)}
                </pre>
              </details>
            ) : null}
            {tradingLive.runtime_state ? (
              <details className="rounded-lg border border-white/10 bg-black/20 p-2 text-[11px]">
                <summary className="cursor-pointer font-mono text-cyan-200/80">Runtime State</summary>
                <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-muted-foreground">
                  {JSON.stringify(tradingLive.runtime_state, null, 2)}
                </pre>
              </details>
            ) : null}
          </div>
        </FadeInView>
      ) : null}

      <FadeInView delay={0.08}>
        <RiskAtDecisionStrip
          trading={tradingLive}
          killSwitchActive={Boolean(healthSnapshot?.kill_switch_active)}
        />
      </FadeInView>

      <FadeInView delay={0.1}>
        <MarketContextStrip regime={liveMetrics.regime} connected={connected} />
      </FadeInView>

      <div className="rounded-lg border border-white/10 bg-black/20 backdrop-blur-sm">
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
              subtext={currentMode === "REAL" ? "Quarter-Kelly cap" : "SIM sizing"}
            />
            <MetricCard label="Risk" value={`${brief.metrics.riskScore}`} subtext={riskLevel} />
          </div>
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
                onClick={() => handleAction("approve")}
              >
                <CheckCircle2 data-icon="inline-start" />
                Approve
                <span className="ml-1 text-[9px] text-emerald-100/70">{mod}+A</span>
              </Button>
            </motion.div>
            <motion.div variants={staggerItem}>
              <Button size="xs" variant="destructive" disabled={deckBlocked} onClick={() => handleAction("reject")}>
                <XCircle data-icon="inline-start" />
                Reject
              </Button>
            </motion.div>
            <motion.div variants={staggerItem}>
              <Button
                size="xs"
                variant="outline"
                disabled={actionsDisabled}
                onClick={() => handleAction("shadow")}
              >
                <Shield data-icon="inline-start" />
                Shadow Deploy
              </Button>
            </motion.div>
            <motion.div variants={staggerItem}>
              <Button size="xs" variant="secondary" disabled={deckBlocked} onClick={() => handleAction("pause")}>
                <PauseCircle data-icon="inline-start" />
                Pause
                <span className="ml-1 text-[9px] text-muted-foreground/80">{mod}+P</span>
              </Button>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
