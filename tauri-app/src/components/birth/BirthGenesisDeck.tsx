import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, OctagonPause, RotateCcw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import {
  CharterTile,
  DataPolicyCard,
  RecoveryActionCard,
  RESUME_TIER_HINT,
  StatusChip,
} from "@/components/birth/BirthGenesisDeckPrimitives";
import { BirthGenesisStatusChips } from "@/components/birth/BirthGenesisStatusChips";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import {
  GenesisMaturityGoalsPreview,
} from "@/components/birth/GenesisMaturityLadder";
import { BirthTwinMicroHost } from "@/components/birth/BirthTwinMicroHost";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/ui/HelpTip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import {
  FOUNDATION_HISTORY_MAX_DAYS,
  FOUNDATION_HISTORY_START_DAYS,
  estimateFirstBootRealDays,
  historicalBarCapDays,
  isHighLoadEstimate,
} from "@/lib/firstBootSizing";
import { formatGenesisCheckpointSummary } from "@/lib/birthPhaseModel";
import {
  resolveGenesisDeckPresentation,
  sanitizeBirthOperatorMessage,
} from "@/lib/birthGenesisPresentation";
import { helpFor } from "@/lib/helpTexts";
import { cn } from "@/lib/utils";
import type { BirthStatusPayload, BirthWipeResult } from "@/lib/birthClient";
import { traceBirthWipe } from "@/lib/birthWipeTrace";
import { useBirthStore } from "@/store/birthStore";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { useBirthUiStore, type WipeConfirmKind } from "@/store/birthUiStore";

type GenesisDeckTab = "charter" | "data" | "recovery";

interface BirthGenesisDeckProps {
  training: OnboardingDraft["training"];
  activating: boolean;
  checkpointAvailable?: boolean;
  /** Prior birth stopped mid-run — surface recovery controls even without checkpoint_resumable. */
  sessionInterrupted?: boolean;
  /** Operator must choose Continue / Start clean (not Activate + wipe thrash). */
  decisionMode?: boolean;
  birthStatus?: BirthStatusPayload | null;
  busy?: boolean;
  engineLive?: boolean;
  error?: string | null;
  /** Birth store poll / residual engine error (merged into deck attention). */
  pollError?: string | null;
  /** First status poll done — false locks Activate during cold restart. */
  sessionHydrated?: boolean;
  sessionProbeState?: "pending" | "ready" | "error";
  sessionProbePending?: boolean;
  onChangeTraining: (training: Partial<OnboardingDraft["training"]>) => void;
  onActivate: () => void;
  onWipe?: () => Promise<BirthWipeResult>;
  onStop?: () => void | Promise<void>;
  onResumeCheckpoint?: () => void;
  onOpenSetup?: () => void;
  resumePlateauRisk?: boolean;
  resumePlateauRiskTrades?: number | null;
  className?: string;
}

