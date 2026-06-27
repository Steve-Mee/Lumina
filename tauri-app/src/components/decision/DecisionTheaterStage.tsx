import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  CheckCircle2,
  PauseCircle,
  Shield,
  XCircle,
} from "lucide-react";

import { DecisionTheaterDebugOverflow } from "@/components/decision/DecisionTheaterDebugOverflow";
import { HudSignal } from "@/components/cockpit/HudSignal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  dispatchApproveLastMutation,
  dispatchPause,
  dispatchRejectMutation,
  dispatchShadowDeploy,
  modifierKeyLabel,
} from "@/lib/commandActions";
import type { DecisionBrief } from "@/lib/decisionTheaterModel";
import { verdictLabel, verdictTone } from "@/lib/decisionTheaterModel";
import {
  resolveDecisionStageHero,
  resolveDecisionTradePreview,
  signalChipClass,
  verdictToneClass,
} from "@/lib/decisionTheaterLayout";
import type { TradeRecord } from "@/lib/liveTradingTypes";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import { staggerContainer, staggerItemWith, transitionOrNone } from "@/lib/motionPresets";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { modeApproveButtonClass, modeTitleClass, modeValueClass } from "@/lib/modePresentation";
import { useDeckPanelStore } from "@/store/deckPanelStore";
import { cn } from "@/lib/utils";
import type { RiskLevel, TradingMode } from "@/store/coreStore";

type DecisionAction = "approve" | "reject" | "shadow" | "pause";

interface DecisionTheaterStageProps {
  brief: DecisionBrief;
  trading: LiveTradingSnapshot | null;
  trades: TradeRecord[];
  currentMode: TradingMode;
  riskLevel: RiskLevel;
  killSwitchActive: boolean;
  deckBlocked: boolean;
  className?: string;
  motionReduced?: boolean;
}

