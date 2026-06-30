import { useEffect, useMemo, useRef, useState } from "react";
import { Settings } from "lucide-react";
import { motion } from "framer-motion";
import { useShallow } from "zustand/react/shallow";

import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { useOrganismEnvelope } from "@/context/OrganismEnvelopeContext";
import { BotConfigurationDialog } from "@/components/cockpit/BotConfigurationDialog";
import { HudOrganismCenter } from "@/components/cockpit/HudOrganismCenter";
import { HudNerveTap } from "@/components/cockpit/HudNerveTap";
import { LaunchNinjaTraderButton } from "@/components/cockpit/LaunchNinjaTraderButton";
import { ModeTransitionVeil } from "@/components/cockpit/ModeTransitionVeil";
import { PresenceRail } from "@/components/cockpit/PresenceRail";
import { TrainingMonitorTrigger } from "@/components/cockpit/TrainingMonitorTrigger";
import { SettingsDialog } from "@/components/cockpit/SettingsDialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useDeckTransition } from "@/hooks/useDeckTransition";
import { handleRuntimeError } from "@/lib/runtimeErrorToast";
import {
  modeSwitchShellClass,
  modeSwitchActivePillClass,
  modeSwitchActivePillMotionClass,
  modeSwitchTooltip,
  realDialogBodyClass,
  realDialogTitleClass,
} from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import {
  aggregateIntegrity,
  deriveCitadelWallsFromInputs,
} from "@/lib/riskCitadelMetrics";
import { useRuntimeStatusPoll, refreshRuntimeStatus } from "@/hooks/useRuntimeStatusPoll";
import {
  emergencyStop,
  flattenPositions,
  pauseTradingSafely,
  startEngine,
  stopAllActivities,
  stopEngine,
} from "@/lib/runtimeClient";
import { fetchMaturationProgress, postApproveReal } from "@/lib/maturationClient";
import { MaturityProgressStrip } from "@/components/cockpit/MaturityProgressStrip";
import {
  springLuxury,
} from "@/lib/motionPresets";
import {
  resolveHudAnnexHintCopy,
  resolveHudHeroLayout,
} from "@/lib/hudSignalLayout";
import {
  resolveOverflowItems,
  type HudOverflowItem,
} from "@/lib/hudOverflowLayout";
import { useModeMotion } from "@/hooks/useModeMotion";
import { toast } from "sonner";
import {
  selectConnectionStatus,
  selectCurrentMode,
  selectFallbackMode,
  selectLiveMetrics,
  selectModeSyncStatus,
  selectReportedMode,
  useCoreStore,
  type ConnectionStatus,
  type TradingMode,
} from "@/store/coreStore";
import { useDeckPanelStore } from "@/store/deckPanelStore";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import { useBotConfigStore } from "@/store/botConfigStore";
import {
  subscribeHudLayoutPrefs,
  useHudLayoutPrefsStore,
} from "@/store/hudLayoutPrefsStore";
import { useHudMetricsHintStore } from "@/store/hudMetricsHintStore";
import { useSettingsDialogStore } from "@/store/settingsDialogStore";

interface CommandHudProps {
  className?: string;
}

