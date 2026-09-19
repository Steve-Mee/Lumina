import { AwakeningLifePulse } from "@/components/maturity/AwakeningLifePulse";
import { CharterTile } from "@/components/birth/BirthGenesisDeckPrimitives";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import { BirthStagePassChecklistCard } from "@/components/birth/BirthStagePassChecklistCard";
import { awakeningTilesFromLearned } from "@/components/maturity/phaseHubAwakening";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import {
  buildAwakeningChecklist,
  type AwakeningProgressView,
} from "@/lib/awakening/awakeningChecklist";
import { awakeningMissionMessage } from "@/lib/awakening/awakeningFailCopy";
import { cn } from "@/lib/utils";

export function AwakeningMission({
  hub,
  progress,
  busy,
  onStart,
  onStop,
  onReturnHub,
  onWipe,
}: {
  hub: MaturityHubPayload | null;
  progress: AwakeningProgressView | null;
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
  const checklist = buildAwakeningChecklist(progress);
  const tiles = awakeningTilesFromLearned(learned);
  const freezeOk = learned.freeze_ok === true;
  const note = typeof progress?.learned?.note === "string" ? progress.learned.note : null;
  const message = awakeningMissionMessage({
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
        <AwakeningLifePulse
          running={running}
          cycle={learned.cycle ?? progress?.progress?.cycle}
          activity={learned.activity ?? progress?.progress?.activity}
          trainTimesteps={learned.train_timesteps ?? progress?.progress?.train_timesteps}
          nB={learned.n_b ?? progress?.progress?.n_b}
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
        <p className="mb-1.5 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
          {running
            ? freezeOk
              ? "Living clock · Birth freeze intact"
              : "Living clock · freeze not proven"
            : "Click to start · floors stay fail-closed"}
        </p>
        <div className="phase-hub-cta__row">
          <BirthLaunchButton
            activating={running}
            disabled={busy || running}
            idleLabel={(retry ? "Retry Awakening" : "Start Awakening").toUpperCase()}
            onClick={onStart}
            className="phase-hub-cta__primary"
          />
          {running ? (
            <button
              type="button"
              className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle phase-hub-cta__deck"
              disabled={busy}
              onClick={onStop}
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle phase-hub-cta__deck"
              disabled={busy}
              onClick={onReturnHub}
            >
              Phase Hub
            </button>
          )}
        </div>
        <div className="mt-2 flex justify-center">
          <button
            type="button"
            className={cn(
              "font-mono text-[10px] tracking-wide text-rose-200/70 underline-offset-2 hover:underline",
              busy && "pointer-events-none opacity-50",
            )}
            disabled={busy || running}
            onClick={onWipe}
          >
            Wipe Awakening only · keep Birth
          </button>
        </div>
      </div>
    </div>
  );
}
