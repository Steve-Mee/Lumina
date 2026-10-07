import { BirthGenesisDeck } from "@/components/birth/BirthGenesisDeck";
import { PhaseGenesisFrame } from "@/components/shared/PhaseCinematicFrames";
import type { BirthPhaseActions } from "@/hooks/useBirthPhaseActions";
import type { BirthPhaseDerived } from "@/hooks/useBirthPhaseDerived";

interface BirthPhaseGenesisBranchProps {
  derived: BirthPhaseDerived;
  controlBusy: boolean;
  onActivate: () => void;
  onWipe: BirthPhaseActions["handleWipeBirthData"];
  onStop: BirthPhaseActions["handleStopBirth"];
  onResumeCheckpoint: () => void;
  onOpenSetup: () => void;
  onChangeTraining: BirthPhaseActions["onChangeTraining"];
}

export function BirthPhaseGenesisBranch({
  derived,
  controlBusy,
  onActivate,
  onWipe,
  onStop,
  onResumeCheckpoint,
  onOpenSetup,
  onChangeTraining,
}: BirthPhaseGenesisBranchProps) {
  const {
    activating,
    trainingDraft,
    checkpointAvailable,
    interrupted,
    decisionMode,
    status,
    engineLive,
    onboardingError,
    pollError,
    resumePlateauRisk,
    sessionHydrated,
    sessionProbeState,
    sessionProbePending,
  } = derived;

  return (
    <PhaseGenesisFrame
      activating={activating}
      trainingTrades={trainingDraft.training_trades}
      ariaLabel="Neural genesis charter"
    >
      <BirthGenesisDeck
        training={trainingDraft}
        activating={activating}
        checkpointAvailable={checkpointAvailable}
        sessionInterrupted={interrupted}
        decisionMode={decisionMode}
        birthStatus={status}
        busy={controlBusy}
        engineLive={engineLive}
        error={onboardingError}
        pollError={pollError}
        sessionHydrated={sessionHydrated}
        sessionProbeState={sessionProbeState}
        sessionProbePending={sessionProbePending}
        onChangeTraining={onChangeTraining}
        onActivate={onActivate}
        onWipe={onWipe}
        onStop={onStop}
        onResumeCheckpoint={onResumeCheckpoint}
        onOpenSetup={onOpenSetup}
        resumePlateauRisk={resumePlateauRisk}
        resumePlateauRiskTrades={status?.resume_plateau_risk_trades ?? null}
      />
    </PhaseGenesisFrame>
  );
}
