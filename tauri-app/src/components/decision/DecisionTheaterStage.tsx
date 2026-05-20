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
import { isCommandDeckBlocked } from "@/lib/commandDeckGuard";
import type { DecisionBrief } from "@/lib/decisionTheaterModel";
import { verdictLabel, verdictTone } from "@/lib/decisionTheaterModel";
import {
  formatKellyLabel,
  formatPositionQty,
  formatPositionSide,
  riskHudGlow,
  signalChipClass,
  verdictToneClass,
} from "@/lib/decisionTheaterLayout";
import type { TradeRecord } from "@/lib/liveTradingTypes";
import type { LiveTradingSnapshot } from "@/lib/liveTradingTypes";
import { staggerContainer, staggerItemWith, transitionOrNone } from "@/lib/motionPresets";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { modeTitleClass, modeValueClass } from "@/lib/modePresentation";
import { formatUsd } from "@/lib/tradingPerformanceModel";
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
  const actionsDisabled = deckBlocked || brief.proposalHash === null || brief.verdict === "hold";
  const mod = modifierKeyLabel();
  const signal = trading?.active_signal ?? null;
  const position = trading?.position;

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
    <section className={cn("decision-theater-stage flex min-h-0 min-w-0 flex-1 flex-col", className)}>
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
          <Badge className={cn("shrink-0 text-[9px] uppercase", verdictClass)}>
            {verdictLabel(brief.verdict)}
          </Badge>
        </header>

        <div className="decision-theater-stage__metrics mt-4 flex gap-4 overflow-x-auto pb-1">
          <HudSignal
            label="Confidence"
            value={`${Math.round(brief.metrics.overallConfidence * 100)}%`}
            glow="violet"
            intensity={brief.metrics.overallConfidence}
          />
          <HudSignal
            label="Kelly"
            value={formatKellyLabel(currentMode, brief.metrics.kellyFraction)}
            glow="cyan"
          />
          <HudSignal
            label="Risk"
            value={`${brief.metrics.riskScore}`}
            glow={riskHudGlow(riskLevel)}
            intensity={brief.metrics.riskScore / 100}
          />
          <HudSignal label="Regime" value={brief.metrics.regime} glow="neutral" />
        </div>

        <div className="decision-theater-stage__metrics mt-3 flex gap-4 overflow-x-auto pb-1">
          <HudSignal label="Position" value={formatPositionSide(trading)} glow="cyan" />
          <HudSignal label="Size" value={formatPositionQty(trading)} glow="neutral" />
          <HudSignal
            label="Open P&L"
            value={formatUsd(position?.open_pnl ?? null)}
            glow={(position?.open_pnl ?? 0) >= 0 ? "emerald" : "amber"}
          />
          <HudSignal
            label="Daily"
            value={formatUsd(position?.daily_pnl ?? null)}
            glow={(position?.daily_pnl ?? 0) >= 0 ? "emerald" : "amber"}
          />
          <HudSignal
            label="Losses"
            value={`${trading?.consecutive_losses ?? 0}`}
            glow={(trading?.consecutive_losses ?? 0) > 2 ? "amber" : "neutral"}
          />
          <HudSignal
            label="Kill Switch"
            value={killSwitchActive ? "ON" : "Off"}
            glow={killSwitchActive ? "amber" : "emerald"}
          />
        </div>

        {signal ? (
          <div className="mt-4 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
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
              <span className={cn("font-mono text-[11px]", modeValueClass(currentMode))}>
                {Math.round(signal.confidence * 100)}% · Confluence{" "}
                {Math.round(signal.confluence * 100)}%
              </span>
            </div>
            <p className="text-sm leading-relaxed text-foreground/90">
              {signal.reason || "No reason published."}
            </p>
            <p className="font-mono text-[10px] text-muted-foreground">
              Stop {signal.stop.toFixed(2)} · Target {signal.target.toFixed(2)} ·{" "}
              {signal.strategy || "strategy n/a"}
            </p>
          </div>
        ) : (
          <p className="mt-4 text-xs text-muted-foreground">No active signal telemetry.</p>
        )}

        <div className="mt-5">
          <h4 className="mb-2 font-mono text-[10px] tracking-[0.16em] text-muted-foreground uppercase">
            Recent
          </h4>
          {trades.length === 0 ? (
            <p className="text-xs text-muted-foreground">No recent executions.</p>
          ) : (
            <ul className="space-y-0">
              {trades.map((trade, index) => (
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
        </div>
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
                className="border-emerald-500/35 bg-emerald-600/80 text-white hover:bg-emerald-600"
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
          <DecisionTheaterDebugOverflow trading={trading} />
        </div>
      </footer>
    </section>
  );
}
