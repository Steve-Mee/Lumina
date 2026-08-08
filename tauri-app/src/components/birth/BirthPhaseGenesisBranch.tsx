import { lazy, Suspense } from "react";

import { BirthGenesisDeck } from "@/components/birth/BirthGenesisDeck";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import type { BirthPhaseActions } from "@/hooks/useBirthPhaseActions";
import type { BirthPhaseDerived } from "@/hooks/useBirthPhaseDerived";
import { cn } from "@/lib/utils";

const BirthHelixVisual = lazy(() =>
  import("@/components/birth/BirthHelixVisual").then((module) => ({
    default: module.BirthHelixVisual,
  })),
);

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
    status,
    engineLive,
    onboardingError,
    resumePlateauRisk,
    sessionHydrated,
    sessionProbeState,
    sessionProbePending,
  } = derived;

  return (
    <div className="birth-mission-shell relative flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="birth-genesis-grid min-h-0 flex-1 overflow-hidden p-3 md:p-4">
        <div
          className={cn(
            "birth-genesis-helix-stage birth-activation-helix-arena birth-helix-accent-wrap pointer-events-none min-h-0",
            activating && "birth-activation-helix-arena--charge",
          )}
        >
          <div className="birth-activation-stage-inner min-h-0 flex-1">
            <div className="birth-activation-helix-slot birth-helix-accent min-h-0 flex-1">
              <Suspense
                fallback={
                  <div className="flex h-full min-h-0 flex-1 items-center justify-center">
                    <BirthOrganismVisual className="size-48 opacity-80" />
                  </div>
                }
              >
                <BirthHelixVisual
                  ceremonyMode
                  activating={activating}
                  primed={activating}
                  trainingTrades={trainingDraft.training_trades}
                  className="h-full min-h-0 w-full max-w-full"
                />
              </Suspense>
            </div>
          </div>
        </div>
        <section
          className="birth-genesis-panel lumina-glass lumina-glass--overlay flex min-h-0 flex-col overflow-hidden"
          aria-label="Neural genesis charter"
        >
          <BirthGenesisDeck
            training={trainingDraft}
            activating={activating}
            checkpointAvailable={checkpointAvailable}
            sessionInterrupted={interrupted}
            birthStatus={status}
            busy={controlBusy}
            engineLive={engineLive}
            error={onboardingError}
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
        </section>
      </div>
    </div>
  );
}
