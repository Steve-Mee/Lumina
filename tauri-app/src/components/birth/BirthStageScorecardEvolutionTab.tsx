/** Evolution tab fields for BirthStageScorecard. */
import type { StageScorecardModel } from "@/lib/birthPhaseModel";
import { BirthFieldCard } from "@/components/birth/BirthFieldCard";
import { formatEvolutionAction } from "@/components/birth/BirthStageScorecardFormat";

export function EvolutionTabFields({ scorecard }: { scorecard: StageScorecardModel }) {
  const evolutionActive =
    scorecard.evolutionPhase != null && scorecard.evolutionPhase !== "none";
  const stepLabel =
    scorecard.evolutionStepLabel ??
    (scorecard.evolutionPhase
      ? `Evolution ${scorecard.evolutionPhase.replace(/_/g, " ")}`
      : "—");

  let actionsDetail = "—";
  if (
    scorecard.evolutionActionsTotal != null &&
    scorecard.evolutionActionsCompleted != null
  ) {
    actionsDetail = `${scorecard.evolutionActionsCompleted}/${scorecard.evolutionActionsTotal}`;
  } else if (
    scorecard.evolutionStep != null &&
    scorecard.evolutionActionsRemaining != null
  ) {
    actionsDetail = `step ${scorecard.evolutionStep}/${scorecard.evolutionStep + scorecard.evolutionActionsRemaining}`;
  }

  return (
    <div className="birth-intel-field-grid">
      <BirthFieldCard
        label="Evolution phase"
        value={evolutionActive ? stepLabel : "—"}
        hint={
          scorecard.evolutionPhantomSteps != null && scorecard.evolutionPhantomSteps > 0
            ? `Phantom steps: ${scorecard.evolutionPhantomSteps}`
            : undefined
        }
        tone={evolutionActive ? "warn" : "default"}
      />
      <BirthFieldCard label="Actions" value={actionsDetail} />
      <BirthFieldCard
        label="Rollouts this step"
        value={
          scorecard.evolutionRolloutsThisStep != null &&
          scorecard.evolutionRolloutsMax != null
            ? `${scorecard.evolutionRolloutsThisStep}/${scorecard.evolutionRolloutsMax}`
            : "—"
        }
      />
      <BirthFieldCard
        label="Plateau clock"
        value={
          scorecard.plateauElapsedSec != null
            ? `${Math.ceil(scorecard.plateauElapsedSec / 60)}m elapsed`
            : "—"
        }
      />
      <BirthFieldCard
        label="Trades beyond gate"
        value={
          scorecard.tradesBeyondGate != null
            ? scorecard.tradesBeyondGate.toLocaleString()
            : "—"
        }
      />
      <BirthFieldCard
        label="Hold trap"
        value={scorecard.holdTrapDetected ? "Active" : "—"}
        tone={scorecard.holdTrapDetected ? "warn" : "default"}
      />
      <BirthFieldCard
        label="Last evolution action"
        value={formatEvolutionAction(scorecard)}
        className="birth-intel-field-span"
      />
      <BirthFieldCard
        label="Plateau quarantine"
        value={
          scorecard.plateauQuarantineActive
            ? "Resume grace — detection paused"
            : "—"
        }
        hint={
          scorecard.plateauQuarantineActive
            ? [
                scorecard.plateauQuarantineRolloutsRemaining != null
                  ? `${scorecard.plateauQuarantineRolloutsRemaining} rollouts`
                  : null,
                scorecard.plateauQuarantineTradesRemainingCount != null &&
                scorecard.plateauQuarantineTradesRemainingCount > 0
                  ? `${scorecard.plateauQuarantineTradesRemainingCount} trades remaining`
                  : scorecard.plateauQuarantineTradesRemaining != null
                    ? `${scorecard.plateauQuarantineTradesRemaining} new trades`
                    : null,
              ]
                .filter(Boolean)
                .join(" | ") || undefined
            : undefined
        }
        tone={scorecard.plateauQuarantineActive ? "accent" : "default"}
        className="birth-intel-field-span"
      />
    </div>
  );
}
