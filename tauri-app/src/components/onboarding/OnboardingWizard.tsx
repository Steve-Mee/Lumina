import { useCallback, useEffect, useMemo } from "react";

import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { StepProgressRail } from "@/components/onboarding/StepProgressRail";
import { BackendStep } from "@/components/onboarding/steps/BackendStep";
import { BirthActivateStep } from "@/components/onboarding/steps/BirthActivateStep";
import { CredentialsStep } from "@/components/onboarding/steps/CredentialsStep";
import { QuickConfigStep } from "@/components/onboarding/steps/QuickConfigStep";
import { SmartSetupStep } from "@/components/onboarding/steps/SmartSetupStep";
import { WelcomeStep } from "@/components/onboarding/steps/WelcomeStep";
import type { OnboardingStepId } from "@/lib/onboardingSteps";
import {
  selectActiveSteps,
  useOnboardingStore,
} from "@/store/onboardingStore";

function needsSmartSetupStep(step: OnboardingStepId): boolean {
  return step === "ollama" || step === "model";
}

export function OnboardingWizard() {
  const payload = useOnboardingStore((s) => s.payload);
  const currentStepIndex = useOnboardingStore((s) => s.currentStepIndex);
  const draft = useOnboardingStore((s) => s.draft);
  const error = useOnboardingStore((s) => s.error);
  const activating = useOnboardingStore((s) => s.activating);
  const smartSetupRunning = useOnboardingStore((s) => s.smartSetupRunning);
  const refresh = useOnboardingStore((s) => s.refresh);
  const setStepIndex = useOnboardingStore((s) => s.setStepIndex);
  const updateDraft = useOnboardingStore((s) => s.updateDraft);
  const runSmartSetup = useOnboardingStore((s) => s.runSmartSetup);
  const saveConfiguration = useOnboardingStore((s) => s.saveConfiguration);
  const activateBirth = useOnboardingStore((s) => s.activateBirth);

  const steps = useMemo(() => selectActiveSteps(payload), [payload]);
  const currentStep = steps[currentStepIndex] ?? steps[0] ?? "welcome";
  const shortPath = steps.filter((s) => s !== "welcome").length <= 2;

  const advance = useCallback(() => {
    let next = currentStepIndex + 1;
    const current = steps[currentStepIndex];
    if (current && needsSmartSetupStep(current)) {
      while (next < steps.length && needsSmartSetupStep(steps[next]!)) {
        next += 1;
      }
    }
    setStepIndex(Math.min(next, steps.length - 1));
  }, [currentStepIndex, setStepIndex, steps]);

  const handleConfigContinue = async () => {
    const ok = await saveConfiguration();
    if (ok) advance();
  };

  useEffect(() => {
    if (smartSetupRunning) {
      const timer = setInterval(() => void refresh(), 2500);
      return () => clearInterval(timer);
    }
  }, [smartSetupRunning, refresh]);

  if (!payload) {
    return (
      <OnboardingShell>
        <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-8">
          <BackendStep
            reachable={false}
            onConnected={() => void refresh()}
            onRefresh={() => void refresh()}
          />
          {error && (
            <p className="max-w-md text-center text-sm text-red-400/90" role="alert">
              {error}
            </p>
          )}
        </div>
      </OnboardingShell>
    );
  }

  const renderStep = () => {
    switch (currentStep) {
      case "welcome":
        return <WelcomeStep onContinue={advance} shortPath={shortPath} />;
      case "backend":
        return (
          <BackendStep
            reachable={payload?.backend.reachable ?? false}
            onConnected={advance}
            onRefresh={() => void refresh()}
          />
        );
      case "ollama":
      case "model":
        return payload ? (
          <SmartSetupStep
            payload={payload}
            running={smartSetupRunning}
            onRun={() => void runSmartSetup()}
            onContinue={advance}
            onRefresh={() => void refresh()}
          />
        ) : null;
      case "credentials":
        return (
          <CredentialsStep
            draft={draft}
            missing={payload?.credentials.missing ?? []}
            onChange={(credentials) => updateDraft({ credentials })}
            onContinue={advance}
          />
        );
      case "configuration":
        return (
          <QuickConfigStep
            draft={draft}
            onChange={updateDraft}
            onContinue={() => void handleConfigContinue()}
          />
        );
      case "birth":
        return (
          <BirthActivateStep
            draft={draft}
            setupComplete={payload?.setup_complete ?? false}
            activating={activating}
            error={error}
            onChangeTraining={(training) => updateDraft({ training: { ...draft.training, ...training } })}
            onActivate={() => void activateBirth()}
          />
        );
      default:
        return null;
    }
  };

  // Collapse ollama+model into one smart setup view when both present
  const displaySteps = steps.filter(
    (s, i) => !needsSmartSetupStep(s) || steps.indexOf(s) === i,
  );
  const displayStepsDeduped = displaySteps.filter(
    (s, i, arr) => !(needsSmartSetupStep(s) && arr.slice(0, i).some(needsSmartSetupStep)),
  );

  const smartStepActive = needsSmartSetupStep(currentStep);
  const railStep = smartStepActive ? ("ollama" as OnboardingStepId) : currentStep;

  return (
    <OnboardingShell>
      <div className="flex flex-1 flex-col items-center overflow-y-auto px-4 py-8">
        {currentStep !== "welcome" && payload && (
          <StepProgressRail
            steps={displayStepsDeduped}
            currentStep={railStep}
            stepStatus={payload.step_status}
          />
        )}
        {error && currentStep !== "birth" && (
          <p className="mb-4 max-w-xl text-center text-sm text-red-400/90" role="alert">
            {error}
          </p>
        )}
        {renderStep()}
      </div>
    </OnboardingShell>
  );
}
