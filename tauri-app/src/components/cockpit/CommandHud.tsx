import { useEffect, useMemo, useRef, useState } from "react";
import { Settings } from "lucide-react";
import { useShallow } from "zustand/react/shallow";

import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { useOrganismEnvelope } from "@/context/OrganismEnvelopeContext";
import { BotConfigurationDialog } from "@/components/cockpit/BotConfigurationDialog";
import { HudOrganismCenter } from "@/components/cockpit/HudOrganismCenter";
import { HudNerveTap } from "@/components/cockpit/HudNerveTap";
import { LaunchNinjaTraderButton } from "@/components/cockpit/LaunchNinjaTraderButton";
import { ModeSwitch } from "@/components/cockpit/ModeSwitch";
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
import { useCommandHudActions } from "@/hooks/useCommandHudActions";
import { useDeckTransition } from "@/hooks/useDeckTransition";
import { realDialogBodyClass, realDialogTitleClass } from "@/lib/modePresentation";
import { helpFor } from "@/lib/helpTexts";
import { cn } from "@/lib/utils";
import {
  aggregateIntegrity,
  deriveCitadelWallsFromInputs,
} from "@/lib/riskCitadelMetrics";
import { useRuntimeStatusPoll } from "@/hooks/useRuntimeStatusPoll";

import { fetchMaturationProgress } from "@/lib/maturationClient";
import { MaturityProgressStrip } from "@/components/cockpit/MaturityProgressStrip";

import {
  resolveHudAnnexHintCopy,
  resolveHudHeroLayout,
} from "@/lib/hudSignalLayout";
import {
  resolveOverflowItems,
  type HudOverflowItem,
} from "@/lib/hudOverflowLayout";

import {
  selectConnectionStatus,
  selectCurrentMode,
  selectFallbackMode,
  selectLiveMetrics,
  selectModeSyncStatus,
  selectReportedMode,
  useCoreStore,
  type ConnectionStatus,
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

export function CommandHud({ className }: CommandHudProps) {
  const [realConfirmOpen, setRealConfirmOpen] = useState(false);
  const [safetyConfirmOpen, setSafetyConfirmOpen] = useState(false);
  const [realSafetyAck, setRealSafetyAck] = useState(false);
  const [pauseTradingAck, setPauseTradingAck] = useState(false);
  const runtime = useRuntimeStatusPoll();
  const [overflowOpen, setOverflowOpen] = useState(false);
  const [realTradingEligible, setRealTradingEligible] = useState(false);
  const [realTradingBlockers, setRealTradingBlockers] = useState<string[]>([]);
  const { transition, completeTransition } = useDeckTransition();
  const prevRegimeRef = useRef<string | null>(null);

  const currentMode = useCoreStore(selectCurrentMode);
  const reportedMode = useCoreStore(selectReportedMode);
  const modeSyncStatus = useCoreStore(selectModeSyncStatus);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);
  const botConfigDirty = useBotConfigStore((s) => s.isDirty);
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

  const engineAlive = Boolean(runtime?.alive);
  const {
    handleModeSelect,
    confirmRealMode,
    toggleEngine,
    saveAndStart,
    handleNerveActivate,
    pauseLiveTrading,
    flatten,
    emergencyStopAction,
    stopAll,
  } = useCommandHudActions({
    currentMode,
    runtimeAlive: engineAlive,
    realTradingEligible,
    onRealConfirmOpen: () => setRealConfirmOpen(true),
    onRealConfirmed: () => setRealConfirmOpen(false),
  });

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
                  pauseLiveTrading();
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
                flatten();
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
                emergencyStopAction();
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
                stopAll();
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
