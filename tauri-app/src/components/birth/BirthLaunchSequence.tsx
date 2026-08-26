import { CredentialsVaultOrganism } from "@/components/onboarding/CredentialsVaultOrganism";
import {
  BIRTH_ACTIVATION_STEPS,
  activationStepIndex,
  type BirthActivationStep,
} from "@/lib/birthOperatorMode";
import type { StartupStepState } from "@/lib/startupReadinessModel";
import { startupStepStateLabel } from "@/lib/startupReadinessModel";
import { cn } from "@/lib/utils";

interface BirthLaunchSequenceProps {
  step: BirthActivationStep;
  className?: string;
}

function stepState(
  index: number,
  current: number,
  step: BirthActivationStep,
): StartupStepState {
  if (step === "done" || current > index) return "done";
  if (current < 0 ? index === 0 : index === Math.min(current, BIRTH_ACTIVATION_STEPS.length - 1)) {
    return "running";
  }
  return "pending";
}

function chipDataState(state: StartupStepState): "ok" | "partial" | "fail" | undefined {
  if (state === "done") return "ok";
  if (state === "running") return "partial";
  if (state === "blocked") return "fail";
  return undefined;
}

function stepDetail(id: string, state: StartupStepState): string {
  if (state === "done") {
    switch (id) {
      case "fabric":
        return "Fabric host link verified";
      case "twin":
        return "Approval Twin path ready";
      case "history":
        return "Market history path ready";
      case "engine":
        return "Birth engine started";
      default:
        return "Complete";
    }
  }
  if (state === "running") {
    switch (id) {
      case "fabric":
        return "Confirming Fabric GREEN / host ready…";
      case "twin":
        return "Checking Twin readiness…";
      case "history":
        return "Preparing historical curriculum…";
      case "engine":
        return "Starting birth engine…";
      default:
        return "In progress…";
    }
  }
  return "Waiting for prior step";
}

/**
 * Birth activation ceremony — same Systems Go vault language as cold start.
 * One intent, one glass card, no wipe/recovery thrash.
 */
export function BirthLaunchSequence({ step, className }: BirthLaunchSequenceProps) {
  const current = activationStepIndex(step);
  const steps = BIRTH_ACTIVATION_STEPS.map((item, index) => ({
    ...item,
    state: stepState(index, current, step),
  }));
  const activeId = steps.find((s) => s.state === "running")?.id;
  const anyRunning = steps.some((s) => s.state === "running");
  const allDone = step === "done" || steps.every((s) => s.state === "done");
  const linked = allDone || steps.filter((s) => s.state === "done").length >= 2;
  const stageCaption = allDone
    ? "Link sealed · birth starting"
    : anyRunning
      ? "Activation sequence · systems awakening"
      : "Organism waiting · channels dark";

  return (
    <div
      className={cn(
        "birth-launch-sequence systems-go-shell relative z-20 flex min-h-0 flex-1 flex-col overflow-hidden",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy={!allDone}
      aria-label="Birth activation in progress"
    >
      <div className="systems-go-viewport">
        <div className="systems-go-window lumina-glass lumina-glass--overlay">
          <div className="systems-go-window__presence" aria-hidden>
            <CredentialsVaultOrganism linked={linked} caption={stageCaption} />
          </div>

          <section className="systems-go-panel" aria-label="Birth activation checklist">
            <header className="systems-go-panel__toolbar">
              <div className="min-w-0">
                <p className="systems-go-panel__eyebrow">Birth Protocol · Activation</p>
                <h1 className="systems-go-panel__title">Starting Birth</h1>
                <p className="systems-go-panel__subtitle">
                  Verifying systems in order. Stay on this screen — nothing is broken while steps
                  complete.
                </p>
              </div>
            </header>

            <div
              className="systems-go-chip-strip"
              role="list"
              aria-label="Activation channel status"
            >
              {steps.map((item) => (
                <span
                  key={item.id}
                  role="listitem"
                  className="credentials-vault-status-chip"
                  data-state={chipDataState(item.state)}
                  title={stepDetail(item.id, item.state)}
                >
                  <span className="credentials-vault-status-chip__dot" aria-hidden />
                  {item.label}
                </span>
              ))}
            </div>

            <div className="systems-go-body" role="list" aria-label="Activation steps">
              {steps.map((item) => (
                <div
                  key={item.id}
                  className="systems-go-step"
                  role="listitem"
                  data-state={item.state}
                  data-active={item.id === activeId ? "true" : undefined}
                >
                  <span className="systems-go-step__dot" aria-hidden />
                  <div className="systems-go-step__meta">
                    <div className="systems-go-step__head">
                      <span className="systems-go-step__label">{item.label}</span>
                      <span className="systems-go-step__badge">
                        {startupStepStateLabel(item.state)}
                      </span>
                    </div>
                    <p className="systems-go-step__detail" title={stepDetail(item.id, item.state)}>
                      {stepDetail(item.id, item.state)}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <footer className="systems-go-footer">
              <p className="systems-go-footer__hint">
                {allDone
                  ? "All activation steps complete · entering Birth…"
                  : anyRunning
                    ? "Working — hold for systems ready"
                    : "One clean activation · then curriculum training"}
              </p>
            </footer>
          </section>
        </div>
      </div>
    </div>
  );
}
