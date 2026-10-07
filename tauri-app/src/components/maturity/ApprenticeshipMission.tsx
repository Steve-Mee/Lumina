import { ApprenticeshipLifePulse } from "@/components/maturity/ApprenticeshipLifePulse";
import { apprenticeshipTilesFromLearned } from "@/components/maturity/phaseHubApprenticeship";
import { LivingPhaseMission } from "@/components/shared/LivingPhaseMission";
import type { PhaseChip } from "@/components/shared/PhaseCinematicFrames";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import {
  buildApprenticeshipChecklist,
  type ApprenticeshipProgressView,
} from "@/lib/apprenticeship/apprenticeshipChecklist";
import { apprenticeshipMissionMessage } from "@/lib/apprenticeship/apprenticeshipFailCopy";

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function ApprenticeshipMission({
  hub,
  progress,
  busy,
  onStart,
  onStop,
  onReturnHub,
  onWipe,
}: {
  hub: MaturityHubPayload | null;
  progress: ApprenticeshipProgressView | null;
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
  const checklist = buildApprenticeshipChecklist(progress);
  const tiles = apprenticeshipTilesFromLearned(learned);
  const tile = (label: string) => tiles.find((item) => item.label === label);
  const note = typeof progress?.learned?.note === "string" ? progress.learned.note : null;
  const message = apprenticeshipMissionMessage({
    running,
    error: hub?.error ?? null,
    focusStatus: hub?.focus_status ?? null,
    progressMessage: hub?.progress_message ?? null,
    note,
  });
  const retry = !running && !progress?.pass_now;
  const nA = asNumber(learned.n_a) ?? 0;
  const nD = asNumber(learned.n_d) ?? 0;
  const sharpe = asNumber(learned.sharpe);
  const constitutionOk = tile("Constitution")?.value === "0";
  const recoveryOk = learned.recovery_ok === true;

  const chips: PhaseChip[] = [
    {
      label: "n_A",
      state: nA >= 150 ? "ok" : running ? "partial" : "idle",
      tip: "Policy-only apprenticeship tape. Playground closes do not count.",
    },
    {
      label: "SHARPE",
      state: sharpe != null && sharpe >= 0.2 ? "ok" : running ? "partial" : "idle",
      tip: "Daily-return Sharpe × √252. Floor 0.20. Missing if fewer than 5 days.",
    },
    {
      label: "DD",
      state: running ? "partial" : "idle",
      tip: "Peak-to-trough of MES 1-lot equity vs $50k. Ceiling 12%.",
    },
    {
      label: "CONST",
      state: constitutionOk ? "ok" : "warn",
      tip: "risk_events=0, VaR intact, envelope held, never REAL.",
    },
  ];

  return (
    <LivingPhaseMission
      running={running}
      busy={busy}
      panelTitle="Lopen"
      panelSubtitle={running ? "Walking exam · this tape" : "Trading exam · click to start"}
      titleTip="REAL rules, SIM capital. Playground tape does not count. Not REAL money."
      progressLabel={`${checklist.metCount}/${checklist.totalCount}`}
      statusLine={message}
      chips={chips}
      tiles={tiles}
      kpis={[
        {
          label: "n_A",
          value: `${Math.round(nA)} / 150`,
          detail: "/ 150 policy closes",
          tone: nA >= 150 ? "success" : "accent",
        },
        {
          label: "Sharpe",
          value: tile("Sharpe")?.value ?? "—",
          detail: tile("Sharpe")?.footnote,
          tone: sharpe != null && sharpe >= 0.2 ? "success" : "accent",
        },
        {
          label: "DD",
          value: tile("DD")?.value ?? "—",
          detail: tile("DD")?.footnote,
        },
        {
          label: "Constitution",
          value: tile("Constitution")?.value ?? "—",
          detail: tile("Constitution")?.footnote,
          tone: constitutionOk ? "success" : "warn",
        },
      ]}
      fields={[
        {
          label: "Sessiedagen",
          value: tile("Sessiedagen")?.value ?? String(nD),
          hint: tile("Sessiedagen")?.footnote,
        },
        {
          label: "Recovery",
          value: tile("Recovery")?.value ?? "—",
          hint: tile("Recovery")?.footnote,
          tone: recoveryOk ? "ok" : "warn",
        },
        {
          label: "Doel",
          value: tile("Doel")?.value ?? "Lopen",
          hint: tile("Doel")?.footnote,
        },
      ]}
      checklist={checklist}
      checklistGoal="AND gates"
      lifePulse={
        <ApprenticeshipLifePulse
          running={running}
          activity={learned.activity ?? progress?.progress?.activity}
          nA={learned.n_a ?? progress?.progress?.n_a}
          nD={learned.n_d ?? progress?.progress?.n_d}
          updatedAt={progress?.progress?.updated_at ?? learned.updated_at}
        />
      }
      intelTitle="AND gates"
      intelSubtitle="n_A 150 · Sharpe 0.20 · DD 12% · constitution 0"
      intelChips={chips}
      startLabel={retry ? "RETRY APPRENTICESHIP" : "START APPRENTICESHIP"}
      onStart={onStart}
      onStop={onStop}
      onSecondary={onReturnHub}
      wipeLabel="Wipe Apprenticeship (keep Playground)"
      onWipe={onWipe}
      ctaFootnote={
        running ? "Living clock · walking exam" : "Start · floors stay fail-closed · no REAL"
      }
    />
  );
}
