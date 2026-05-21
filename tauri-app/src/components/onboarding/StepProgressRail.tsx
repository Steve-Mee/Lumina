import type { OnboardingStepId } from "@/lib/onboardingSteps";
import { STEP_LABELS } from "@/lib/onboardingSteps";
import { cn } from "@/lib/utils";

interface StepProgressRailProps {
  steps: OnboardingStepId[];
  currentStep: OnboardingStepId;
  stepStatus: Record<string, string>;
  compact?: boolean;
  minimal?: boolean;
}

export function StepProgressRail({
  steps,
  currentStep,
  stepStatus,
  compact = false,
  minimal = false,
}: StepProgressRailProps) {
  const visible = steps.filter((s) => s !== "welcome");
  if (visible.length <= 1) return null;

  if (minimal) {
    return (
      <nav
        className="mb-3 flex w-full max-w-5xl shrink-0 justify-center"
        aria-label="Onboarding progress"
      >
        <span className="rounded-full border border-cyan-500/20 bg-cyan-500/5 px-3 py-1 font-mono text-[9px] tracking-[0.16em] text-cyan-300/80 uppercase">
          {STEP_LABELS[currentStep]}
        </span>
      </nav>
    );
  }

  return (
    <nav
      className={cn(
        "flex flex-wrap items-center justify-center gap-3",
        compact ? "mb-4" : "mb-8",
      )}
      aria-label="Onboarding progress"
    >
      {visible.map((step) => {
        const isActive = step === currentStep;
        const isDone = stepStatus[step] === "done";
        return (
          <div key={step} className="flex items-center gap-2">
            <span
              className="onboarding-step-rail-dot"
              data-active={isActive}
              data-done={isDone}
              aria-hidden
            />
            <span
              className={cn(
                "text-[10px] tracking-[0.14em] uppercase",
                isActive ? "text-cyan-300/90" : "text-muted-foreground",
              )}
            >
              {STEP_LABELS[step]}
            </span>
          </div>
        );
      })}
    </nav>
  );
}
