import type { OnboardingStepId } from "@/lib/onboardingSteps";
import { STEP_LABELS } from "@/lib/onboardingSteps";
import { cn } from "@/lib/utils";

interface StepProgressRailProps {
  steps: OnboardingStepId[];
  currentStep: OnboardingStepId;
  stepStatus: Record<string, string>;
}

export function StepProgressRail({ steps, currentStep, stepStatus }: StepProgressRailProps) {
  const visible = steps.filter((s) => s !== "welcome");
  if (visible.length <= 1) return null;

  return (
    <nav
      className="mb-8 flex flex-wrap items-center justify-center gap-3"
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