export function BirthGenesisDeck({
  training,
  activating,
  checkpointAvailable = false,
  sessionInterrupted = false,
  decisionMode = false,
  birthStatus = null,
  busy = false,
  engineLive = false,
  error = null,
  pollError = null,
  sessionHydrated = true,
  sessionProbeState = "ready",
  sessionProbePending = false,
  onChangeTraining,
  onActivate,
  onWipe: _onWipe,
  onStop: _onStop,
  onResumeCheckpoint,
  onOpenSetup,
  resumePlateauRisk = false,
  resumePlateauRiskTrades = null,
  className,
}: BirthGenesisDeckProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [genesisTab, setGenesisTab] = useState<GenesisDeckTab>("charter");
  const [helixPrimed, setHelixPrimed] = useState(false);
  const [sequencing, setSequencing] = useState(false);
  const [probeRetrying, setProbeRetrying] = useState(false);
  const openWipeConfirm = useBirthUiStore((s) => s.openWipeConfirm);
  const openStopConfirm = useBirthUiStore((s) => s.openStopConfirm);
  const wipeConfirmWiping = useBirthUiStore((s) => s.wipeConfirmWiping);
  const sessionLocked = sessionProbePending || !sessionHydrated || sessionProbeState === "error";
  const disabled = activating || busy || sequencing || sessionLocked;
  const wipeBlocked = busy || activating || wipeConfirmWiping || sessionProbePending;
  const gatePct = Math.round((training.stage1_winrate_pass_threshold ?? 0.45) * 100);
  const estimatedDays = estimateFirstBootRealDays(training.training_trades);
  const barCapDays = historicalBarCapDays();
  const historyLabel = `Foundation ${FOUNDATION_HISTORY_START_DAYS}d · expand 180/${FOUNDATION_HISTORY_MAX_DAYS}`;
  const checkpointSummary = checkpointAvailable
    ? formatGenesisCheckpointSummary(birthStatus)
    : null;
  const resumeTier = String(birthStatus?.progress?.resume_cache_tier ?? "").trim().toUpperCase();
  const resumeTierHint = RESUME_TIER_HINT[resumeTier] ?? null;

  const loadHints: string[] = [];
  if (isHighLoadEstimate(estimatedDays)) {
    loadHints.push(
      `Large trade budget (~${estimatedDays.toLocaleString()} estimated session-days at 450 trades/day) — longer wall-clock, not extra unique tape.`,
    );
  }
  if (FOUNDATION_HISTORY_MAX_DAYS > barCapDays && training.prefer_real_data_only) {
    loadHints.push(
      `365d expand is calendar SLA; 1-minute bar fetch still caps at ~${barCapDays.toLocaleString()} days.`,
    );
  }

  const summaryLine = [
    `${training.training_trades.toLocaleString()} trades`,
    `Gate ${gatePct}%`,
    historyLabel,
    training.prefer_real_data_only ? "Real data" : "Mixed data",
  ].join(" · ");

  const presentation = resolveGenesisDeckPresentation({
    activating,
    sessionInterrupted,
    checkpointAvailable,
    resumePlateauRisk,
    decisionMode,
    sessionProbePending,
    sessionProbeError: sessionProbeState === "error",
    engineLive,
    error,
    pollError,
    statusMessage: birthStatus?.message ?? birthStatus?.progress?.message ?? null,
    statusError: birthStatus?.error ?? null,
  });

  // Recovery SSOT from presentation — never after clean post-wipe idle.
  const showRecoveryTab = presentation.showRecoveryTab;
  const decisionSurface =
    presentation.ctaMode === "decision" || presentation.preferRecoveryTab;

  // Land on Recovery when birth needs a decision / failed (not Charter frontpage).
  useEffect(() => {
    if (!showRecoveryTab) {
      if (genesisTab === "recovery") setGenesisTab("charter");
      return;
    }
    if (presentation.preferRecoveryTab) {
      setGenesisTab("recovery");
    }
  }, [showRecoveryTab, presentation.preferRecoveryTab]); // eslint-disable-line react-hooks/exhaustive-deps -- intentional land once per decision edge

  const recoveryOperator = sanitizeBirthOperatorMessage(
    String(error ?? "").trim() ||
      String(pollError ?? "").trim() ||
      String(birthStatus?.error ?? "").trim() ||
      String(birthStatus?.message ?? birthStatus?.progress?.message ?? "").trim() ||
      "",
  );

  const openStartClean = (source: string = "recovery_tab") => {
    const kind: WipeConfirmKind = "reset";
    traceBirthWipe("ui.wipe_button.click", {
      mode: "genesis",
      kind,
      busy,
      activating,
      wiping: wipeConfirmWiping,
      source,
    });
    if (wipeBlocked) {
      toast.info(
        wipeConfirmWiping
          ? "Wipe already in progress…"
          : activating
            ? "Birth is starting — wipe afterward."
            : "Please wait — another birth action is in progress.",
      );
      return;
    }
    openWipeConfirm(kind);
  };

  return (
    <div
      className={cn(
        "birth-genesis-panel__layout flex min-h-0 flex-1 flex-col overflow-hidden",
        className,
      )}
    >
      <div className="risk-envelope-panel__toolbar shrink-0">
        <div className="min-w-0">
          <div className="birth-genesis-title-row">
            <p className="risk-envelope-panel__toolbar-title">Neural Genesis</p>
            <HelpTip
              className="birth-genesis-title-help"
              label="Neural Genesis info"
              text={
                helpFor("genesis_maturity_charter") ??
                "Sign the pre-birth contract. Training size is auto-sized. Birth pass is process-R, not a WR exam."
              }
            />
          </div>
          <p className="mt-0.5 font-mono text-[0.5rem] tracking-wide text-white/30 uppercase">
            {presentation.toolbarSubtitle}
          </p>
        </div>
        {/* Twin train occupies the former HelpTip slot — tighter toolbar composition */}
        <BirthTwinMicroHost variant="genesis-toolbar" />
      </div>

      <div
        className="risk-envelope-status-strip shrink-0"
        role="status"
        aria-label="Genesis status"
      >
        <StatusChip
          label="CHARTER"
          state="ok"
          tip="Auto charter ready — training trades are system-derived. Pass is process-R, not WR."
        />
        <StatusChip
          label="DATA"
          state={training.prefer_real_data_only ? "ok" : "partial"}
          tip={
            training.prefer_real_data_only
              ? "Prefer real market data for certified birth."
              : "Mixed / synthetic paths allowed — practice only if real data is short."
          }
        />
        <StatusChip
          label="HISTORY"
          state={isHighLoadEstimate(estimatedDays) ? "warn" : "ok"}
          tip={`Foundation ${FOUNDATION_HISTORY_START_DAYS}d start · expand 180/${FOUNDATION_HISTORY_MAX_DAYS}. Not linked to training trades.`}
        />
        <StatusChip
          label="BIRTH"
          state={presentation.birthChipState}
          tip={
            engineLive
              ? "Birth engine is running in the background — stop before wipe. Does not block re-entry to Genesis."
              : presentation.birthChipState === "warn"
                ? "Birth needs attention — use the actions below. This chip is status only."
                : "Birth engine idle — safe to activate. This chip is status only; it does not gate Activate Birth."
          }
        />
      </div>

      {/* Charter/Data banner only — Recovery tab owns its own decision story (no dual narrative). */}
      {genesisTab !== "recovery" ? (
        <div
          className={cn(
            "risk-envelope-banner mx-2 mt-2 shrink-0",
            presentation.banner.tone === "warn"
              ? "risk-envelope-banner--warn"
              : "risk-envelope-banner--info",
          )}
          role={presentation.banner.tone === "warn" ? "alert" : "status"}
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="min-w-0 flex-1 text-[11px] leading-relaxed">
              <strong
                className={
                  presentation.banner.tone === "warn"
                    ? "text-amber-100/95"
                    : "text-cyan-200/90"
                }
              >
                {presentation.banner.title}
              </strong>{" "}
              {presentation.banner.body}
            </p>
            {sessionProbePending || sessionProbeState === "error" ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="shrink-0 font-mono text-[10px] tracking-wide uppercase"
                disabled={probeRetrying}
                onClick={() => {
                  setProbeRetrying(true);
                  void useBirthStore
                    .getState()
                    .pollFresh()
                    .finally(() => setProbeRetrying(false));
                }}
              >
                {probeRetrying || sessionProbePending ? (
                  <Loader2 className="mr-1.5 size-3.5 animate-spin" aria-hidden />
                ) : null}
                {probeRetrying ? "Retrying…" : sessionProbePending ? "Loading…" : "Retry status"}
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {presentation.detail && genesisTab !== "recovery" ? (
        <div
          className="birth-distress-callout mx-2 mt-2 shrink-0 rounded-lg px-3 py-2"
          role="status"
        >
          <p className="birth-distress-callout__body text-[11px] leading-relaxed">
            {presentation.detail.operatorLine}
          </p>
          {presentation.detail.technicalLine ? (
            <p
              className="mt-1 font-mono text-[9px] leading-snug text-white/35"
              title={presentation.detail.technicalLine}
            >
              Detail: {presentation.detail.technicalLine}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="birth-genesis-panel__body min-h-0 flex-1 overflow-hidden px-2 pt-2">
        <Tabs
          value={showRecoveryTab ? genesisTab : genesisTab === "recovery" ? "charter" : genesisTab}
          onValueChange={(value) => setGenesisTab(value as GenesisDeckTab)}
          className="risk-envelope-tabs flex min-h-0 flex-1 flex-col"
        >
          <TabsList
            className={cn(
              "risk-envelope-tab-list",
              showRecoveryTab ? "risk-envelope-tab-list--3" : "risk-envelope-tab-list--2",
            )}
            aria-label="Genesis charter sections"
          >
            <TabsTrigger value="charter">Charter</TabsTrigger>
            <TabsTrigger value="data">Data</TabsTrigger>
            {showRecoveryTab ? <TabsTrigger value="recovery">Recovery</TabsTrigger> : null}
          </TabsList>

          <div className="risk-envelope-tab-body">
            <TabsContent value="charter" className="risk-envelope-tab-content">
              <motion.div
                initial={reducedMotion ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.35 }}
                className="space-y-3"
              >
                {/* Evolution ladder lives in OnboardingShell chrome (red thread). */}

                <div className="genesis-charter-tile-grid">
                  <CharterTile
                    label="Training trades"
                    value={training.training_trades.toLocaleString()}
                    tip={
                      helpFor("training_trades") ??
                      "Curriculum trade budget auto-sized for this machine (hardware / first-boot)."
                    }
                    footnote="System-derived · not operator-editable"
                  />
                  <CharterTile
                    label="Foundation exam"
                    value="1/5 plant"
                    tip={
                      helpFor("stage1_winrate_gate") ??
                      "Birth grades process-R and occupancy. Certificate OOS ≥48% is Proving Ground."
                    }
                    footnote="Not a WR 35–45% pass · not REAL"
                  />
                  <CharterTile
                    label="Historical window"
                    value={historyLabel}
                    tip={
                      helpFor("max_real_days") ??
                      "Foundation start 90 calendar days; expand 180 then 365. Trade budget is a cap, not a history sizer."
                    }
                    footnote="Start 90d · not auto-linked to trades"
                  />
                </div>

                {loadHints.length > 0 ? (
                  <div className="risk-envelope-field-card">
                    <p className="risk-envelope-field-label">Load notes</p>
                    <ul className="mt-1 space-y-1 text-[11px] text-muted-foreground">
                      {loadHints.map((hint) => (
                        <li key={hint}>· {hint}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <GenesisMaturityGoalsPreview />
              </motion.div>
            </TabsContent>

            <TabsContent value="data" className="risk-envelope-tab-content">
              <p className="mb-3 text-center text-[11px] leading-relaxed text-muted-foreground">
                Data policy for historical curriculum. Prefer real market data for a certifiable
                birth. These toggles do not change live capital risk.
              </p>

              <div className="genesis-data-policy-grid">
                <DataPolicyCard
                  label="Real data only"
                  tip={helpFor("prefer_real_data_only")}
                  hint="Certified birth needs ≥95% real market data coverage."
                  controlLabel="Prefer real data"
                  checked={training.prefer_real_data_only}
                  disabled={disabled}
                  onChange={(prefer_real_data_only) =>
                    onChangeTraining({ prefer_real_data_only })
                  }
                />
                <DataPolicyCard
                  label="Synthetic fallback"
                  tip={helpFor("allow_minimal_synthetic_fallback")}
                  hint="Practice top-up only when real data is short."
                  controlLabel="Allow synthetic top-up"
                  checked={training.allow_minimal_synthetic_fallback}
                  disabled={disabled}
                  onChange={(allow_minimal_synthetic_fallback) =>
                    onChangeTraining({ allow_minimal_synthetic_fallback })
                  }
                />
                <DataPolicyCard
                  label="Simulator data"
                  tip={helpFor("require_real_simulator_data")}
                  hint="Require NT / CrossTrade simulator history first."
                  controlLabel="Require simulator data"
                  checked={training.require_real_simulator_data}
                  disabled={disabled}
                  onChange={(require_real_simulator_data) =>
                    onChangeTraining({ require_real_simulator_data })
                  }
                />
              </div>

              <p className="mt-3 text-center font-mono text-[0.55rem] tracking-wide text-white/30 uppercase">
                Charter snapshot · {summaryLine}
              </p>
            </TabsContent>

            {showRecoveryTab ? (
              <TabsContent value="recovery" className="risk-envelope-tab-content">
                <motion.div
                  initial={reducedMotion ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3 }}
                  className="genesis-recovery-surface space-y-3"
                >
                  <div
                    className={cn(
                      "risk-envelope-banner shrink-0",
                      decisionSurface || presentation.hasAttention
                        ? "risk-envelope-banner--warn"
                        : "risk-envelope-banner--info",
                    )}
                    role={decisionSurface || presentation.hasAttention ? "alert" : "status"}
                  >
                    <p className="text-[11px] leading-relaxed">
                      <strong
                        className={
                          decisionSurface || presentation.hasAttention
                            ? "text-amber-100/95"
                            : "text-cyan-200/90"
                        }
                      >
                        {checkpointAvailable
                          ? "Checkpoint ready — choose one path:"
                          : presentation.hasAttention
                            ? "Recovery required:"
                            : "Recovery tools:"}
                      </strong>{" "}
                      {checkpointAvailable
                        ? "Continue resumes training. Start clean clears curriculum (tick cache kept). Full wipe also drops tick cache."
                        : presentation.hasAttention
                          ? "Start clean or Full wipe below. Retry activation from the footer when the issue is clear."
                          : "Start clean clears curriculum. Full wipe includes tick cache. Stop engine if the host is still live."}
                    </p>
                  </div>

                  {recoveryOperator.operator ? (
                    <div
                      className="birth-distress-callout shrink-0 rounded-lg px-3 py-2"
                      role="status"
                    >
                      <p className="birth-distress-callout__body text-[11px] leading-relaxed">
                        {recoveryOperator.operator}
                      </p>
                      {recoveryOperator.technical ? (
                        <p
                          className="mt-1 font-mono text-[9px] leading-snug text-white/35"
                          title={recoveryOperator.technical}
                        >
                          Detail: {recoveryOperator.technical}
                        </p>
                      ) : null}
                    </div>
                  ) : null}

                  <BirthGenesisStatusChips
                    engineLive={engineLive}
                    resumePlateauRisk={resumePlateauRisk}
                    resumePlateauRiskTrades={resumePlateauRiskTrades}
                    checkpointAvailable={checkpointAvailable}
                    checkpointSummary={checkpointSummary}
                    resumeTierHint={resumeTierHint}
                    className="justify-center"
                  />

                  {/* One equal glass row — Continue · Start clean · Full wipe (+ Stop when live). */}
                  <div
                    className={cn(
                      "genesis-recovery-action-grid",
                      checkpointAvailable && engineLive && "genesis-recovery-action-grid--4",
                      checkpointAvailable && !engineLive && "genesis-recovery-action-grid--3",
                      !checkpointAvailable && engineLive && "genesis-recovery-action-grid--3",
                      !checkpointAvailable && !engineLive && "genesis-recovery-action-grid--2",
                    )}
                  >
                    {checkpointAvailable ? (
                      <RecoveryActionCard
                        label="Continue"
                        tip="Resume training from the last resumable checkpoint. Curriculum and stage progress are preserved."
                        hint={
                          checkpointSummary
                            ? checkpointSummary
                            : "Resumes last checkpoint · preferred path"
                        }
                        tone="accent"
                      >
                        <button
                          type="button"
                          className={cn(
                            "genesis-recovery-action-card__btn genesis-recovery-action-card__btn--accent",
                            (busy || wipeBlocked) && "cursor-not-allowed opacity-70",
                          )}
                          disabled={busy || wipeBlocked}
                          onClick={() => {
                            if (busy) {
                              toast.info("Please wait — another birth action is in progress.");
                              return;
                            }
                            onResumeCheckpoint?.();
                          }}
                        >
                          <RotateCcw className="size-3.5 shrink-0" aria-hidden />
                          <span>Continue</span>
                        </button>
                      </RecoveryActionCard>
                    ) : null}

                    <RecoveryActionCard
                      label="Start clean"
                      tip="Clear birth curriculum and start a new run. Tick cache is kept by default for faster reload."
                      hint="Tick cache kept · faster reload"
                      tone="warn"
                    >
                      <button
                        type="button"
                        className={cn(
                          "genesis-recovery-action-card__btn genesis-recovery-action-card__btn--warn",
                          wipeBlocked && "cursor-not-allowed opacity-70",
                        )}
                        disabled={wipeBlocked}
                        aria-busy={wipeConfirmWiping}
                        onClick={() => openStartClean("recovery_primary")}
                      >
                        {wipeConfirmWiping ? (
                          <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden />
                        ) : (
                          <Trash2 className="size-3.5 shrink-0" aria-hidden />
                        )}
                        <span>Start clean</span>
                      </button>
                    </RecoveryActionCard>

                    <RecoveryActionCard
                      label="Full wipe"
                      tip="Permanent removal of all birth artifacts including tick cache and enrichment. Use only for a hard clean start."
                      hint="Includes tick cache · two-step confirm"
                      tone="danger"
                    >
                      <button
                        type="button"
                        className={cn(
                          "genesis-recovery-action-card__btn genesis-recovery-action-card__btn--danger",
                          wipeBlocked && "cursor-not-allowed opacity-70",
                        )}
                        disabled={wipeBlocked}
                        aria-busy={wipeConfirmWiping}
                        onClick={() => {
                          const kind: WipeConfirmKind = "full";
                          traceBirthWipe("ui.wipe_button.click", {
                            mode: "genesis",
                            kind,
                            busy,
                            activating,
                            wiping: wipeConfirmWiping,
                            source: "recovery_tab_full",
                          });
                          if (wipeBlocked) {
                            toast.info(
                              wipeConfirmWiping
                                ? "Wipe already in progress…"
                                : activating
                                  ? "Birth is starting — wipe afterward."
                                  : "Please wait — another birth action is in progress.",
                            );
                            return;
                          }
                          openWipeConfirm(kind);
                        }}
                      >
                        {wipeConfirmWiping ? (
                          <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden />
                        ) : (
                          <Trash2 className="size-3.5 shrink-0" aria-hidden />
                        )}
                        <span>Full wipe</span>
                      </button>
                    </RecoveryActionCard>

                    {engineLive ? (
                      <RecoveryActionCard
                        label="Stop engine"
                        tip="Stop the live birth engine. Checkpoint is kept when possible."
                        hint="Engine still running"
                        tone="danger"
                      >
                        <button
                          type="button"
                          className={cn(
                            "genesis-recovery-action-card__btn genesis-recovery-action-card__btn--danger",
                            busy && "cursor-not-allowed opacity-70",
                          )}
                          disabled={busy}
                          onClick={() => {
                            if (busy) {
                              toast.info("Please wait — another birth action is in progress.");
                              return;
                            }
                            openStopConfirm();
                          }}
                        >
                          <OctagonPause className="size-3.5 shrink-0" aria-hidden />
                          <span>Stop birth</span>
                        </button>
                      </RecoveryActionCard>
                    ) : null}
                  </div>

                  <p className="text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
                    One decision · full wipe always opens a two-step safety dialog
                  </p>
                </motion.div>
              </TabsContent>
            ) : null}
          </div>
        </Tabs>
      </div>

      {/* Footer: Activate/Retry only. Decision CTAs live under Recovery tab (no Go-to-Recovery thrash). */}
      <div className="risk-envelope-cta-bar genesis-launch-cta shrink-0">
        {onOpenSetup ? (
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="onboarding-btn-secondary lumina-interactive rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
              onClick={onOpenSetup}
              disabled={disabled}
            >
              Setup & connection
            </button>
          </div>
        ) : null}

        {presentation.ctaMode === "decision" ||
        (presentation.preferRecoveryTab && presentation.ctaMode !== "retry") ? (
          <p className="text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
            {genesisTab === "recovery"
              ? "Continue or Start clean above · Charter / Data stay available"
              : "Open the Recovery tab for Continue or Start clean"}
          </p>
        ) : (
          <div className="flex w-full flex-col gap-2">
            <p className="mb-0 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
              {presentation.ctaHint}
            </p>
            <BirthLaunchButton
              activating={activating}
              primed={helixPrimed}
              disabled={busy || sessionLocked || presentation.ctaMode === "locked"}
              waitingSession={sessionLocked || presentation.ctaMode === "locked"}
              idleLabel={
                presentation.ctaMode === "retry" ? "RETRY BIRTH" : "ACTIVATE BIRTH"
              }
              onClick={onActivate}
              onPrimedChange={setHelixPrimed}
              onSequencingChange={setSequencing}
              className="w-full"
            />
            {presentation.showStartCleanSecondary && presentation.ctaMode === "retry" ? (
              <div className="genesis-launch-secondary mt-1 flex w-full flex-col gap-2 border-t border-white/5 pt-3">
                <button
                  type="button"
                  className={cn(
                    "genesis-recovery-primary-btn genesis-recovery-secondary-btn w-full rounded-md font-mono text-xs tracking-wide uppercase",
                    wipeBlocked && "cursor-not-allowed opacity-70",
                  )}
                  disabled={wipeBlocked}
                  aria-busy={wipeConfirmWiping}
                  onClick={() => openStartClean("retry_secondary")}
                >
                  {wipeConfirmWiping ? (
                    <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
                  ) : (
                    <Trash2 className="size-4 shrink-0" aria-hidden />
                  )}
                  <span>Start clean</span>
                </button>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
