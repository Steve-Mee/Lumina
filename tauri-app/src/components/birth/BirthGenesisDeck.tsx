import { useEffect, useRef, useState, type ReactNode } from "react";
import { motion } from "framer-motion";
import { Loader2, OctagonPause, RotateCcw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { BirthGenesisStatusChips } from "@/components/birth/BirthGenesisStatusChips";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import {
  GenesisMaturityGoalsPreview,
} from "@/components/birth/GenesisMaturityLadder";
import { Button } from "@/components/ui/button";
import { HelpTip } from "@/components/ui/HelpTip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import {
  historicalBarCapDays,
  isHighLoadEstimate,
  linkMaxRealDaysToTrainingTrades,
  resolveDefaultMaxRealDays,
} from "@/lib/firstBootSizing";
import { formatGenesisCheckpointSummary } from "@/lib/birthPhaseModel";
import { helpFor } from "@/lib/helpTexts";
import { luminaInteractiveClass } from "@/lib/glassGlowTaxonomy";
import { distressPanelClass, warnOverlayBodyClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import type { BirthStatusPayload, BirthWipeResult } from "@/lib/birthClient";
import { traceBirthWipe } from "@/lib/birthWipeTrace";
import { useBirthStore } from "@/store/birthStore";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { useBirthUiStore, type WipeConfirmKind } from "@/store/birthUiStore";

type GenesisDeckTab = "charter" | "data" | "recovery";

const RESUME_TIER_HINT: Record<string, string> = {
  T0: "Latest cache loaded directly.",
  T1: "Checkpoint manifest restored from cache.",
  T2: "Regime map recomputed (algo update); curriculum intact.",
  T3: "Data re-prepared; curriculum intact.",
  T4: "New market data — holdout recomputed; curriculum intact.",
};

interface BirthGenesisDeckProps {
  training: OnboardingDraft["training"];
  activating: boolean;
  checkpointAvailable?: boolean;
  /** Prior birth stopped mid-run — surface recovery controls even without checkpoint_resumable. */
  sessionInterrupted?: boolean;
  birthStatus?: BirthStatusPayload | null;
  busy?: boolean;
  engineLive?: boolean;
  error?: string | null;
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

function StatusChip({
  label,
  state,
  tip,
}: {
  label: string;
  state: "ok" | "partial" | "warn" | "idle";
  tip: string;
}) {
  return (
    <span
      className="risk-envelope-status-chip"
      data-state={state === "idle" ? undefined : state}
      title={tip}
    >
      <span className="risk-envelope-status-chip__dot" />
      {label}
    </span>
  );
}

function RecoveryActionCard({
  label,
  tip,
  hint,
  tone = "default",
  children,
}: {
  label: string;
  tip?: string;
  hint: string;
  tone?: "default" | "accent" | "warn" | "danger";
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "risk-envelope-field-card genesis-recovery-action-card h-full",
        tone === "accent" && "genesis-recovery-action-card--accent",
        tone === "warn" && "genesis-recovery-action-card--warn",
        tone === "danger" && "genesis-recovery-action-card--danger",
      )}
    >
      <div className="mb-2 flex items-center justify-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      <div className="genesis-recovery-action-card__body">{children}</div>
      <p className="risk-envelope-field-hint mt-auto pt-2 text-center">{hint}</p>
    </div>
  );
}

function CharterTile({
  label,
  value,
  tip,
  footnote,
}: {
  label: string;
  value: string;
  tip: string;
  footnote: string;
}) {
  return (
    <div className="risk-envelope-field-card genesis-charter-tile genesis-charter-tile--centered flex h-full flex-col items-center text-center">
      <div className="mb-1 flex items-center justify-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        <HelpTip text={tip} />
      </div>
      <p className="font-mono text-lg tabular-nums tracking-tight text-cyan-100 sm:text-xl">
        {value}
      </p>
      <p className="risk-envelope-field-hint mt-auto w-full pt-1 text-center">{footnote}</p>
    </div>
  );
}

function DataPolicyCard({
  label,
  tip,
  hint,
  checked,
  disabled,
  onChange,
  controlLabel,
}: {
  label: string;
  tip?: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  controlLabel: string;
}) {
  return (
    <div className="risk-envelope-field-card genesis-data-policy-card h-full">
      <div className="mb-2 flex items-center justify-center gap-1.5">
        <p className="risk-envelope-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      <label className="genesis-data-policy-card__control">
        <input
          type="checkbox"
          className="size-4 shrink-0 accent-cyan-400"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="text-sm font-medium text-foreground/90">{controlLabel}</span>
      </label>
      <p className="risk-envelope-field-hint mt-auto pt-2 text-center">{hint}</p>
    </div>
  );
}

