import { AwakeningLifePulse } from "@/components/maturity/AwakeningLifePulse";
import {
  awakeningNumber,
  awakeningSkillClock,
  awakeningStableTone,
  awakeningTilesFromLearned,
  formatAwakeningFixed,
} from "@/components/maturity/phaseHubAwakening";
import { LivingPhaseMission } from "@/components/shared/LivingPhaseMission";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import {
  buildAwakeningChecklist,
  type AwakeningProgressView,
} from "@/lib/awakening/awakeningChecklist";
import { awakeningMissionMessage, isAwakeningFailed } from "@/lib/awakening/awakeningFailCopy";
import type { PhaseChip } from "@/components/shared/PhaseCinematicFrames";

export function AwakeningMission({
  hub,
  progress,
  busy,
  clockLive = false,
  onStart,
  onStop,
  onReturnHub,
  onWipe,
}: {
  hub: MaturityHubPayload | null;
  progress: AwakeningProgressView | null;
  busy: boolean;
  /** Onboarding already says the clock is live, before the first progress poll. */
  clockLive?: boolean;
  onStart: () => void;
  onStop: () => void;
  onReturnHub: () => void;
  onWipe: () => void;
}) {
  const polled = hub != null || progress != null;
  const running = polled
    ? Boolean(hub?.runner_active || progress?.runner_active)
    : clockLive;
  const learned = {
    ...(hub?.focus_learned ?? {}),
    ...(progress?.progress ?? {}),
    ...(progress?.learned ?? {}),
  };
  const checklist = buildAwakeningChecklist(progress);
  const tiles = awakeningTilesFromLearned(learned);
  const tile = (label: string) => tiles.find((item) => item.label === label);
  const clock = awakeningSkillClock(learned);
  const freezeOk = learned.freeze_ok === true;
  const note = typeof progress?.learned?.note === "string" ? progress.learned.note : null;
  const message = awakeningMissionMessage({
    running,
    error: hub?.error ?? null,
    focusStatus: hub?.focus_status ?? null,
    progressMessage: hub?.progress_message ?? null,
    note,
  });
  const retry = isAwakeningFailed({
    running,
    error: hub?.error ?? null,
    focusStatus: hub?.focus_status ?? null,
  });
  const medianLossR = awakeningNumber(learned.median_loss_r);
  const pairedCi = awakeningNumber(learned.paired_ci_low);
  const stableValue = tile("STABLE")?.value ?? "INCONCLUSIVE";
  const stableChip = awakeningStableTone(stableValue) === "success" ? "ok" : "warn";
  const plantValue = tile("Plant")?.value ?? "—";
  const plantOk = plantValue === "plant";
  const constitutionValue = tile("Constitution")?.value ?? "—";
  const constitutionOk = constitutionValue === "clear";
  const yn = (value: unknown) =>
    value === true ? "yes" : value === false ? "no" : "—";
  const activityLabel = clock.activity.replace(/_/g, " ");

  const chips: PhaseChip[] = [
    {
      label: "FREEZE",
      state: freezeOk ? "ok" : "warn",
      tip: "Birth artefacts stay read-only while Awakening runs.",
    },
    {
      label: "CLOCK",
      state: running ? "partial" : clock.nB >= 500 ? "ok" : "idle",
      tip: "Policy-only holdout closes. n_B under 500 is inconclusive.",
    },
    { label: stableValue, state: stableChip, tip: tile("STABLE")?.tip ?? "Grind classifier." },
    {
      label: plantOk ? "PLANT" : "PLANT?",
      state: plantOk ? "ok" : "warn",
      tip: tile("Plant")?.tip ?? "Weight sha must equal the Birth plant.",
    },
  ];

  return (
    <LivingPhaseMission
      running={running}
      busy={busy}
      panelTitle="First Watch"
      panelSubtitle={`eval holdout B · no learn · ${activityLabel}`}
      titleTip="One blind holdout-B eval of the frozen Birth plant. No learn(). Not a WR exam. Not REAL."
      progressLabel={`${checklist.metCount}/${checklist.totalCount}`}
      statusLine={message}
      chips={chips}
      tiles={tiles}
      kpis={[
        {
          label: "n_B",
          value: clock.nBLabel,
          detail: "/ 500 policy closes",
          tone: clock.nB >= 500 ? "success" : "accent",
        },
        {
          label: "Occupancy",
          value: tile("Occupancy")?.value ?? "—",
          detail: tile("Occupancy")?.footnote,
        },
        {
          label: "STABLE",
          value: stableValue,
          detail: tile("STABLE")?.footnote,
          tone: awakeningStableTone(stableValue),
        },
        {
          label: "Plant",
          value: plantValue,
          detail: tile("Plant")?.footnote,
          tone: plantOk ? "success" : "warn",
        },
      ]}
      sectionTitle="Holdout book"
      fields={[
        {
          label: "Twin watch",
          value: formatCountOrDash(learned.twin_watch_n),
          hint: "This run only",
          tip: "Twin-source events of this run. A metrics dump is not proof.",
        },
        {
          label: "Process-R",
          value: formatAwakeningFixed(medianLossR),
          hint: "median loss R ≤ 1.5",
          tone: medianLossR != null && medianLossR <= 1.5 ? "ok" : "warn",
        },
        {
          label: "Baseline book",
          value: yn(learned.parent_replay_present),
          hint: "parent ledger on disk",
          tone: learned.parent_replay_present === true ? "ok" : "warn",
        },
        {
          label: "Constitution",
          value: constitutionValue,
          hint: "0 violations · 0 blocks",
          tone: constitutionOk ? "ok" : "warn",
        },
        {
          label: "Paired CI",
          value: pairedCi == null ? "—" : `${pairedCi >= 0 ? "+" : ""}${pairedCi.toFixed(3)}R`,
          hint: "recorded · Playground hand wall",
        },
        {
          label: "Freeze",
          value: freezeOk ? "intact" : "violated",
          hint: "Birth artefacts read-only",
          tone: freezeOk ? "ok" : "danger",
        },
      ]}
      checklist={checklist}
      checklistGoal="First Watch"
      lifePulse={
        <AwakeningLifePulse
          running={running}
          cycle={learned.cycle ?? progress?.progress?.cycle}
          activity={learned.activity ?? progress?.progress?.activity}
          trainTimesteps={learned.train_timesteps ?? progress?.progress?.train_timesteps}
          probeBars={learned.probe_bars ?? progress?.progress?.probe_bars}
          nB={learned.n_b ?? progress?.progress?.n_b}
          updatedAt={progress?.progress?.updated_at ?? learned.updated_at}
        />
      }
      intelTitle="AND gates"
      intelSubtitle={tile("n_B")?.footnote ?? "First Watch clock"}
      intelChips={[
        {
          label: "GATE",
          state: checklist.allMet ? "ok" : checklist.metCount > 0 ? "partial" : "idle",
          tip: `${checklist.metCount}/${checklist.totalCount} AND gates clear`,
        },
        {
          label: "CLOCK",
          state: running ? "partial" : clock.nB >= 500 ? "ok" : "idle",
          tip: "Policy-only holdout clock",
        },
        { label: "STABLE", state: stableChip, tip: tile("STABLE")?.tip ?? "STABLE classifier" },
        {
          label: "FREEZE",
          state: freezeOk ? "ok" : "warn",
          tip: "Birth freeze must stay intact",
        },
      ]}
      intelFields={[
        {
          label: "Policy-only",
          value: yn(learned.policy_only),
          hint: "policy closes only",
          tone: learned.policy_only === true ? "ok" : "warn",
        },
        {
          label: "Recovery",
          value: yn(learned.recovery_ok),
          hint: "stall→retry, freeze held",
          tone: learned.recovery_ok === true ? "ok" : "warn",
        },
      ]}
      startLabel={(retry ? "Retry Awakening" : "Start Awakening").toUpperCase()}
      onStart={onStart}
      onStop={onStop}
      onSecondary={running ? undefined : onReturnHub}
      wipeLabel="Wipe Awakening only · keep Birth"
      onWipe={onWipe}
      ctaFootnote={
        running
          ? freezeOk
            ? "Living clock · Birth freeze intact"
            : "Living clock · freeze not proven"
          : "Start · floors stay fail-closed"
      }
    />
  );
}

function formatCountOrDash(value: unknown): string {
  const n = awakeningNumber(value);
  return n == null ? "—" : Math.round(n).toLocaleString("en-US");
}
