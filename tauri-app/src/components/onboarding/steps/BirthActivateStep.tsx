import { lazy, Suspense, useState } from "react";

import { BirthCinematicLayout } from "@/components/birth/BirthCinematicLayout";
import { BirthGenesisDeck } from "@/components/birth/BirthGenesisDeck";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import type { OnboardingDraft } from "@/store/onboardingStore";

const BirthHelixVisual = lazy(() =>
  import("@/components/birth/BirthHelixVisual").then((module) => ({
    default: module.BirthHelixVisual,
  })),
);

interface BirthActivateStepProps {
  draft: OnboardingDraft;
  setupComplete: boolean;
  activating: boolean;
  error: string | null;
  onChangeTraining: (training: Partial<OnboardingDraft["training"]>) => void;
  onActivate: () => void;
}

export function BirthActivateStep({
  draft,
  setupComplete: _setupComplete,
  activating,
  error,
  onChangeTraining,
  onActivate,
}: BirthActivateStepProps) {
  const [helixPrimed, _setHelixPrimed] = useState(false);
  const [sequencing, _setSequencing] = useState(false);
  const helixCharged = helixPrimed || sequencing || activating;

  const caption =
    activating
      ? "Activation sequence engaged — organism awakening"
      : sequencing
        ? "Sequencing neural lattice — hold steady"
        : helixCharged
          ? "Neural lattice primed — commit on your mark"
          : "Organism dormant — awaiting activation sequence";

  const stage = (
    <div className="birth-activation-stage-inner">
      <div className="birth-activation-helix-slot">
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
            primed={helixCharged}
            trainingTrades={draft.training.training_trades}
            className="h-full min-h-0 w-full max-w-2xl"
          />
        </Suspense>
      </div>
      <div className="birth-activation-hud">
        <p className="birth-activation-caption">{caption}</p>
      </div>
    </div>
  );

  const deck = (
    <BirthGenesisDeck
      training={draft.training}
      activating={activating}
      error={error}
      onChangeTraining={onChangeTraining}
      onActivate={onActivate}
    />
  );

  return (
    <BirthCinematicLayout
      className="px-2 md:px-6"
      stage={stage}
      deck={deck}
      stageCharging={sequencing}
    />
  );
}
