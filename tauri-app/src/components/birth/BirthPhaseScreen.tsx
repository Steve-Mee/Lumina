import { motion } from "framer-motion";

import { BirthLaunchSequence } from "@/components/birth/BirthLaunchSequence";
import { BirthPhaseGenesisBranch } from "@/components/birth/BirthPhaseGenesisBranch";
import { BirthPhaseMissionBranch } from "@/components/birth/BirthPhaseMissionBranch";
import { BirthPhaseRecoveryOverlays } from "@/components/birth/BirthPhaseRecoveryOverlays";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import { ModeTransitionVeil } from "@/components/cockpit/ModeTransitionVeil";
import { useBirthPhaseActions } from "@/hooks/useBirthPhaseActions";
import { useOnboardingModeMotion } from "@/hooks/useOnboardingModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { transitionOrNone, springBirthLuxury } from "@/lib/motionPresets";
import { warnOverlayPanelClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

export function BirthPhaseScreen() {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useOnboardingModeMotion();
  const birthMotion = { ...modeMotion, ...springBirthLuxury };

  const {
    derived,
    retrying,
    controlBusy,
    advancedOpen,
    setAdvancedOpen,
    realPreviewActive,
    milestoneVeilActive,
    setMilestoneVeilActive,
    setRecoveryDismissed,
    transition,
    handleStopBirth,
    handleStartBirth,
    handleWipeBirthData,
    handleResumeCheckpoint,
    handleExtraTraining,
    enterCommandDeck,
    onRealPreviewComplete,
    completeDeckEntry,
    handleResumeBirth,
    handleWipeRetryBirth,
    handleReuseDataBirth,
    returnToGenesis,
    retryBirth,
    enterSetupReview,
    onChangeTraining,
    stalledRecoveryActions,
    certificateFailureDetail,
  } = useBirthPhaseActions();

  const {
    phaseHeader,
    missionMode,
    recoveryOverlayActive,
    certificateFailedPinned,
    genesisMode,
    launchingMode,
    activationStep,
  } = derived;

  return (
    <OnboardingShell className="birth-phase-screen birth-phase-screen--cinematic onboarding-shell--form">
      <motion.div
        className={cn(
          "birth-phase-cinematic relative mx-auto flex h-dvh min-h-0 w-full max-w-none flex-col overflow-hidden",
          recoveryOverlayActive && "birth-phase-cinematic--recovery-active",
        )}
        animate={{ opacity: transition.active ? 0.35 : 1 }}
        transition={transitionOrNone(reducedMotion, birthMotion)}
      >
        <LuminaPhaseHeader
          {...phaseHeader}
          variant={missionMode && !launchingMode ? "compact" : "strip"}
          className="relative z-20"
        />
        <EvolutionLadderStrip
          className={cn(
            "relative z-20",
            missionMode && !launchingMode && "evolution-ladder-strip--dense !py-1",
          )}
        />
        {certificateFailedPinned ? (
          <p
            className={cn(
              "birth-distress-callout relative z-20 mx-4 mb-2 shrink-0 rounded-lg px-3 py-2 text-xs",
              warnOverlayPanelClass(),
            )}
          >
            Certificate not passed — backend still reports failure. Use Continue learning or Reuse
            data &amp; retry from recovery actions.
          </p>
        ) : null}
        {launchingMode ? (
          <BirthLaunchSequence step={activationStep} />
        ) : genesisMode ? (
          <BirthPhaseGenesisBranch
            derived={derived}
            controlBusy={controlBusy}
            onActivate={() => void handleStartBirth()}
            onWipe={handleWipeBirthData}
            onStop={handleStopBirth}
            onResumeCheckpoint={handleResumeCheckpoint}
            onOpenSetup={() => enterSetupReview("credentials")}
            onChangeTraining={onChangeTraining}
          />
        ) : missionMode ? (
          <BirthPhaseMissionBranch
            derived={derived}
            controlBusy={controlBusy}
            advancedOpen={advancedOpen}
            onToggleAdvanced={setAdvancedOpen}
            onStop={handleStopBirth}
            onEnterDeck={enterCommandDeck}
            onExtraTraining={handleExtraTraining}
          />
        ) : (
          // Fail-closed: never orphan empty hero — land on Genesis branch.
          <BirthPhaseGenesisBranch
            derived={derived}
            controlBusy={controlBusy}
            onActivate={() => void handleStartBirth()}
            onWipe={handleWipeBirthData}
            onStop={handleStopBirth}
            onResumeCheckpoint={handleResumeCheckpoint}
            onOpenSetup={() => enterSetupReview("credentials")}
            onChangeTraining={onChangeTraining}
          />
        )}

        {!launchingMode ? (
          <BirthPhaseRecoveryOverlays
            derived={derived}
            retrying={retrying}
            certificateFailureDetail={certificateFailureDetail}
            stalledRecoveryActions={stalledRecoveryActions}
            onDismissRecovery={() => setRecoveryDismissed(true)}
            onResumeBirth={handleResumeBirth}
            onReuseDataBirth={handleReuseDataBirth}
            onWipeRetryBirth={handleWipeRetryBirth}
            onReturnToGenesis={returnToGenesis}
            onRetryBirth={() => void retryBirth()}
          />
        ) : null}
      </motion.div>

      <ModeTransitionVeil
        active={milestoneVeilActive}
        targetMode="REAL"
        durationSec={0.85}
        scopeSelector=".onboarding-shell"
        onComplete={() => setMilestoneVeilActive(false)}
      />
      <ModeTransitionVeil
        active={realPreviewActive}
        targetMode="REAL"
        durationSec={1.2}
        scopeSelector=".onboarding-shell"
        onComplete={onRealPreviewComplete}
      />
      <ModeTransitionVeil
        active={transition.active}
        targetMode={transition.targetMode}
        durationSec={transition.durationSec}
        scopeSelector={transition.scopeSelector}
        onComplete={completeDeckEntry}
      />
    </OnboardingShell>
  );
}