export function BirthGenesisDeck({
  training,
  activating,
  checkpointAvailable = false,
  sessionInterrupted = false,
  birthStatus = null,
  busy = false,
  engineLive = false,
  error = null,
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
  const estimatedDays = resolveDefaultMaxRealDays(training.training_trades);
  const barCapDays = historicalBarCapDays();
  const linkedDays = linkMaxRealDaysToTrainingTrades(training.training_trades);
  const checkpointSummary = checkpointAvailable
    ? formatGenesisCheckpointSummary(birthStatus)
    : null;
  const resumeTier = String(birthStatus?.progress?.resume_cache_tier ?? "").trim().toUpperCase();
  const resumeTierHint = RESUME_TIER_HINT[resumeTier] ?? null;

  const loadHints: string[] = [];
  if (isHighLoadEstimate(estimatedDays)) {
    loadHints.push(
      `Large trade target (~${estimatedDays.toLocaleString()} days of history) — longer load and higher hardware load.`,
    );
  }
  if (estimatedDays > barCapDays && training.prefer_real_data_only) {
    loadHints.push(
      `Bar fetch capped at ~${barCapDays.toLocaleString()} days; synthetic top-up may apply.`,
    );
  }

  const migratedRef = useRef(false);
  useEffect(() => {
    if (migratedRef.current) return;
    migratedRef.current = true;
    if (training.max_real_days !== linkedDays) {
      onChangeTraining({ max_real_days: linkedDays });
    }
    // One-time auto-link of historical window to system trade target.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const summaryLine = [
    `${training.training_trades.toLocaleString()} trades`,
    `Gate ${gatePct}%`,
    `~${linkedDays}d history`,
    training.prefer_real_data_only ? "Real data" : "Mixed data",
  ].join(" · ");

  // Recovery context: interrupted runs often lack checkpoint_resumable but still need wipe/resume UX.
  // During cold probe, surface Recovery so operators see that prior-session options are coming.
  const showRecoveryTab =
    checkpointAvailable ||
    resumePlateauRisk ||
    engineLive ||
    sessionInterrupted ||
    sessionProbePending;

  // Open Recovery when operator lands on interrupted / checkpoint surface.
  const recoveryAutoOpenRef = useRef(false);
  useEffect(() => {
    if (recoveryAutoOpenRef.current) return;
    if (
      showRecoveryTab &&
      (sessionInterrupted || checkpointAvailable || resumePlateauRisk || sessionProbePending)
    ) {
      recoveryAutoOpenRef.current = true;
      setGenesisTab("recovery");
    }
  }, [
    showRecoveryTab,
    sessionInterrupted,
    checkpointAvailable,
    resumePlateauRisk,
    sessionProbePending,
  ]);

  return (
    <div
      className={cn(
        "birth-genesis-panel__layout flex min-h-0 flex-1 flex-col overflow-hidden",
        className,
      )}
    >
      <div className="risk-envelope-panel__toolbar shrink-0">
        <div className="min-w-0">
          <p className="risk-envelope-panel__toolbar-title">Neural Genesis</p>
          <p className="mt-0.5 font-mono text-[0.5rem] tracking-wide text-white/30 uppercase">
            Maturity charter · awaiting activation
          </p>
        </div>
        <HelpTip
          text={
            helpFor("genesis_maturity_charter") ??
            "Sign the pre-birth contract. Training size and winrate gate are auto-sized for this machine."
          }
        />
      </div>

      <div
        className="risk-envelope-status-strip shrink-0"
        role="status"
        aria-label="Genesis status"
      >
        <StatusChip
          label="CHARTER"
          state="ok"
          tip="Auto charter ready — training trades and winrate gate are system-derived."
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
          tip={`Auto historical window ~${linkedDays} days linked to training trades.`}
        />
        <StatusChip
          label="BIRTH"
          state={engineLive ? "warn" : "ok"}
          tip={
            engineLive
              ? "Birth engine is running in the background — stop before wipe. Does not block re-entry to Genesis."
              : "Birth engine idle — safe to activate. This chip is status only; it does not gate Activate Birth."
          }
        />
      </div>

      <div className="risk-envelope-banner risk-envelope-banner--info mx-2 mt-2 shrink-0">
        <p className="text-[11px] leading-relaxed">
          <strong className="text-cyan-200/90">What we need from you:</strong> review the auto
          charter, set data policy, then activate birth. Training size and Stage‑1 winrate gate
          are computed for this install — not manual sliders.
        </p>
      </div>

      {error ? (
        <p
          className={cn("mx-2 mt-2 shrink-0 rounded-lg p-2 text-xs", distressPanelClass("error"))}
          role="alert"
          title={error}
        >
          <span className={cn(warnOverlayBodyClass(), "line-clamp-3")}>{error}</span>
        </p>
      ) : null}

      {sessionProbePending || sessionProbeState === "error" ? (
        <div
          className={cn(
            "risk-envelope-banner mx-2 mt-2 shrink-0",
            sessionProbeState === "error"
              ? "risk-envelope-banner--warn"
              : "risk-envelope-banner--info",
          )}
          role="status"
          aria-live="polite"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="min-w-0 flex-1 text-[11px] leading-relaxed">
              {sessionProbeState === "error" ? (
                <>
                  <strong className="text-amber-200/90">Session status unavailable:</strong>{" "}
                  Could not confirm whether a previous birth is waiting. Activate stays locked
                  until status loads — retry so you do not overwrite a checkpoint by accident.
                </>
              ) : (
                <>
                  <strong className="text-cyan-200/90">Loading session state:</strong>{" "}
                  Checking for a previous birth (checkpoint / interrupted run). Activate is
                  locked until this finishes.
                </>
              )}
            </p>
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
          </div>
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
                    label="Winrate gate"
                    value={`${gatePct}%`}
                    tip={
                      helpFor("stage1_winrate_gate") ??
                      "Stage 1 pipeline pass threshold. REAL still needs certificate OOS ≥48%."
                    }
                    footnote="Auto pipeline gate · not REAL guarantee"
                  />
                  <CharterTile
                    label="Historical window"
                    value={`~${linkedDays}d`}
                    tip={
                      helpFor("max_real_days") ??
                      "Calendar days of history linked to the training trade target."
                    }
                    footnote="Auto-linked to training trades"
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
                <div
                  className={cn(
                    "risk-envelope-banner mb-3 shrink-0",
                    sessionProbePending
                      ? "risk-envelope-banner--info"
                      : sessionInterrupted || resumePlateauRisk
                        ? "risk-envelope-banner--warn"
                        : "risk-envelope-banner--info",
                  )}
                >
                  <p className="text-[11px] leading-relaxed">
                    <strong className="text-cyan-200/90">
                      {sessionProbePending
                        ? "Detecting previous session:"
                        : sessionInterrupted
                          ? "Session interrupted:"
                          : checkpointAvailable
                            ? "Checkpoint ready:"
                            : "Recovery:"}
                    </strong>{" "}
                    {sessionProbePending
                      ? "Loading resume / wipe options from the last birth. Activate stays locked until this completes."
                      : sessionInterrupted
                        ? "Previous birth stopped before completion. Resume if a checkpoint exists, or wipe for a clean start (two-step safety confirm)."
                        : checkpointAvailable
                          ? "Resume curriculum from the last stage, or wipe data if you want a clean run."
                          : "Wipe birth data for a clean start, or Activate for a new run. Wipe always opens a safety dialog."}
                  </p>
                </div>

                {sessionProbePending ? (
                  <div className="mb-3 flex items-center justify-center gap-2 rounded-lg border border-cyan-500/20 bg-cyan-950/20 px-3 py-4 font-mono text-[11px] text-cyan-100/80">
                    <Loader2 className="size-4 animate-spin text-cyan-300" aria-hidden />
                    Loading Resume · Wipe birth data · Full wipe…
                  </div>
                ) : null}

                {!sessionProbePending ? (
                <BirthGenesisStatusChips
                  engineLive={engineLive}
                  resumePlateauRisk={resumePlateauRisk}
                  resumePlateauRiskTrades={resumePlateauRiskTrades}
                  checkpointAvailable={checkpointAvailable}
                  checkpointSummary={checkpointSummary}
                  resumeTierHint={resumeTierHint}
                  className="mb-3 justify-center"
                />
                ) : null}

                {!sessionProbePending ? (
                <div className="genesis-recovery-action-grid">
                  {checkpointAvailable ? (
                    <RecoveryActionCard
                      label="Resume"
                      tip="Continue from the last stage / PPO steps. Data prep may re-run briefly; curriculum is not wiped."
                      hint={checkpointSummary ?? "Checkpoint available"}
                      tone="accent"
                    >
                      <Button
                        type="button"
                        size="sm"
                        className={cn(
                          luminaInteractiveClass("default"),
                          "genesis-recovery-action-card__btn w-full font-mono text-[10px] tracking-wide uppercase",
                          busy && "cursor-not-allowed opacity-70",
                        )}
                        disabled={busy}
                        onClick={() => {
                          if (busy) {
                            toast.info("Please wait — another birth action is in progress.");
                            return;
                          }
                          onResumeCheckpoint?.();
                        }}
                      >
                        <RotateCcw className="size-3.5 shrink-0" aria-hidden />
                        <span>Resume checkpoint</span>
                      </Button>
                    </RecoveryActionCard>
                  ) : null}

                  <RecoveryActionCard
                    label="Reset data"
                    tip="Clear checkpoint, PPO weights progress, and stage receipts. Tick cache is kept for faster reloads."
                    hint="Tick cache kept · two-step confirm"
                    tone="warn"
                  >
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className={cn(
                        luminaInteractiveClass("danger"),
                        "genesis-recovery-action-card__btn w-full border-[color:var(--status-warn-border)] font-mono text-[10px] tracking-wide text-[color:var(--status-warn-fg)] uppercase hover:bg-[color:var(--status-warn-bg)]",
                        wipeBlocked && "cursor-not-allowed opacity-70",
                      )}
                      disabled={wipeBlocked}
                      aria-busy={wipeConfirmWiping}
                      onClick={() => {
                        const kind: WipeConfirmKind = "reset";
                        traceBirthWipe("ui.wipe_button.click", {
                          mode: "genesis",
                          kind,
                          busy,
                          activating,
                          wiping: wipeConfirmWiping,
                          source: "recovery_tab",
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
                      <span>Wipe birth data</span>
                    </Button>
                  </RecoveryActionCard>

                  <RecoveryActionCard
                    label="Full wipe"
                    tip="Permanent removal of all birth artifacts including tick cache and enrichment. Use only for a hard clean start."
                    hint="Includes tick cache · two-step confirm"
                    tone="danger"
                  >
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className={cn(
                        luminaInteractiveClass("danger"),
                        "genesis-recovery-action-card__btn w-full border-red-600/55 bg-red-950/20 font-mono text-[10px] tracking-wide text-red-100 uppercase hover:bg-red-950/40",
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
                          source: "recovery_tab",
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
                    </Button>
                  </RecoveryActionCard>

                  {engineLive ? (
                    <RecoveryActionCard
                      label="Stop engine"
                      tip="Stop the live birth engine. Checkpoint is kept when possible."
                      hint="Engine still running"
                      tone="danger"
                    >
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className={cn(
                          luminaInteractiveClass("danger"),
                          "genesis-recovery-action-card__btn w-full border-red-500/45 font-mono text-[10px] tracking-wide text-red-200 uppercase",
                          busy && "cursor-not-allowed opacity-70",
                        )}
                        disabled={busy}
                        onClick={() => {
                          if (busy) {
                            toast.info("Please wait — another birth action is in progress.");
                            return;
                          }
                          // Confirm host runs the stop after operator confirms.
                          openStopConfirm();
                        }}
                      >
                        <OctagonPause className="size-3.5 shrink-0" aria-hidden />
                        <span>Stop birth</span>
                      </Button>
                    </RecoveryActionCard>
                  ) : null}
                </div>
                ) : null}

                <p className="mt-3 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
                  Wipe always opens a two-step safety dialog · Activate arms a fresh run
                </p>
              </TabsContent>
            ) : null}
          </div>
        </Tabs>
      </div>

      <div className="risk-envelope-cta-bar genesis-launch-cta shrink-0">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <BirthGenesisStatusChips
            engineLive={engineLive}
            resumePlateauRisk={resumePlateauRisk}
            resumePlateauRiskTrades={resumePlateauRiskTrades}
            checkpointAvailable={checkpointAvailable}
            checkpointSummary={checkpointSummary}
            resumeTierHint={resumeTierHint}
          />
          {onOpenSetup ? (
            <button
              type="button"
              className="onboarding-btn-secondary lumina-interactive rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
              onClick={onOpenSetup}
              disabled={disabled}
            >
              Setup & connection
            </button>
          ) : null}
        </div>

        <p className="mb-2 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
          {sessionLocked
            ? "Activate locked until session status loads · prevents accidental overwrite"
            : showRecoveryTab
              ? "Recovery actions are on the Recovery tab · hold Activate for a fresh ring arm"
              : "Hold to arm the ring · birth engine idle is normal before activate"}
        </p>
        <BirthLaunchButton
          activating={activating}
          primed={helixPrimed}
          disabled={busy || sessionLocked}
          waitingSession={sessionLocked}
          onClick={onActivate}
          onPrimedChange={setHelixPrimed}
          onSequencingChange={setSequencing}
          className="w-full"
        />
      </div>
    </div>
  );
}
