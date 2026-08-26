/**
 * Systems Go cover — vault/mission visual language.
 * Stage organism + glass mission panel + traffic steps.
 */
import { useEffect, useMemo, useState } from "react";

import { CredentialsVaultOrganism } from "@/components/onboarding/CredentialsVaultOrganism";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { NinjaTraderRequiredDialog } from "@/components/startup/NinjaTraderRequiredDialog";
import { SystemsGoDialog } from "@/components/startup/SystemsGoDialog";
import type { SystemsProgress } from "@/lib/startupSystemsOrchestrator";
import type { OnboardingPayload } from "@/lib/onboardingSteps";
import type { StartupStepState } from "@/lib/startupReadinessModel";
import { startupStepStateLabel } from "@/lib/startupReadinessModel";
import { cn } from "@/lib/utils";

/** Map step state → vault status-chip data-state (ok | partial | fail). */
function chipState(state: StartupStepState): "ok" | "partial" | "fail" | undefined {
  if (state === "done") return "ok";
  if (state === "running") return "partial";
  if (state === "blocked") return "fail";
  return undefined;
}

function stepLabel(id: string): string {
  switch (id) {
    case "backend":
      return "Backend";
    case "nt_process":
      return "NinjaTrader";
    case "fabric":
      return "Fabric link";
    case "birth_session":
      return "Birth session";
    case "route":
      return "Surface";
    default:
      return id;
  }
}