function formatEquity(equity: number | null): string {
  if (equity === null) {
    return "—";
  }
  return `$${equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatEquityCompact(equity: number | null): string {
  if (equity === null) {
    return "—";
  }
  if (equity >= 1000) {
    return `$${Math.round(equity / 1000)}k`;
  }
  return `$${Math.round(equity)}`;
}

function connectionVitality(status: ConnectionStatus, fallback: boolean): number {
  if (fallback) {
    return 0.55;
  }
  switch (status) {
    case "connected":
      return 0.92;
    case "connecting":
    case "reconnecting":
      return 0.6;
    case "disconnected":
      return 0.35;
  }
}

function ModeSwitch({
  mode,
  reportedMode,
  syncStatus,
  onSelect,
  realEligible,
}: {
  mode: TradingMode;
  reportedMode: TradingMode | null;
  syncStatus: "idle" | "pending" | "error";
  onSelect: (mode: TradingMode) => void;
  realEligible: boolean;
}) {
  const modeMotion = useModeMotion();
  const pillMotion = mode === "REAL" ? springLuxury : modeMotion;
  const showSyncDot = syncStatus === "pending" || syncStatus === "error";
  const showMismatch =
    reportedMode !== null && reportedMode !== mode && syncStatus !== "pending";

  return (
    <div className="relative flex flex-col items-end gap-0.5">
      {(showMismatch || showSyncDot) && (
        <span
          className={cn(
            "absolute -top-1 -right-1 size-2 rounded-full",
            syncStatus === "error" ? "bg-red-400" : "bg-[#c9b896]",
          )}
          title={
            syncStatus === "error"
              ? "Mode sync failed — local override active"
              : syncStatus === "pending"
                ? "Mode sync in progress"
                : "Backend reports different mode"
          }
          aria-label={
            syncStatus === "error"
              ? "Mode sync error"
              : syncStatus === "pending"
                ? "Mode syncing"
                : "Mode mismatch with backend"
          }
        />
      )}
      <motion.div
        layout
        className={cn(
          "relative flex rounded-lg border p-0.5 lumina-glow-edge",
          modeSwitchShellClass(mode),
        )}
        transition={modeMotion}
        role="group"
        aria-label="Trading mode"
      >
        {(["SIM", "REAL"] as const).map((option) => {
          const active = mode === option;
          return (
            <Button
              key={option}
              type="button"
              size="sm"
              variant="command-ghost"
              aria-pressed={active}
              title={modeSwitchTooltip(option)}
              onClick={() => {
                if (option === "REAL" && !realEligible) {
                  return;
                }
                onSelect(option);
              }}
              disabled={option === "REAL" && !realEligible}
              className={cn(
                "relative h-9 min-w-[64px] font-mono text-[11px] tracking-[0.18em] uppercase transition-colors",
                modeSwitchActivePillClass(option, active),
                !active && option === "REAL" && "text-slate-500/60 hover:text-slate-300/80",
                !active && option === "SIM" && "text-muted-foreground/70 hover:text-foreground",
              )}
            >
              {active ? (
                <motion.span
                  layoutId="mode-pill"
                  className={cn(
                    "absolute inset-0 rounded-md",
                    modeSwitchActivePillMotionClass(option),
                  )}
                  transition={pillMotion}
                />
              ) : null}
              <span className="relative z-[1]">{option}</span>
            </Button>
          );
        })}
      </motion.div>
      <span className="font-mono text-[9px] tracking-[0.14em] text-muted-foreground/70 uppercase">
        {modeSwitchTooltip(mode)}
      </span>
    </div>
  );
}

export function CommandHud({ className }: CommandHudProps) {
  const [realConfirmOpen, setRealConfirmOpen] = useState(false);
  const [safetyConfirmOpen, setSafetyConfirmOpen] = useState(false);
  const [realSafetyAck, setRealSafetyAck] = useState(false);
  const [pauseTradingAck, setPauseTradingAck] = useState(false);
  const runtime = useRuntimeStatusPoll();
  const [overflowOpen, setOverflowOpen] = useState(false);
  const [realTradingEligible, setRealTradingEligible] = useState(false);
  const [realTradingBlockers, setRealTradingBlockers] = useState<string[]>([]);
  const { transition, startTransition, completeTransition } = useDeckTransition();
  const prevRegimeRef = useRef<string | null>(null);

  const currentMode = useCoreStore(selectCurrentMode);
  const reportedMode = useCoreStore(selectReportedMode);
  const modeSyncStatus = useCoreStore(selectModeSyncStatus);
  const setOperatorMode = useCoreStore((state) => state.setOperatorMode);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);
  const botConfigDirty = useBotConfigStore((s) => s.isDirty);
  const saveBotConfig = useBotConfigStore((s) => s.save);
  const organismEnvelope = useOrganismEnvelope();
  const hudPrefs = useHudLayoutPrefsStore((s) => s.prefs);
  const hydrateHudPrefs = useHudLayoutPrefsStore((s) => s.hydrate);
  const openSettings = useSettingsDialogStore((s) => s.openSettings);
  const { metrics } = useAdaptiveIntelligenceContext();
  const setAnnexHint = useHudMetricsHintStore((s) => s.setAnnexHint);
  const pulseHint = useHudMetricsHintStore((s) => s.pulseHint);
  const metricsHintPulse = useHudMetricsHintStore((s) => s.pulse);

  const citadelInput = useCoreStore(
    useShallow((state) => ({
      liveMetrics: state.liveMetrics,
      riskLevel: state.riskLevel,
      fortress: state.fortress,
    })),
  );

  const walls = useMemo(
    () => deriveCitadelWallsFromInputs(citadelInput),
    [citadelInput],
  );
  const fortressIntegrity = useMemo(() => aggregateIntegrity(walls), [walls]);

  const equityIntensity = connectionVitality(connectionStatus, fallbackMode) * (0.88 + organismEnvelope * 0.12);
  const heroLayout = resolveHudHeroLayout(
    currentMode,
    {
      regime: liveMetrics.regime,
      regimeConfidence: liveMetrics.regimeConfidence,
      dailyPnlUsd: liveMetrics.dailyPnlUsd,
    },
    equityIntensity,
    hudPrefs,
    {
      connectionStatus,
      sessionActive: Boolean(metrics?.session_active),
      fallbackMode,
    },
  );

  useEffect(() => {
    if (heroLayout.showContextualAnnexHint && heroLayout.contextualKind !== "none") {
      setAnnexHint(true, heroLayout.contextualKind);
    } else {
      setAnnexHint(false, null);
    }
  }, [heroLayout.showContextualAnnexHint, heroLayout.contextualKind, setAnnexHint]);

  const heroReadout =
    heroLayout.heroPrimary === "equity"
      ? { label: "Equity", value: formatEquity(liveMetrics.equity) }
      : { label: "Fortress", value: `${Math.round(fortressIntegrity * 100)}%` };

  const equityCompact =
    heroLayout.heroPrimary === "fortress" ? formatEquityCompact(liveMetrics.equity) : undefined;

  const overflowItems = useMemo(
    () =>
      resolveOverflowItems({
        mode: currentMode,
        runtime,
        apiKeyConfigured,
      }),
    [currentMode, runtime, apiKeyConfigured],
  );

  useEffect(() => {
    return subscribeHudLayoutPrefs(() => hydrateHudPrefs());
  }, [hydrateHudPrefs]);

  useEffect(() => {
    if (!safetyConfirmOpen) {
      setRealSafetyAck(false);
      setPauseTradingAck(false);
    }
  }, [safetyConfirmOpen]);

  useEffect(() => {
    if (currentMode !== "SIM" || heroLayout.contextualKind !== "regime") {
      prevRegimeRef.current = liveMetrics.regime;
      return;
    }
    if (
      prevRegimeRef.current !== null &&
      prevRegimeRef.current !== liveMetrics.regime &&
      heroLayout.showContextualAnnexHint
    ) {
      pulseHint();
      const timer = window.setTimeout(() => {
        useHudMetricsHintStore.getState().clearPulse();
      }, 8000);
      prevRegimeRef.current = liveMetrics.regime;
      return () => window.clearTimeout(timer);
    }
    prevRegimeRef.current = liveMetrics.regime;
    return undefined;
  }, [
    currentMode,
    heroLayout.contextualKind,
    heroLayout.showContextualAnnexHint,
    liveMetrics.regime,
    pulseHint,
  ]);

  useEffect(() => {
    void fetchMaturationProgress()
      .then((payload) => {
        setRealTradingEligible(Boolean(payload.real_trading_eligible));
        setRealTradingBlockers(
          Array.isArray(payload.real_trading_blockers) ? payload.real_trading_blockers : [],
        );
      })
      .catch(() => {
        setRealTradingEligible(false);
        setRealTradingBlockers([]);
      });
  }, []);

  const handleModeSelect = (mode: TradingMode) => {
    if (mode === currentMode) {
      return;
    }
    if (mode === "REAL") {
      if (!realTradingEligible) {
        toast.error(
          "REAL blocked — complete Awakening (certificate + Evolution Proof) and later maturation phases.",
        );
        return;
      }
      setRealConfirmOpen(true);
      return;
    }
    startTransition({ kind: "modeSwitch", targetMode: mode });
    setOperatorMode(mode);
  };

  const confirmRealMode = () => {
    void postApproveReal()
      .then(() => {
        startTransition({ kind: "modeSwitch", targetMode: "REAL" });
        setOperatorMode("REAL");
        setRealConfirmOpen(false);
        if (!sessionStorage.getItem("lumina.realOpsHintShown")) {
          sessionStorage.setItem("lumina.realOpsHintShown", "1");
          toast.info("REAL Ops tab unlocked in Intelligence deck", {
            action: {
              label: "Open REAL Ops",
              onClick: () => useDeckPanelStore.getState().setActiveRightTab("realOps"),
            },
          });
        }
      })
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "REAL approval failed");
      });
  };

  const toggleEngine = () => {
    void (runtime?.alive
      ? stopEngine()
          .then((r) => {
            toast.success(r.message);
            void refreshRuntimeStatus();
          })
          .catch(handleRuntimeError)
      : startEngine()
          .then((r) => {
            toast.success(r.message);
            void refreshRuntimeStatus();
          })
          .catch(handleRuntimeError));
  };

  const saveAndStart = () => {
    void (async () => {
      if (botConfigDirty()) {
        const ok = await saveBotConfig();
        if (!ok) {
          toast.error("Save bot config before starting engine");
          return;
        }
        toast.success("Bot configuration saved");
      }
      return startEngine()
        .then((r) => {
          toast.success(r.message);
          void refreshRuntimeStatus();
        })
        .catch(handleRuntimeError);
    })();
  };

  const renderOverflowItem = (item: HudOverflowItem) => {
    switch (item.id) {
      case "trainingMonitor":
        return <TrainingMonitorTrigger key={item.id} className="w-full justify-start" />;
      case "botConfig":
        return <BotConfigurationDialog key={item.id} />;
      case "saveAndStart":
        return (
          <Button
            key={item.id}
            type="button"
            size="sm"
            variant="command-ghost"
            className="w-full justify-start"
            onClick={() => {
              saveAndStart();
              setOverflowOpen(false);
            }}
          >
            {item.label}
          </Button>
        );
      case "stopEngine":
        return (
          <Button
            key={item.id}
            type="button"
            size="sm"
            variant="command-ghost"
            className="w-full justify-start"
            onClick={() => {
              toggleEngine();
              setOverflowOpen(false);
            }}
          >
            {item.label}
          </Button>
        );
      case "safety":
        return (
          <Button
            key={item.id}
            type="button"
            size="sm"
            variant="command-ghost"
            className="w-full justify-start"
            onClick={() => {
              setSafetyConfirmOpen(true);
              setOverflowOpen(false);
            }}
          >
            {item.label}
          </Button>
        );
      case "launchNinja":
        return <LaunchNinjaTraderButton key={item.id} className="w-full justify-start" />;
      default:
        return null;
    }
  };

  const engineAlive = Boolean(runtime?.alive);

  const handleNerveActivate = () => {
    if (botConfigDirty()) {
      saveAndStart();
      return;
    }
    toggleEngine();
  };

  return (
    <>
      <header
        data-tour="command-hud"
        data-mode={currentMode}
        className={cn(
          "command-hud lumina-glass lumina-glass--hud relative z-10 shrink-0 border-b border-white/10",
          className,
        )}
      >
        <PresenceRail
          engineAlive={engineAlive}
          heroReadout={heroReadout}
          equityCompact={equityCompact}
        />
        <div className="flex flex-col gap-2.5 px-4 py-2.5 md:px-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="command-hud-metrics flex flex-wrap gap-3 md:flex-nowrap lg:flex-1 lg:justify-center">
            <HudOrganismCenter
              mode={currentMode}
              heroPrimary={heroLayout.heroPrimary}
              readout={heroReadout.value}
              readoutLabel={heroReadout.label}
              vitality={
                heroLayout.heroPrimary === "equity"
                  ? heroLayout.primary.kind === "equity"
                    ? heroLayout.primary.intensity
                    : 0.75
                  : fortressIntegrity
              }
              onActivate={() => useDeckPanelStore.getState().setActiveRightTab("performance")}
            />
            {heroLayout.showContextualAnnexHint && heroLayout.contextualKind !== "none" ? (
              <button
                type="button"
                className={cn(
                  "command-hud-annex-hint font-mono text-[9px] tracking-[0.14em] uppercase",
                  metricsHintPulse && "command-hud-annex-hint--pulse",
                )}
                onClick={() => useDeckPanelStore.getState().setActiveRightTab("performance")}
              >
                {resolveHudAnnexHintCopy(currentMode, heroLayout.contextualKind)}
              </button>
            ) : null}
          </div>

          <div className="flex items-center justify-end gap-2">
            <HudNerveTap
              mode={currentMode}
              engineAlive={engineAlive}
              apiKeyConfigured={apiKeyConfigured}
              configDirty={botConfigDirty()}
              menuOpen={overflowOpen}
              onActivate={handleNerveActivate}
              onToggleMenu={() => setOverflowOpen((open) => !open)}
              onMenuClose={() => setOverflowOpen(false)}
              menu={
                <div className="flex flex-col gap-1.5">
                  <Button
                    type="button"
                    size="sm"
                    variant="command-ghost"
                    className="w-full justify-start"
                    onClick={() => {
                      openSettings("apiKey");
                      setOverflowOpen(false);
                    }}
                  >
                    <Settings className="mr-2 size-3.5" />
                    Settings
                  </Button>
                  {overflowItems.map((item) => renderOverflowItem(item))}
                </div>
              }
            />
            <ModeSwitch
              mode={currentMode}
              reportedMode={reportedMode}
              syncStatus={modeSyncStatus}
              onSelect={handleModeSelect}
              realEligible={realTradingEligible}
            />
          </div>
        </div>
        <MaturityProgressStrip className="mt-2" />
      </header>

      <Dialog open={realConfirmOpen} onOpenChange={setRealConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className={realDialogTitleClass()}>Enable REAL Mode?</DialogTitle>
            <DialogDescription className={cn("leading-relaxed", realDialogBodyClass())}>
              {realTradingEligible ? (
                <>
                  REAL mode engages live capital protection: conservative sizing, fail-closed
                  safeguards, and EOD flatten rules. Confirm only after safety gate checks are
                  green and you accept capital risk.
                </>
              ) : (
                <>
                  REAL is blocked until maturation gates pass. Complete Playground → Apprenticeship
                  → Proving Ground first.
                  {realTradingBlockers.length > 0 ? (
                    <ul className="mt-2 list-inside list-disc text-xs">
                      {realTradingBlockers.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : null}
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="command-ghost" onClick={() => setRealConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="command-primary"
              disabled={!realTradingEligible}
              onClick={confirmRealMode}
            >
              Confirm REAL
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={safetyConfirmOpen} onOpenChange={setSafetyConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-red-200">Safety actions</DialogTitle>
            <DialogDescription>
              Flatten closes open positions. Emergency stop cancels orders and flattens all.
              {currentMode === "REAL" ? " These actions affect live capital." : null}
            </DialogDescription>
          </DialogHeader>
          {currentMode === "REAL" ? (
            <>
              <label className={cn("flex items-start gap-2 text-xs", realDialogBodyClass())}>
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={realSafetyAck}
                  onChange={(e) => setRealSafetyAck(e.target.checked)}
                />
                I understand this affects live capital
              </label>
              <label
                className={cn("flex items-start gap-2 text-xs", realDialogBodyClass())}
                title={helpFor("pause_live_trading")}
              >
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={pauseTradingAck}
                  onChange={(e) => setPauseTradingAck(e.target.checked)}
                />
                I want to pause live trading safely (flatten + stop engine)
              </label>
            </>
          ) : null}
          <DialogFooter className="flex-wrap gap-2">
            <Button type="button" variant="command-ghost" onClick={() => setSafetyConfirmOpen(false)}>
              Cancel
            </Button>
            {currentMode === "REAL" ? (
              <Button
                type="button"
                variant="command-ghost"
                disabled={!pauseTradingAck}
                onClick={() => {
                  void pauseTradingSafely()
                    .then((r) => {
                      toast.success(r.message);
                      void refreshRuntimeStatus();
                    })
                    .catch(handleRuntimeError);
                  setSafetyConfirmOpen(false);
                }}
              >
                Pause live trading
              </Button>
            ) : null}
            <Button
              type="button"
              variant="command-ghost"
              onClick={() => {
                void flattenPositions()
                  .then(() => toast.success("Positions flattened"))
                  .catch(handleRuntimeError);
                setSafetyConfirmOpen(false);
              }}
            >
              Flatten
            </Button>
            <Button
              type="button"
              variant="command-ghost"
              data-intent="danger"
              disabled={currentMode === "REAL" && !realSafetyAck}
              onClick={() => {
                void emergencyStop()
                  .then(() => toast.success("Emergency stop executed"))
                  .catch(handleRuntimeError);
                setSafetyConfirmOpen(false);
              }}
            >
              Emergency Stop
            </Button>
            <Button
              type="button"
              variant="command-ghost"
              data-intent="danger"
              disabled={currentMode === "REAL" && !realSafetyAck}
              onClick={() => {
                void stopAllActivities()
                  .then((r) => toast.success(r.message))
                  .catch(handleRuntimeError);
                setSafetyConfirmOpen(false);
              }}
            >
              Stop All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ModeTransitionVeil
        active={transition.active}
        targetMode={transition.targetMode}
        durationSec={transition.durationSec}
        scopeSelector={transition.scopeSelector}
        onComplete={completeTransition}
      />

      <SettingsDialog hideTrigger />
    </>
  );
}
