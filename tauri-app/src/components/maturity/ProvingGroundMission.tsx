import { ProvingGroundLifePulse } from "@/components/maturity/ProvingGroundLifePulse";
import { CharterTile } from "@/components/birth/BirthGenesisDeckPrimitives";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import { BirthStagePassChecklistCard } from "@/components/birth/BirthStagePassChecklistCard";
import { provingGroundTilesFromLearned } from "@/components/maturity/phaseHubProvingGround";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import {
  buildProvingGroundChecklist,
  type ProvingGroundProgressView,
} from "@/lib/provingGround/provingGroundChecklist";
import { provingGroundMissionMessage } from "@/lib/provingGround/provingGroundFailCopy";

export function ProvingGroundMission({
  hub,
  progress,
  busy,
  onStart,
  onStop,
  onReturnHub,
  onWipe,
}: {
  hub: MaturityHubPayload | null;
  progress: ProvingGroundProgressView | null;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
  onReturnHub: () => void;
  onWipe: () => void;
}) {
  const running = Boolean(hub?.runner_active || progress?.runner_active);
  const learned = {
    ...(hub?.focus_learned ?? {}),
    ...(progress?.learned ?? {}),
  };
  const checklist = buildProvingGroundChecklist(progress);
  const tiles = provingGroundTilesFromLearned(learned);
  const note = typeof progress?.learned?.note === "string" ? progress.learned.note : null;
  const message = provingGroundMissionMessage({
    running,
    error: hub?.error ?? null,
    focusStatus: hub?.focus_status ?? null,
    progressMessage: hub?.progress_message ?? null,
    note,
  });
  const retry = !running && !progress?.pass_now;

  return (
    <div className="birth-mission-shell relative flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-3 md:p-4">
        <ProvingGroundLifePulse
          running={running}
          activity={learned.activity ?? progress?.progress?.activity}
          nG={learned.n_g ?? progress?.progress?.n_g}
          gate={learned.promotion_criteria_passed ?? progress?.progress?.promotion_criteria_passed}
          updatedAt={progress?.progress?.updated_at ?? learned.updated_at}
        />
        <p className="phase-hub-verdict shrink-0 px-1">{message}</p>
        <div className="genesis-charter-tile-grid phase-hub-kpi-grid shrink-0">
          {tiles.map((tile) => (
            <CharterTile
              key={tile.label}
              label={tile.label}
              value={tile.value}
              tip={tile.tip}
              footnote={tile.footnote}
            />
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          <BirthStagePassChecklistCard
            checklist={checklist}
            goalLabel="AND gates"
            showMode={false}
          />
        </div>
      </div>
      <div className="risk-envelope-cta-bar genesis-launch-cta phase-hub-cta shrink-0">
        <div className="phase-hub-cta__row">
          {running ? (
            <BirthLaunchButton
              idleLabel="STOP CLOCK"
              className="phase-hub-cta__primary"
              disabled={busy}
              onActivate={onStop}
            />
          ) : (
            <BirthLaunchButton
              idleLabel={retry ? "RETRY PROVING GROUND" : "START PROVING GROUND"}
              className="phase-hub-cta__primary"
              disabled={busy}
              onActivate={onStart}
            />
          )}
          <BirthLaunchButton
            idleLabel="PHASE HUB"
            className="phase-hub-cta__deck"
            disabled={busy}
            onActivate={onReturnHub}
          />
        </div>
        {!running ? (
          <button
            type="button"
            className="mt-2 text-xs text-amber-200/80 underline-offset-2 hover:underline"
            onClick={onWipe}
          >
            Wipe Proving Ground (keep Apprenticeship)
          </button>
        ) : null}
      </div>
    </div>
  );
}