export function DecisionTheaterStage({
  brief,
  trading,
  trades,
  currentMode,
  riskLevel,
  killSwitchActive,
  deckBlocked,
  className,
  motionReduced: motionReducedProp,
}: DecisionTheaterStageProps) {
  const reducedMotionPref = usePrefersReducedMotion();
  const reducedMotion = motionReducedProp ?? reducedMotionPref;
  const modeMotion = useModeMotion();
  const staggerItem = staggerItemWith(modeMotion);
  const verdictClass = verdictToneClass(verdictTone(brief.verdict));
  const [verdictFlash, setVerdictFlash] = useState(false);
  const prevVerdictRef = useRef(brief.verdict);

  useEffect(() => {
    if (prevVerdictRef.current === brief.verdict) {
      return;
    }
    prevVerdictRef.current = brief.verdict;
    setVerdictFlash(true);
    const timer = window.setTimeout(() => setVerdictFlash(false), 220);
    return () => window.clearTimeout(timer);
  }, [brief.verdict]);
  const actionsDisabled = deckBlocked || brief.proposalHash === null || brief.verdict === "hold";
  const mod = modifierKeyLabel();
  const signal = trading?.active_signal ?? null;

  const stageHero = resolveDecisionStageHero(
    currentMode,
    brief,
    trading,
    riskLevel,
    killSwitchActive,
  );
  const { preview: tradePreview, overflowCount: tradeOverflowCount } =
    resolveDecisionTradePreview(trades);
  const proposalActive = brief.verdict !== "hold" && brief.proposalHash !== null;

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
    <section
      data-mode={currentMode}
      className={cn(
        "decision-theater-stage flex min-h-0 min-w-0 flex-1 flex-col",
        verdictFlash && "decision-theater-stage--verdict-flash",
        className,
      )}
    >
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 [scrollbar-width:thin]">
        <header className="flex items-start justify-between gap-3">
          <AnimatePresence mode="wait">
            <motion.p
              key={brief.headline}
              className={cn("min-w-0 font-mono text-sm leading-snug", modeTitleClass(currentMode))}
              initial={reducedMotion ? false : { opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reducedMotion ? undefined : { opacity: 0, y: -4 }}
              transition={transitionOrNone(reducedMotion, modeMotion)}
            >
              {brief.headline}
            </motion.p>
          </AnimatePresence>
          <Badge
            className={cn(
              "shrink-0 text-[9px] uppercase",
              verdictClass,
              verdictFlash && "decision-verdict-flash",
            )}
          >
            {verdictLabel(brief.verdict)}
          </Badge>
        </header>

        <div className="decision-theater-stage__metrics mt-4 flex gap-4 overflow-x-auto pb-1">
          <HudSignal
            label={stageHero.primary.label}
            value={stageHero.primary.value}
            glow={stageHero.primary.glow}
            intensity={stageHero.primary.intensity}
          />
          {stageHero.secondary ? (
            <HudSignal
              label={stageHero.secondary.label}
              value={stageHero.secondary.value}
              glow={stageHero.secondary.glow}
              intensity={stageHero.secondary.intensity}
            />
          ) : null}
        </div>

        {signal ? (
          <div className="mt-4 space-y-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
                Active Signal
              </span>
              <span
                className={cn(
                  "rounded-md px-2 py-0.5 font-mono text-xs tracking-wider uppercase",
                  signalChipClass(signal.signal),
                )}
              >
                {signal.signal}
              </span>
              <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-foreground/85">
                {Math.round(signal.confidence * 100)}%
              </span>
              <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                CF {Math.round(signal.confluence * 100)}%
              </span>
              {proposalActive ? (
                <>
                  <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    SL {signal.stop.toFixed(2)}
                  </span>
                  <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    TP {signal.target.toFixed(2)}
                  </span>
                </>
              ) : null}
              {signal.strategy ? (
                <span className="font-mono text-[10px] text-muted-foreground">{signal.strategy}</span>
              ) : null}
            </div>
            <p className="text-xs leading-relaxed text-foreground/85 line-clamp-1">
              {signal.reason || "No reason published."}
            </p>
          </div>
        ) : (
          <p className="mt-4 text-xs text-muted-foreground">No active signal telemetry.</p>
        )}

        <details className="decision-theater-stage__recent mt-5 group">
          <summary className="mb-2 flex cursor-pointer list-none items-center justify-between gap-2 font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase [&::-webkit-details-marker]:hidden">
            <span>Recent{trades.length > 0 ? ` (${trades.length})` : ""}</span>
            {trades.length > 0 ? (
              <Button
                type="button"
                size="xs"
                variant="command-ghost"
                className="h-6 px-2 text-[9px]"
                onClick={(event) => {
                  event.preventDefault();
                  useDeckPanelStore.getState().setActiveRightTab("monitor");
                }}
              >
                Open Monitor
              </Button>
            ) : null}
          </summary>
          {tradePreview.length === 0 ? (
            <p className="text-xs text-muted-foreground">No recent executions.</p>
          ) : (
            <ul className="space-y-0">
              {tradePreview.map((trade, index) => (
                <li
                  key={`${trade.ts ?? "trade"}-${index}`}
                  className="decision-theater-stage__trade-row py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={cn("font-mono text-[10px] uppercase", modeValueClass(currentMode))}>
                      {trade.signal || "—"}
                    </span>
                    <span
                      className={cn(
                        "font-mono text-[10px] tabular-nums",
                        trade.pnl >= 0 ? "text-emerald-300" : "text-red-300",
                      )}
                    >
                      {trade.pnl.toFixed(2)}
                    </span>
                  </div>
                  <p className="mt-0.5 font-mono text-[9px] text-muted-foreground">
                    {trade.entry.toFixed(2)} → {trade.exit.toFixed(2)} · qty {trade.qty}
                    {trade.symbol ? ` · ${trade.symbol}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {tradeOverflowCount > 0 ? (
            <p className="mt-1 font-mono text-[9px] text-muted-foreground">
              +{tradeOverflowCount} more in debug metrics
            </p>
          ) : null}
        </details>
      </div>

      <footer className="shrink-0 border-t border-white/5 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <motion.div
            className="flex flex-wrap gap-1.5"
            variants={staggerContainer}
            initial={reducedMotion ? false : "hidden"}
            animate="visible"
          >
            <motion.div variants={staggerItem}>
              <Button
                type="button"
                size="xs"
                variant="command-primary"
                className={modeApproveButtonClass(currentMode)}
                disabled={actionsDisabled}
                onClick={() => handleAction("approve")}
              >
                <CheckCircle2 data-icon="inline-start" />
                Approve
                <span className="ml-1 text-[9px] text-emerald-100/70">{mod}+A</span>
              </Button>
            </motion.div>
            <motion.div variants={staggerItem}>
              <Button
                size="xs"
                variant="command-ghost"
                data-intent="danger"
                disabled={deckBlocked}
                onClick={() => handleAction("reject")}
              >
                <XCircle data-icon="inline-start" />
                Reject
              </Button>
            </motion.div>
            <motion.div variants={staggerItem}>
              <Button
                size="xs"
                variant="command-ghost"
                disabled={actionsDisabled}
                onClick={() => handleAction("shadow")}
              >
                <Shield data-icon="inline-start" />
                Shadow Deploy
              </Button>
            </motion.div>
            <motion.div variants={staggerItem}>
              <Button
                size="xs"
                variant="command-ghost"
                disabled={deckBlocked}
                onClick={() => handleAction("pause")}
              >
                <PauseCircle data-icon="inline-start" />
                Pause
                <span className="ml-1 text-[9px] text-muted-foreground/80">{mod}+P</span>
              </Button>
            </motion.div>
          </motion.div>
          <DecisionTheaterDebugOverflow trading={trading} overflow={stageHero.overflow} />
        </div>
      </footer>
    </section>
  );
}
