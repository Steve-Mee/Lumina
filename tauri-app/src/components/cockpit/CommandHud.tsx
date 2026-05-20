import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, MoreHorizontal, Settings } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useShallow } from "zustand/react/shallow";

import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { useOrganismEnvelope } from "@/context/OrganismEnvelopeContext";
import { BotConfigurationDialog } from "@/components/cockpit/BotConfigurationDialog";
import { HudSignal, HudSignalArc } from "@/components/cockpit/HudSignal";
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
import { useDeckStatusRail } from "@/hooks/useDeckStatusResolution";
import { useDeckTransition } from "@/hooks/useDeckTransition";
import { handleRuntimeError } from "@/lib/runtimeErrorToast";
import {
  modeSwitchTooltip,
  realDialogBodyClass,
  realDialogTitleClass,
} from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import { formatUsd } from "@/lib/tradingPerformanceModel";
import {
  aggregateIntegrity,
  deriveCitadelWallsFromInputs,
  integrityTier,
} from "@/lib/riskCitadelMetrics";
import {
  emergencyStop,
  fetchRuntimeStatus,
  flattenPositions,
  pauseTradingSafely,
  startEngine,
  stopAllActivities,
  stopEngine,
  type RuntimeStatus,
} from "@/lib/runtimeClient";
import { helpFor } from "@/lib/helpTexts";
import {
  menuPopWith,
  springHudSnappy,
  springLuxury,
  transitionOrNone,
} from "@/lib/motionPresets";
import {
  resolveHudHeroLayout,
} from "@/lib/hudSignalLayout";
import {
  resolveOverflowItems,
  type HudOverflowItem,
} from "@/lib/hudOverflowLayout";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
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

function DeckStatusRailChip({ kind }: { kind: "recovery" | "sync" | "fallback" }) {
  if (kind === "recovery") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/25 px-2 py-0.5 text-[9px] tracking-wide text-emerald-200/90 uppercase lumina-glass lumina-glass--overlay">
        <CheckCircle2 className="size-2.5 shrink-0" />
        Linked
      </span>
    );
  }
  if (kind === "sync") {
    return (
      <span className="rounded-full border border-amber-400/25 px-2 py-0.5 text-[9px] tracking-wide text-amber-200/90 uppercase">
        Syncing
      </span>
    );
  }
  return (
    <span className="rounded-full border border-amber-400/25 px-2 py-0.5 text-[9px] tracking-wide text-amber-200/80 uppercase">
      Polling
    </span>
  );
}

