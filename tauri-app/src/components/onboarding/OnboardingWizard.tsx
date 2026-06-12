import { useCallback, useEffect, useMemo, useState } from "react";

import { motion } from "framer-motion";

import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { useOnboardingModeMotion } from "@/hooks/useOnboardingModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { distressPanelClass, warnOverlayBodyClass } from "@/lib/modePresentation";
import { stepFade, transitionOrNone } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";
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
  const setPhase = useOnboardingStore((s) => s.setPhase);
  const currentStepIndex = useOnboardingStore((s) => s.currentStepIndex);
  const draft = useOnboardingStore((s) => s.draft);
  const error = useOnboardingStore((s) => s.error);
  const activating = useOnboardingStore((s) => s.activating);
  const smartSetupRunning = useOnboardingStore((s) => s.smartSetupRunning);
  const refresh = useOnboardingStore((s) => s.refresh);
  const setStepIndex = useOnboardingStore((s) => s.setStepIndex);
  const updateDraft = useOnboardingStore((s) => s.updateDraft);
  const runSmartSetup = useOnboardingStore((s) => s.runSmartSetup);
  const saveCredentials = useOnboardingStore((s) => s.saveCredentials);
  const saveConfiguration = useOnboardingStore((s) => s.saveConfiguration);
  const activateBirth = useOnboardingStore((s) => s.activateBirth);
  const importCredentialsFromEnv = useOnboardingStore((s) => s.importCredentialsFromEnv);
  const [savingCredentials, setSavingCredentials] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const onboardingMotion = useOnboardingModeMotion();
  const stepTransition = transitionOrNone(reducedMotion, stepFade);

  const steps = useMemo(() => selectActiveSteps(payload), [payload]);
  const currentStep = steps[currentStepIndex] ?? steps[0] ?? "welcome";
  const shortPath = steps.length <= 2;

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

  const handleCredentialsContinue = async () => {
    setSavingCredentials(true);
    const ok = await saveCredentials();
    setSavingCredentials(false);
    if (ok) advance();
  };

  const handleConfigContinue = async () => {
    const ok = await saveConfiguration();
    if (ok) advance();
  };

  useEffect(() => {
    if (payload?.app_surface === "birth") {
      setPhase("birth");
    }
  }, [payload?.app_surface, setPhase]);

  useEffect(() => {
    if (smartSetupRunning) {
      const timer = setInterval(() => void refresh(), 2500);
      return () => clearInterval(timer);
    }
  }, [smartSetupRunning, refresh]);

  useEffect(() => {
    if (!payload) return;
    if (currentStep !== "credentials") return;
    if (payload.credentials.wizard_required === false) {
      advance();
      return;
    }
    if (!steps.includes("credentials")) {
      advance();
    }
  }, [payload, currentStep, steps, advance]);

  if (!payload || !payload.backend.reachable) {
    return (
      <OnboardingShell>
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-6 px-4 py-8">
          <BackendStep
            reachable={false}
            connectionError={error ?? payload?.backend.error}
            onConnected={() => void refresh()}
            onRefresh={() => void refresh()}
          />
        </div>
      </OnboardingShell>
    );
  }

  if (payload.app_surface === "birth") {
    return null;
  }

  const renderStep = () => {
    switch (currentStep) {
      case "welcome":
        return (
          <WelcomeStep
            onContinue={advance}
            shortPath={shortPath}
            readiness={payload.readiness}
          />
        );
      case "backend":
        return (
          <BackendStep
            reachable={payload.backend.reachable}
            readiness={payload.readiness}
            connectionError={error}
            onConnected={advance}
            onRefresh={() => void refresh()}
          />
        );
      case "ollama":
      case "model":
        return (
          <SmartSetupStep
            payload={payload}
            running={smartSetupRunning}
            selectedModelKey={draft.selected_model_key}
            onSelectModel={(key) => updateDraft({ selected_model_key: key })}
            onRun={(opts) => void runSmartSetup(opts)}
            onContinue={advance}
            onRefresh={() => void refresh()}
          />
        );
      case "credentials":
        return (
          <CredentialsStep
            draft={draft}
            missing={payload.credentials.missing}
            present={payload.credentials.present}
            envPath={
              payload.credentials.env_path ??
              (payload.workspace_root ? `${payload.workspace_root}/.env` : undefined)
            }
            hasAdminApiKeyInEnv={payload.credentials.has_admin_api_key}
            wizardRequired={payload.credentials.wizard_required ?? true}
            skipReason={payload.credentials.skip_reason ?? null}
            saving={savingCredentials}
            onChange={(credentials) => updateDraft({ credentials })}
            onContinue={() => void handleCredentialsContinue()}
            onImportFromEnv={importCredentialsFromEnv}
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

  const isBirthStep = currentStep === "birth";

  return (
    <OnboardingShell
      className={cn("onboarding-shell--form", isBirthStep && "onboarding-shell--birth")}
    >
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col",
          isBirthStep
            ? "w-full min-h-0 flex-1 overflow-hidden px-4 py-0"
            : "items-center overflow-y-auto px-4 py-8",
        )}
      >
        <div
          className={cn(
            "w-full min-h-0",
            isBirthStep
              ? "onboarding-birth-column overflow-hidden"
              : "flex flex-col items-center",
          )}
        >
        {currentStep !== "welcome" && payload && (
          <StepProgressRail
            steps={displayStepsDeduped}
            currentStep={railStep}
            stepStatus={payload.step_status}
            compact={isBirthStep}
            minimal={isBirthStep}
          />
        )}
        {error && currentStep !== "birth" ? (
          <p className={cn("mb-4 max-w-xl rounded-lg p-3 text-center text-sm", distressPanelClass("error"))} role="alert">
            <span className={warnOverlayBodyClass()}>{error}</span>
          </p>
        ) : null}
        <motion.div
          key={currentStep}
          className={cn(
            "w-full",
            !isBirthStep && "max-w-xl",
            currentStep !== "welcome" &&
              currentStep !== "birth" &&
              "lumina-glass lumina-glass--panel rounded-xl p-4 md:p-6",
            isBirthStep &&
              "onboarding-birth-viewport flex min-h-0 max-w-none flex-1 flex-col",
          )}
          initial={reducedMotion ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={stepTransition}
        >
          {renderStep()}
        </motion.div>
        </div>
      </div>
    </OnboardingShell>
  );
}
