import { PlaygroundLifePulse } from "@/components/maturity/PlaygroundLifePulse";
import { PlaygroundSenseBrief } from "@/components/maturity/PlaygroundSenseBrief";
import { playgroundTilesFromLearned } from "@/components/maturity/phaseHubPlayground";
import { LivingPhaseMission } from "@/components/shared/LivingPhaseMission";
import type { PhaseChip } from "@/components/shared/PhaseCinematicFrames";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import {
  buildPlaygroundChecklist,
  type PlaygroundProgressView,
} from "@/lib/playground/playgroundChecklist";
import { playgroundMissionMessage } from "@/lib/playground/playgroundFailCopy";

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function PlaygroundMission({
  hub,
  progress,
  busy,
  onStart,
  onStop,
  onReturnHub,
  onOpenDeck,
  onWipe,
}: {
  hub: MaturityHubPayload | null;
  progress: PlaygroundProgressView | null;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
  onReturnHub: () => void;
  onOpenDeck: () => void;
  onWipe: () => void;
}) {
  const running = Boolean(hub?.runner_active || progress?.runner_active);
  const learned = {
    ...(hub?.focus_learned ?? {}),
    ...(progress?.progress ?? {}),
    ...(progress?.learned ?? {}),
  };
  const checklist = buildPlaygroundChecklist(progress);
  const tiles = playgroundTilesFromLearned(learned);
  const tile = (label: string) => tiles.find((item) => item.label === label);
  const note = typeof progress?.learned?.note === "string" ? progress.learned.note : null;
  const retry = !running && !progress?.pass_now;
  const nP = asNumber(learned.n_p) ?? 0;
  const greenDays = asNumber(learned.green_days) ?? 0;
  const firstFill = learned.first_fill === true;
  const envelopeSealed = learned.envelope_sealed === true;
  const envelope = envelopeSealed && learned.envelope_breached !== true;
  const message = playgroundMissionMessage({
    running,
    error: hub?.error ?? null,
    focusStatus: hub?.focus_status ?? null,
    progressMessage: hub?.progress_message ?? null,
    note,
    envelopeSealed,
  });

  const chips: PhaseChip[] = [
    {
      label: "GROEN",
      state: greenDays >= 5 ? "ok" : running ? "partial" : "idle",
      tip: "Vijf aaneengesloten groene sessiedagen. Een bijvul is geen dag.",
    },
    {
      label: "CLOSES",
      state: firstFill ? "partial" : "idle",
      tip: "Echte fills. Geen poort van 150.",
    },
    {
      label: "METING",
      state: "idle",
      tip: "Papieren uitslag en het hand-examen tegen de plant. Een groene dag is de rekening hoger aan de sluiting.",
    },
    {
      label: "ENVELOPE",
      state: envelope ? "ok" : "warn",
      tip: "Operator-sealed SIM risk envelope. Missing file is unsealed.",
    },
  ];

  return (
    <LivingPhaseMission
      running={running}
      busy={busy}
      panelTitle="Eerste stappen"
      panelSubtitle={
        running ? "Zij kijkt elke minuut · flat is een keuze" : "Klik om te starten · SIM, geen REAL"
      }
      titleTip="Zij kijkt elke gesloten minuut. Een 240-minutenkaars is niet nodig om te beginnen."
      progressLabel={`${checklist.metCount}/${checklist.totalCount}`}
      statusLine={progress?.sense?.headline ? "" : message}
      notice={
        <PlaygroundSenseBrief
          sense={progress?.sense}
          running={running}
          variant={running ? "dock" : "inline"}
        />
      }
      lifePulse={
        <PlaygroundLifePulse
          running={running}
          updatedAt={progress?.progress?.updated_at ?? learned.updated_at}
          nP={nP}
          greenDays={greenDays}
          envelopeSealed={envelopeSealed}
          feedNote={learned.feed_note}
          exchangeNote={progress?.sense?.clock}
        />
      }
      chips={chips}
      tiles={tiles}
      kpis={[
        {
          label: "Groene dagen",
          value: tile("Groene dagen")?.value ?? `${greenDays} / 5`,
          detail: "schoolpoort",
          tone: greenDays >= 5 ? "success" : "accent",
        },
        {
          label: "Closes",
          value: tile("Closes")?.value ?? String(nP),
          detail: "geen poort van 150",
          tone: "accent",
        },
        {
          label: "Mean R",
          value: tile("Mean R")?.value ?? "—",
          detail: tile("Mean R")?.footnote,
        },
        {
          label: "First fill",
          value: tile("First fill")?.value ?? "—",
          detail: tile("First fill")?.footnote,
          tone: firstFill ? "success" : "warn",
        },
      ]}
      fields={[
        {
          label: "Envelope",
          value: tile("Envelope")?.value ?? "—",
          hint: tile("Envelope")?.footnote,
          tone: envelope ? "ok" : "warn",
        },
        {
          label: "Doel",
          value: tile("Doel")?.value ?? "Eerste stappen",
          hint: tile("Doel")?.footnote,
        },
      ]}
      checklist={checklist}
      checklistGoal="AND gates"
      intelTitle="AND gates"
      intelSubtitle="Playground tape · policy-only"
      intelChips={chips}
      startLabel={retry ? "RETRY PLAYGROUND" : "START PLAYGROUND"}
      onStart={onStart}
      onStop={onStop}
      secondaryLabel="Command Deck"
      onSecondary={onOpenDeck}
      extraLinkLabel="Phase Hub"
      onExtraLink={onReturnHub}
      wipeLabel="Wipe Playground (keep Awakening)"
      onWipe={onWipe}
      ctaFootnote={
        running ? "Zij kijkt · een flat is geen storing" : "Start · eerste echte fill · vloeren blijven dicht"
      }
    />
  );
}