function ModeSwitch({
  mode,
  reportedMode,
  syncStatus,
  onSelect,
}: {
  mode: TradingMode;
  reportedMode: TradingMode | null;
  syncStatus: "idle" | "pending" | "error";
  onSelect: (mode: TradingMode) => void;
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
          mode === "SIM"
            ? "border-cyan-400/30 bg-cyan-950/40"
            : "border-slate-500/30 bg-slate-900/40",
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
              onClick={() => onSelect(option)}
              className={cn(
                "relative h-9 min-w-[64px] font-mono text-[11px] tracking-[0.18em] uppercase transition-colors",
                active && option === "SIM" && "text-cyan-200",
                active && option === "REAL" && "text-slate-200",
                !active && option === "REAL" && "text-slate-500/60 hover:text-slate-300/80",
                !active && option === "SIM" && "text-muted-foreground/70 hover:text-foreground",
              )}
            >
              {active ? (
                <motion.span
                  layoutId="mode-pill"
                  className={cn(
                    "absolute inset-0 rounded-md lumina-glow-edge",
                    option === "SIM"
                      ? "bg-cyan-500/20 ring-1 ring-cyan-400/40"
                      : "bg-slate-700/30 ring-1 ring-slate-400/30",
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
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [overflowOpen, setOverflowOpen] = useState(false);
  const { transition, startTransition, completeTransition } = useDeckTransition();
  const overflowRef = useRef<HTMLDivElement>(null);
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
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
  const { railChip } = useDeckStatusRail();
  const setAnnexHint = useHudMetricsHintStore((s) => s.setAnnexHint);
  const pulseHint = useHudMetricsHintStore((s) => s.pulseHint);

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
  const fortressTier = integrityTier(fortressIntegrity);

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
    if (!overflowOpen) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (overflowRef.current && !overflowRef.current.contains(event.target as Node)) {
        setOverflowOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [overflowOpen]);

  useEffect(() => {
    if (!safetyConfirmOpen) {
      setRealSafetyAck(false);
      setPauseTradingAck(false);
    }
  }, [safetyConfirmOpen]);

  useEffect(() => {
    const refresh = () => {
      void fetchRuntimeStatus()
        .then(setRuntime)
        .catch(() => setRuntime(null));
    };
    refresh();
    const id = window.setInterval(refresh, 5000);
    return () => window.clearInterval(id);
  }, []);

  const handleModeSelect = (mode: TradingMode) => {
    if (mode === currentMode) {
      return;
    }
    if (mode === "REAL") {
      setRealConfirmOpen(true);
      return;
    }
    startTransition({ kind: "modeSwitch", targetMode: mode });
    setOperatorMode(mode);
  };

  const confirmRealMode = () => {
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
  };

  const toggleEngine = () => {
    void (runtime?.alive
      ? stopEngine()
          .then((r) => {
            toast.success(r.message);
            setRuntime({ ...runtime!, alive: false, message: r.message });
          })
          .catch(handleRuntimeError)
      : startEngine()
          .then((r) => {
            toast.success(r.message);
            void fetchRuntimeStatus().then(setRuntime);
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
          void fetchRuntimeStatus().then(setRuntime);
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
  const statusChip = railChip ? <DeckStatusRailChip kind={railChip} /> : undefined;

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
          statusChip={statusChip}
          equityCompact={equityCompact}
          hideSyncSecondary={modeSyncStatus === "pending"}
        />
        <div className="flex flex-col gap-2.5 px-4 py-2.5 md:px-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="command-hud-metrics flex flex-wrap gap-3 md:flex-nowrap lg:flex-1 lg:justify-center">
            {heroLayout.primary.kind === "equity" ? (
              <HudSignal
                label="Equity"
                value={formatEquity(liveMetrics.equity)}
                glow={heroLayout.primary.glow}
                intensity={heroLayout.primary.intensity}
              />
            ) : (
              <HudSignalArc
                label="Fortress"
                integrity={fortressIntegrity}
                tier={fortressTier}
              />
            )}
            {heroLayout.secondary?.kind === "regime" ? (
              <HudSignal
                label="Regime"
                value={liveMetrics.regime}
                glow="violet"
                intensity={heroLayout.secondary.intensity}
                className={heroLayout.secondary.pulse ? "hud-signal--pulse" : undefined}
              />
            ) : null}
            {heroLayout.secondary?.kind === "pnl" ? (
              <HudSignal
                label="Daily P&L"
                value={formatUsd(liveMetrics.dailyPnlUsd)}
                glow={heroLayout.secondary.glow}
              />
            ) : null}
          </div>

          <div className="flex items-center justify-end gap-2">
            {!engineAlive ? (
              <Button
                type="button"
                size="xs"
                variant="command-primary"
                disabled={!apiKeyConfigured}
                title={
                  !apiKeyConfigured
                    ? "Configure admin API key in Settings to start the engine"
                    : undefined
                }
                onClick={toggleEngine}
              >
                Start Engine
              </Button>
            ) : (
              <div className="relative" ref={overflowRef}>
                <Button
                  type="button"
                  size="sm"
                  variant="command-ghost"
                  className="h-9 w-9 p-0"
                  aria-expanded={overflowOpen}
                  aria-label="More actions"
                  onClick={() => setOverflowOpen((open) => !open)}
                >
                  <MoreHorizontal className="size-4" />
                </Button>
                <AnimatePresence>
                  {overflowOpen ? (
                    <motion.div
                      key="hud-overflow"
                      className="deck-overflow-menu absolute right-0 top-full z-50 mt-1 w-56 rounded-lg p-2 lumina-glass lumina-glow-edge"
                      variants={menuPopWith(springHudSnappy)}
                      initial={reducedMotion ? false : "hidden"}
                      animate="visible"
                      exit={reducedMotion ? undefined : "exit"}
                      transition={transitionOrNone(reducedMotion, modeMotion)}
                    >
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
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </div>
            )}
            <ModeSwitch
              mode={currentMode}
              reportedMode={reportedMode}
              syncStatus={modeSyncStatus}
              onSelect={handleModeSelect}
            />
          </div>
        </div>
      </header>

      <Dialog open={realConfirmOpen} onOpenChange={setRealConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className={realDialogTitleClass()}>Enable REAL Mode?</DialogTitle>
            <DialogDescription className={cn("leading-relaxed", realDialogBodyClass())}>
              REAL mode engages live capital protection: conservative sizing, fail-closed
              safeguards, and EOD flatten rules. Confirm only after safety gate checks are
              green and you accept capital risk.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="command-ghost" onClick={() => setRealConfirmOpen(false)}>
              Cancel
            </Button>
            <Button type="button" variant="command-primary" onClick={confirmRealMode}>
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
                      void fetchRuntimeStatus().then(setRuntime);
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
