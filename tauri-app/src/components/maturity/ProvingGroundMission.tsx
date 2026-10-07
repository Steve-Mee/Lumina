import { ProvingGroundLifePulse } from "@/components/maturity/ProvingGroundLifePulse";
import { provingGroundTilesFromLearned } from "@/components/maturity/phaseHubProvingGround";
import { LivingPhaseMission } from "@/components/shared/LivingPhaseMission";
import type { PhaseChip } from "@/components/shared/PhaseCinematicFrames";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import {
  buildProvingGroundChecklist,
  type ProvingGroundProgressView,
} from "@/lib/provingGround/provingGroundChecklist";
import { provingGroundMissionMessage } from "@/lib/provingGround/provingGroundFailCopy";

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

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
    ...(progress?.progress ?? {}),
    ...(progress?.learned ?? {}),
  };
  const checklist = buildProvingGroundChecklist(progress);
  const tiles = provingGroundTilesFromLearned(learned);
  const tile = (label: string) => tiles.find((item) => item.label === label);
  const note = typeof progress?.learned?.note === "string" ? progress.learned.note : null;
  const message = provingGroundMissionMessage({
    running,
    error: hub?.error ?? null,
    focusStatus: hub?.focus_status ?? null,
    progressMessage: hub?.progress_message ?? null,
    note,
  });
  const retry = !running && !progress?.pass_now;
  const nG = asNumber(learned.n_g) ?? 0;
  const gate = asNumber(learned.promotion_criteria_passed) ?? 0;
  const shadowOk = learned.shadow_this_run === true;

  const chips: PhaseChip[] = [
    {
      label: "n_G",
      state: nG >= 150 ? "ok" : running ? "partial" : "idle",
      tip: "Policy-only proving tape. Earlier tapes do not count.",
    },
    {
      label: "CERT",
      state: running ? "partial" : "idle",
      tip: "OOS WR ≥ 48% · Sharpe ≥ 0.35 · DD ≤ 8%. Birth certificate JSON is not pass.",
    },
    {
      label: "SHADOW",
      state: shadowOk ? "ok" : running ? "partial" : "idle",
      tip: "This clock: live SIM fill-rate and slippage vs backtest.",
    },
    {
      label: "GATE",
      state: gate >= 4 ? "ok" : running ? "partial" : "idle",
      tip: "PromotionGate.evaluate on this child. Missing evidence = reject.",
    },
  ];

  return (
    <LivingPhaseMission
      running={running}
      busy={busy}
      panelTitle="Driving test"
      panelSubtitle={running ? "Cert exam · this run" : "Last machine exam · click to start"}
      titleTip="Last machine exam before capital. Not walking. Not REAL money."
      progressLabel={`${checklist.metCount}/${checklist.totalCount}`}
      statusLine={message}
      chips={chips}
      tiles={tiles}
      kpis={[
        {
          label: "n_G",
          value: tile("n_G")?.value ?? "0 / 150",
          detail: "/ 150 policy closes",
          tone: nG >= 150 ? "success" : "accent",
        },
        {
          label: "Cert WR",
          value: tile("Cert WR")?.value ?? "—",
          detail: tile("Cert WR")?.footnote,
          tone: "accent",
        },
        {
          label: "Sharpe / DD",
          value: tile("Sharpe / DD")?.value ?? "—",
          detail: tile("Sharpe / DD")?.footnote,
        },
        {
          label: "PromotionGate",
          value: tile("PromotionGate")?.value ?? "0 / 4",
          detail: tile("PromotionGate")?.footnote,
          tone: gate >= 4 ? "success" : "accent",
        },
      ]}
      fields={[
        {
          label: "Shadow",
          value: tile("Shadow")?.value ?? "—",
          hint: tile("Shadow")?.footnote,
          tone: shadowOk ? "ok" : "warn",
        },
        {
          label: "Doel",
          value: tile("Doel")?.value ?? "Rijexamen",
          hint: tile("Doel")?.footnote,
        },
      ]}
      checklist={checklist}
      checklistGoal="AND gates"
      lifePulse={
        <ProvingGroundLifePulse
          running={running}
          activity={learned.activity ?? progress?.progress?.activity}
          nG={learned.n_g ?? progress?.progress?.n_g}
          gate={learned.promotion_criteria_passed ?? progress?.progress?.promotion_criteria_passed}
          updatedAt={progress?.progress?.updated_at ?? learned.updated_at}
        />
      }
      intelTitle="AND gates"
      intelSubtitle="Cert 48% · shadow · PromotionGate 4/4"
      intelChips={chips}
      startLabel={retry ? "RETRY PROVING GROUND" : "START PROVING GROUND"}
      onStart={onStart}
      onStop={onStop}
      onSecondary={onReturnHub}
      wipeLabel="Wipe Proving Ground (keep Apprenticeship)"
      onWipe={onWipe}
      ctaFootnote={
        running ? "Living clock · driving test" : "Start · floors stay fail-closed · no REAL"
      }
    />
  );
}
