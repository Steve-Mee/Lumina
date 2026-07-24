import { useCallback, useEffect, useMemo, useState } from "react";

import { motion } from "framer-motion";
import { toast } from "sonner";

import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { resolveWizardPhaseHeader } from "@/lib/luminaPhasePresentation";
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
  const setupReviewActive = useOnboardingStore((s) => s.setupReviewActive);
  const exitSetupReview = useOnboardingStore((s) => s.exitSetupReview);
  const [savingCredentials, setSavingCredentials] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const stepTransition = transitionOrNone(reducedMotion, stepFade);

  const steps = useMemo(
    () => selectActiveSteps(payload),
    // Recompute when review mode toggles (selectActiveSteps reads store flag).
    // eslint-disable-next-line react-hooks/exhaustive-deps -- setupReviewActive is intentional
    [payload, setupReviewActive],
  );
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
    if (ok) {
      // Operator reopened vault from Birth — return to Genesis after seal.
      if (useOnboardingStore.getState().setupReviewActive) {
        useOnboardingStore.getState().exitSetupReview();
        return;
      }
      // When setup is complete, SSOT moves to Birth — no need to advance wizard steps.
      const surface = useOnboardingStore.getState().payload?.app_surface;
      const phase = useOnboardingStore.getState().phase;
      if (phase === "birth" || surface === "birth") {
        return;
      }
      advance();
      return;
    }
    const message = useOnboardingStore.getState().error?.trim() || "Could not seal vault";
    toast.error(message);
  };

  const handleConfigContinue = async () => {
    const ok = await saveConfiguration();
    if (ok) advance();
  };

  useEffect(() => {
    // Do not kick operators out of setup review back to Birth on refresh SSOT.
    if (setupReviewActive) return;
    if (payload?.app_surface === "birth") {
      setPhase("birth");
    }
  }, [payload?.app_surface, setPhase, setupReviewActive]);

  useEffect(() => {
    if (smartSetupRunning) {
      const timer = setInterval(() => void refresh(), 2500);
      return () => clearInterval(timer);
    }
  }, [smartSetupRunning, refresh]);

  useEffect(() => {
    if (!payload) return;
    if (setupReviewActive) return;
    if (currentStep !== "credentials") return;
    if (payload.credentials.wizard_required === false) {
      advance();
      return;
    }
    if (!steps.includes("credentials")) {
      advance();
    }
  }, [payload, currentStep, steps, advance, setupReviewActive]);

  if (!payload || !payload.backend.reachable) {
    return (
      <OnboardingShell>
        <LuminaPhaseHeader {...resolveWizardPhaseHeader("backend")} variant="hero" />
        <EvolutionLadderStrip className="relative z-20 shrink-0" />
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

  // When operator reopens setup from Birth, keep rendering the wizard even if SSOT is birth.
  if (payload.app_surface === "birth" && !setupReviewActive) {
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
            wizardRequired={setupReviewActive ? true : (payload.credentials.wizard_required ?? true)}
            skipReason={setupReviewActive ? null : (payload.credentials.skip_reason ?? null)}
            setupReviewActive={setupReviewActive}
            saving={savingCredentials}
            onChange={(credentials) => updateDraft({ credentials })}
            onContinue={() => void handleCredentialsContinue()}
            onImportFromEnv={importCredentialsFromEnv}
            onBackToGenesis={setupReviewActive ? () => exitSetupReview() : undefined}
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
  const isCredentialsStep = currentStep === "credentials";
  const isConfigurationStep = currentStep === "configuration";
  const isCinematicStep = isBirthStep || isCredentialsStep || isConfigurationStep;
  const phaseHeader = resolveWizardPhaseHeader(currentStep, activating);

  return (
    <OnboardingShell
      className={cn(
        "onboarding-shell--form",
        isBirthStep && "onboarding-shell--birth",
        isCredentialsStep && "onboarding-shell--birth credentials-vault-host",
        isConfigurationStep && "onboarding-shell--birth risk-envelope-host",
      )}
    >
      <LuminaPhaseHeader
        {...phaseHeader}
        variant={isCinematicStep ? "strip" : "hero"}
        className="relative z-20 shrink-0"
      />
      <EvolutionLadderStrip className="relative z-20 shrink-0" />
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col",
          isCinematicStep
            ? "w-full min-h-0 flex-1 overflow-hidden"
            : "items-center overflow-y-auto px-4 py-8",
        )}
      >
        <div
          className={cn(
            "w-full min-h-0",
            isCinematicStep
              ? "flex min-h-0 flex-1 flex-col overflow-hidden"
              : "flex flex-col items-center",
          )}
        >
        {currentStep !== "welcome" &&
        currentStep !== "credentials" &&
        currentStep !== "configuration" &&
        payload ? (
          <StepProgressRail
            steps={displayStepsDeduped}
            currentStep={railStep}
            stepStatus={payload.step_status}
            compact={isBirthStep}
            minimal={isBirthStep}
          />
        ) : null}
        {error && currentStep !== "birth" && currentStep !== "credentials" ? (
          <p className={cn("mb-4 max-w-xl rounded-lg p-3 text-center text-sm", distressPanelClass("error"))} role="alert">
            <span className={warnOverlayBodyClass()}>{error}</span>
          </p>
        ) : null}
        {error && currentStep === "credentials" ? (
          <p
            className={cn(
              "relative z-20 mx-3 mt-2 shrink-0 rounded-lg px-3 py-2 text-center text-xs",
              distressPanelClass("error"),
            )}
            role="alert"
          >
            <span className={warnOverlayBodyClass()}>{error}</span>
          </p>
        ) : null}
        <motion.div
          key={currentStep}
          className={cn(
            "w-full",
            !isCinematicStep && "max-w-xl",
            currentStep !== "welcome" &&
              currentStep !== "birth" &&
              currentStep !== "credentials" &&
              "lumina-glass lumina-glass--panel rounded-xl p-4 md:p-6",
            isCinematicStep &&
              "flex min-h-0 max-w-none flex-1 flex-col overflow-hidden",
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