export function StartupReadinessScreen({
  payload,
  fetchError,
  systemsProgress,
  showNtDialog,
  showFabricChoice,
  showBirthRetry,
  ntWaiting,
  waitDetail,
  onStartNinjaTrader,
  onContinueWithoutNt,
  onRetryFabric,
  onRetryBirth,
  onRetry,
  className,
}: {
  payload: OnboardingPayload | null;
  fetchError?: string | null;
  systemsProgress?: SystemsProgress | null;
  showNtDialog?: boolean;
  showFabricChoice?: boolean;
  showBirthRetry?: boolean;
  ntWaiting?: boolean;
  waitDetail?: string | null;
  onStartNinjaTrader?: () => void;
  onContinueWithoutNt?: () => void;
  onRetryFabric?: () => void;
  onRetryBirth?: () => void;
  onRetry?: () => void | Promise<void>;
  className?: string;
}) {
  const [fetching, setFetching] = useState(false);

  const steps = systemsProgress?.steps ?? [];
  const headline =
    systemsProgress?.headline ?? (fetchError ? "Backend unreachable" : "Systems Go");
  const subtitle =
    systemsProgress?.subtitle ??
    (fetchError
      ? "Cannot reach the control plane. Retry when the backend is up."
      : "Bringing Lumina online — one clean start");

  const canRetryBackend =
    Boolean(fetchError) || payload?.backend.reachable === false;

  const fabricLinked = systemsProgress?.fabricGreen === true;
  const stageCaption = useMemo(() => {
    if (fabricLinked) return "Link sealed · systems online";
    if (steps.some((s) => s.state === "running")) return "Systems awakening…";
    if (steps.some((s) => s.state === "blocked")) {
      return "Channels blocked · operator action";
    }
    return "Organism waiting · channels dark";
  }, [fabricLinked, steps]);

  const activeRunning = steps.some((s) => s.state === "running");
  const activeStepId = steps.find((s) => s.state === "running" || s.state === "blocked")?.id;

  useEffect(() => {
    if (!canRetryBackend || !onRetry) return;
    const id = globalThis.setInterval(() => {
      void (async () => {
        setFetching(true);
        try {
          await onRetry();
        } finally {
          setFetching(false);
        }
      })();
    }, 2000);
    return () => globalThis.clearInterval(id);
  }, [canRetryBackend, onRetry]);

  const allSettled =
    steps.length > 0 &&
    steps.every((s) => s.state === "done" || s.state === "skipped") &&
    !activeRunning;

  return (
    <OnboardingShell
      className={cn(
        "onboarding-shell--form onboarding-shell--birth systems-go-shell",
        className,
      )}
    >
      <div className="systems-go-viewport">
        <div
          className="systems-go-window lumina-glass lumina-glass--overlay"
          role="status"
          aria-live="polite"
          aria-label="Lumina systems go"
        >
          <div className="systems-go-window__presence" aria-hidden>
            <CredentialsVaultOrganism linked={fabricLinked || allSettled} caption={stageCaption} />
          </div>

          <section className="systems-go-panel" aria-label="Systems checklist">
            <header className="systems-go-panel__toolbar">
              <div className="min-w-0">
                <p className="systems-go-panel__eyebrow">Lumina · Systems Go</p>
                <h1 className="systems-go-panel__title">{headline}</h1>
                <p className="systems-go-panel__subtitle">{subtitle}</p>
              </div>
            </header>

            {steps.length > 0 ? (
              <div
                className="systems-go-chip-strip"
                role="list"
                aria-label="System channel status"
              >
                {steps.map((step) => (
                  <span
                    key={step.id}
                    role="listitem"
                    className="credentials-vault-status-chip"
                    data-state={chipState(step.state)}
                    title={step.detail || stepLabel(step.id)}
                  >
                    <span className="credentials-vault-status-chip__dot" aria-hidden />
                    {stepLabel(step.id)}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="systems-go-body" role="list" aria-label="Startup systems">
              {steps.length === 0 ? (
                <div
                  className="systems-go-step"
                  data-state="running"
                  data-active="true"
                  role="listitem"
                >
                  <span className="systems-go-step__dot" aria-hidden />
                  <div className="systems-go-step__meta">
                    <div className="systems-go-step__head">
                      <span className="systems-go-step__label">Initializing</span>
                      <span className="systems-go-step__badge">running</span>
                    </div>
                    <p className="systems-go-step__detail">Preparing systems checklist…</p>
                  </div>
                </div>
              ) : (
                steps.map((step) => (
                  <div
                    key={step.id}
                    className="systems-go-step"
                    role="listitem"
                    data-state={step.state}
                    data-active={step.id === activeStepId ? "true" : undefined}
                  >
                    <span className="systems-go-step__dot" aria-hidden />
                    <div className="systems-go-step__meta">
                      <div className="systems-go-step__head">
                        <span className="systems-go-step__label">{stepLabel(step.id)}</span>
                        <span className="systems-go-step__badge">
                          {startupStepStateLabel(step.state)}
                        </span>
                      </div>
                      {step.detail ? (
                        <p className="systems-go-step__detail" title={step.detail}>
                          {step.detail}
                        </p>
                      ) : null}
                    </div>
                  </div>
                ))
              )}
            </div>

            <footer className="systems-go-footer">
              {canRetryBackend ? (
                <button
                  type="button"
                  className="onboarding-cta"
                  disabled={fetching}
                  onClick={() => {
                    setFetching(true);
                    void Promise.resolve(onRetry?.()).finally(() => setFetching(false));
                  }}
                >
                  {fetching ? "Retrying…" : "Retry backend"}
                </button>
              ) : (
                <p className="systems-go-footer__hint">
                  {allSettled
                    ? "All systems green · entering Lumina…"
                    : ntWaiting || activeRunning
                      ? "Working — hold for systems ready"
                      : "One clean start · then the deck is yours"}
                </p>
              )}
            </footer>
          </section>
        </div>
      </div>

      <NinjaTraderRequiredDialog
        open={Boolean(showNtDialog)}
        busy={ntWaiting}
        waitDetail={waitDetail}
        onStart={() => onStartNinjaTrader?.()}
        onContinueWithout={() => onContinueWithoutNt?.()}
      />

      <SystemsGoDialog
        open={Boolean(showFabricChoice && !showNtDialog)}
        eyebrow="Fabric · not ready"
        title="Connection is not GREEN yet"
        titleId="fabric-choice-title"
        busy={ntWaiting}
        primaryLabel="Retry Fabric"
        onPrimary={() => onRetryFabric?.()}
        secondaryLabel="Continue without live link"
        onSecondary={() => onContinueWithoutNt?.()}
        footnote="Without GREEN: review only — Activate Birth and trading stay blocked."
      >
        <p className="systems-go-dialog__text">
          {waitDetail ||
            "NinjaTrader is running but the LUMINA host link is not ready. Common fix: open New → LUMINA (reloads host token), wait for datafeed Connected, then Retry Fabric."}
        </p>
      </SystemsGoDialog>

      <SystemsGoDialog
        open={Boolean(showBirthRetry && !showNtDialog && !showFabricChoice)}
        eyebrow="Birth · session"
        title="Birth session not loaded"
        titleId="birth-retry-title"
        busy={ntWaiting}
        primaryLabel="Retry birth session"
        onPrimary={() => onRetryBirth?.()}
        secondaryLabel="Continue anyway (review only)"
        onSecondary={() => onContinueWithoutNt?.()}
      >
        <p className="systems-go-dialog__text">
          {waitDetail ||
            "Status could not be loaded yet. Retry here — do not open a half-loaded Genesis."}
        </p>
      </SystemsGoDialog>
    </OnboardingShell>
  );
}
